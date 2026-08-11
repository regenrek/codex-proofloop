#!/usr/bin/env python3
"""Bounded, opt-in Herdr sentinel for one Codex writer run."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_config import validate_bundle  # noqa: E402
from test_distillation_gate import ensure_baseline, evaluate  # noqa: E402

SETTLED_STATUSES = {"done", "blocked"}
PENDING_POLL_SECONDS = 2
_shutdown_reason: str | None = None


def utc_iso(timestamp: float | None = None) -> str:
    value = time.time() if timestamp is None else timestamp
    return datetime.fromtimestamp(value, timezone.utc).isoformat()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, help="Exact Herdr agent or pane target")
    parser.add_argument("--project", required=True, type=Path, help="Absolute project root")
    parser.add_argument("--project-profile", required=True, type=Path)
    parser.add_argument("--run-contract", required=True, type=Path)
    parser.add_argument("--session-file", type=Path, help="JSONL fixture for a bounded diagnostic run")
    parser.add_argument("--interval", type=int, default=60, help="Polling interval in seconds")
    parser.add_argument("--once", action="store_true", help="Inspect once and exit")
    parser.add_argument("--dry-run", action="store_true", help="Print a critical notice instead of sending it")
    args = parser.parse_args(argv)
    if args.interval < 10:
        parser.error("--interval must be at least 10 seconds")
    if args.session_file is not None and not args.once:
        parser.error("--session-file requires --once")
    return args


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def retired_state_destination(state_path: Path, timestamp: float) -> Path:
    stamp = datetime.fromtimestamp(timestamp, timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    stem = state_path.name[:-5] if state_path.name.endswith(".json") else state_path.name
    candidate = state_path.with_name(f"{stem}.retired.{stamp}.json")
    suffix = 1
    while candidate.exists():
        candidate = state_path.with_name(f"{stem}.retired.{stamp}.{suffix}.json")
        suffix += 1
    return candidate


def retire_state(state_path: Path, state: dict[str, Any], timestamp: float, exit_reason: str) -> Path:
    state["sentinel_exit_reason"] = exit_reason
    state["retired_at_utc"] = utc_iso(timestamp)
    atomic_json(state_path, state)
    destination = retired_state_destination(state_path, timestamp)
    state_path.rename(destination)
    return destination


def configured_path(project: Path, raw: Any, field: str) -> Path:
    if not isinstance(raw, str) or not raw:
        raise ValueError(f"{field}: expected project-relative path")
    path = (project / raw).resolve()
    try:
        path.relative_to(project)
    except ValueError as error:
        raise ValueError(f"{field}: path escapes the project") from error
    return path


def validate_inputs(
    project: Path,
    profile_path: Path,
    contract_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not project.is_absolute() or not project.is_dir():
        raise ValueError("--project must be an existing absolute directory")
    profile = load_json(profile_path)
    contract = load_json(contract_path)
    errors = validate_bundle(profile, contract)
    if errors:
        raise ValueError("configuration failed validation: " + "; ".join(errors))
    if contract.get("luna_mode") != "silent-sentinel":
        raise ValueError("$.luna_mode must explicitly select 'silent-sentinel'")
    if "silent-sentinel" not in profile["roles"]["luna"]["allowed_modes"]:
        raise ValueError("project profile does not allow 'silent-sentinel'")
    expected_profile = (project / contract["project_profile"]).resolve()
    if expected_profile != profile_path:
        raise ValueError("$.project_profile does not resolve to --project-profile")
    return profile, contract


def run_json(command: list[str]) -> dict[str, Any]:
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"{command[0]} exited {result.returncode}")
    value = json.loads(result.stdout)
    if not isinstance(value, dict):
        raise RuntimeError("Herdr returned a non-object response")
    return value


def find_session(session_id: str) -> Path | None:
    root = Path.home() / ".codex" / "sessions"
    matches = sorted(root.rglob(f"*{session_id}.jsonl"), key=lambda path: path.stat().st_mtime)
    return matches[-1] if matches else None


def agent_snapshot(target: str) -> tuple[str | None, str, Path | None]:
    agent = run_json(["herdr", "agent", "get", target])["result"]["agent"]
    status = str(agent.get("agent_status", "unknown"))
    session_id = agent.get("agent_session", {}).get("value")
    if not session_id:
        return None, status, None
    normalized = str(session_id)
    return normalized, status, find_session(normalized)


def read_records(path: Path, offset: int) -> tuple[list[dict[str, Any]], int]:
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        handle.seek(offset)
        for line in handle:
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                records.append(value)
        return records, handle.tell()


def has_session_activity(records: list[dict[str, Any]]) -> bool:
    return any(str(record.get("type") or "") not in {"", "session_meta"} for record in records)


def inspect_records(
    records: list[dict[str, Any]],
    state: dict[str, Any],
    contract: dict[str, Any],
) -> list[tuple[str, str, str]]:
    events: list[tuple[str, str, str]] = []
    patch_turns = {str(item) for item in state.get("patch_turns", [])}
    validation_command = contract["validation"]["command"]
    full_suite_command = state.get("full_suite_command")

    for record in records:
        record_type = record.get("type")
        payload = record.get("payload") or {}
        payload_type = payload.get("type")

        if record_type == "compacted" or payload_type == "context_compacted":
            events.append(("CONTEXT_COMPACTED", "stop", "writer context was compacted"))

        item = payload.get("item") or {}
        if (
            record_type == "event_msg"
            and payload_type == "item_completed"
            and item.get("type") == "FileChange"
            and item.get("status") == "completed"
        ):
            key = payload.get("turn_id") or item.get("id")
            if not key:
                serialized = json.dumps(record, sort_keys=True, default=str)
                key = hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]
            patch_turns.add(str(key))
            state["last_material_at"] = time.time()

        if record_type == "response_item" and payload_type == "custom_tool_call":
            tool_input = str(payload.get("input") or "")
            if validation_command and validation_command in tool_input:
                patch_count = len(patch_turns)
                if state.get("last_validation_patch_count") == patch_count:
                    events.append(
                        ("REPEATED_VALIDATION", "stop", "validation repeated without a new patch")
                    )
                state["last_validation_patch_count"] = patch_count
            if full_suite_command and full_suite_command in tool_input:
                if contract["phase"] == "build" or not contract["test_policy"]["full_suite"]["allowed"]:
                    events.append(("FULL_SUITE_EARLY", "stop", "configured full-suite command ran without explicit HARDEN permission"))

    state["patch_turns"] = sorted(patch_turns)
    limit = contract["budgets"]["max_patch_batches"]
    if len(patch_turns) > limit:
        events.append(("PATCH_BUDGET", "stop", f"{len(patch_turns)} patch batches exceed {limit}"))
    return events


def owner_alive(owner_pid: int) -> bool:
    try:
        os.kill(owner_pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def append_new_events(
    state: dict[str, Any],
    candidates: list[tuple[str, str, str]],
) -> list[dict[str, Any]]:
    seen = {str(code) for code in state.get("event_codes", [])}
    new_events: list[dict[str, Any]] = []
    for code, level, detail in candidates:
        if code in seen:
            continue
        event = {"code": code, "level": level, "detail": detail, "observed_at_utc": utc_iso()}
        state.setdefault("events", []).append(event)
        new_events.append(event)
        seen.add(code)
    state["event_codes"] = sorted(seen)
    return new_events


def critical_notice(task_id: str, events: list[dict[str, Any]]) -> str:
    codes = ",".join(str(event["code"]) for event in events)
    detail = "; ".join(str(event["detail"]) for event in events)
    return (
        f"[LUNA-SENTINEL][STOP][{codes}] Task {task_id}: {detail}. "
        "Finish only the current atomic command, make no further edits or tests, and return a handoff."
    )


def send_critical(target: str, message: str, dry_run: bool) -> None:
    if dry_run:
        print(message)
        return
    result = subprocess.run(
        ["herdr", "agent", "prompt", target, message],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "critical notice delivery failed")


def install_signal_handlers() -> None:
    def request_shutdown(signum: int, _frame: Any) -> None:
        global _shutdown_reason
        _shutdown_reason = signal.Signals(signum).name.lower()

    signal.signal(signal.SIGINT, request_shutdown)
    signal.signal(signal.SIGTERM, request_shutdown)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    project = args.project.resolve()
    profile_path = args.project_profile.resolve()
    contract_path = args.run_contract.resolve()
    process_record: Path | None = None
    process: dict[str, Any] | None = None
    state_path: Path | None = None
    state: dict[str, Any] | None = None
    retire_state_selected = False
    exit_reason = "error"
    exit_code = 1

    try:
        profile, contract = validate_inputs(project, profile_path, contract_path)
        baseline = ensure_baseline(project, profile, contract)
        if baseline.get("verdict") != "pass":
            raise RuntimeError("deterministic gate baseline failed")
        cleanup = contract["cleanup"]
        process_record = configured_path(
            project, cleanup["sentinel_process_record"], "$.cleanup.sentinel_process_record"
        )
        state_path = configured_path(
            project, cleanup["sentinel_state_record"], "$.cleanup.sentinel_state_record"
        )
        retire_state_selected = cleanup["retire_sentinel_state"]
        if process_record.exists():
            prior_process = load_json(process_record)
            if prior_process.get("status") == "running":
                raise RuntimeError("sentinel process record is already running")
            raise RuntimeError(
                "sentinel run is already finalized; use a new run contract and evidence directory"
            )

        digest = hashlib.sha256(
            json.dumps(contract, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        now = time.time()
        runtime_minutes = min(
            profile["sentinel_policy"]["max_runtime_minutes"],
            contract["budgets"]["hard_stop_minutes"],
        )
        if state_path.exists():
            state = load_json(state_path)
            if state.get("kind") != "codex-herdr/silent-sentinel-state":
                raise RuntimeError("sentinel state has the wrong kind")
            if state.get("contract_digest") != digest:
                raise RuntimeError("sentinel state belongs to another contract")
        else:
            state = {
                "schema_version": 1,
                "kind": "codex-herdr/silent-sentinel-state",
                "contract_digest": digest,
                "session_id": None,
                "offset": 0,
                "started_at": now,
                "last_material_at": now,
                "last_validation_patch_count": None,
                "patch_turns": [],
                "event_codes": [],
                "events": [],
                "target_seen_working": False,
                "target_activity_observed": False,
                "target_observed_pending": False,
                "full_suite_command": profile["validation"]["full_suite_command"],
            }
        state["full_suite_command"] = profile["validation"]["full_suite_command"]
        deadline = float(state["started_at"]) + runtime_minutes * 60
        owner_pid = os.getppid()
        if owner_pid <= 1:
            raise RuntimeError("refusing to run without a live owner process")
        process = {
            "schema_version": 1,
            "kind": "codex-herdr/silent-sentinel-process",
            "process_id": os.getpid(),
            "owner_process_id": owner_pid,
            "purpose": "silent-sentinel",
            "started_by_workflow": True,
            "target": args.target,
            "started_at_utc": utc_iso(now),
            "deadline_utc": utc_iso(deadline),
            "state_record": cleanup["sentinel_state_record"],
            "retired_state_record": None,
            "state_retired_at_utc": None,
            "state_retirement_error": None,
            "status": "running",
            "exit_reason": None,
            "stopped_at_utc": None,
        }
        atomic_json(process_record, process)
        atomic_json(state_path, state)
        install_signal_handlers()

        while True:
            if _shutdown_reason is not None:
                exit_reason, exit_code = _shutdown_reason, 0
                break
            if not owner_alive(owner_pid):
                exit_reason, exit_code = "owner-lost", 0
                break

            now = time.time()
            candidates: list[tuple[str, str, str]] = []
            if now >= deadline:
                candidates.append(("RUNTIME_DEADLINE", "stop", "sentinel runtime deadline reached"))

            if args.session_file is not None:
                session_id = args.session_file.resolve().stem
                status = "working"
                session_file = args.session_file.resolve()
            else:
                session_id, status, session_file = agent_snapshot(args.target)

            if status == "unknown":
                candidates.append(("TARGET_UNKNOWN", "stop", "target status became unknown"))

            if session_id is not None and session_file is not None:
                previous_session = state.get("session_id")
                if previous_session is None:
                    if args.session_file is None and not state.get("target_observed_pending"):
                        candidates.append(
                            ("TARGET_NOT_FRESH", "stop", "target already had a session at startup")
                        )
                    state["session_id"] = session_id
                    state["offset"] = 0
                elif previous_session != session_id:
                    candidates.append(("TARGET_REPLACED", "stop", "target switched session"))
                records, offset = read_records(session_file, int(state.get("offset", 0)))
                state["offset"] = offset
                if status == "working":
                    state["target_seen_working"] = True
                    state["target_activity_observed"] = True
                if has_session_activity(records):
                    state["target_activity_observed"] = True
                candidates.extend(inspect_records(records, state, contract))
            elif not state.get("target_activity_observed"):
                state["target_observed_pending"] = True

            gate = evaluate("check", project, profile, contract)
            for item in gate["violations"]:
                code = str(item["code"])
                if contract["phase"] == "harden" and code in {"TEST_ADMISSION_MISSING", "TEST_ADMISSION_INVALID", "TEST_EVIDENCE_MISSING", "EPHEMERAL_LEAK"}:
                    continue
                candidates.append((code, "stop", str(item.get("detail", code))))

            quiet_minutes = (now - float(state["last_material_at"])) / 60
            checkpoint = contract["budgets"]["checkpoint_minutes"]
            if status == "working" and quiet_minutes >= checkpoint:
                candidates.append(
                    ("CHECKPOINT", "warning", f"no material artifact for {quiet_minutes:.0f} minutes")
                )

            target_settling = state.get("target_activity_observed") and (
                status in SETTLED_STATUSES or status == "idle"
            )
            if target_settling:
                settlement = evaluate("settle", project, profile, contract)
                settlement_events = [
                    (str(item["code"]), "stop", str(item.get("detail", item["code"])))
                    for item in settlement["violations"]
                ]
                terminal_stops = [item for item in candidates + settlement_events if item[1] == "stop"]
                if terminal_stops:
                    append_new_events(state, terminal_stops)
                    state["last_checked_at_utc"] = utc_iso(now)
                    atomic_json(state_path, state)
                    exit_reason, exit_code = "gate-failed-after-settlement", 2
                    break
                append_new_events(state, [("TARGET_SETTLED", "completion", f"target settled as {status}")])
                state["last_checked_at_utc"] = utc_iso(now)
                atomic_json(state_path, state)
                exit_reason, exit_code = "target-settled", 0
                break

            new_events = append_new_events(state, candidates)
            state["last_checked_at_utc"] = utc_iso(now)
            stop_events = [event for event in new_events if event["level"] == "stop"]
            if stop_events:
                atomic_json(state_path, state)
                if status == "working":
                    try:
                        send_critical(
                            args.target,
                            critical_notice(contract["task"]["id"], stop_events),
                            args.dry_run,
                        )
                        for event in stop_events:
                            event["delivered_at_utc"] = utc_iso()
                    except RuntimeError as error:
                        for event in stop_events:
                            event["delivery_error"] = str(error)
                        atomic_json(state_path, state)
                        exit_reason, exit_code = "notice-delivery-failed", 2
                        break
                atomic_json(state_path, state)
                exit_reason, exit_code = "mandatory-stop", 0
                break

            atomic_json(state_path, state)
            if args.once:
                exit_reason, exit_code = "once-complete", 0
                break
            time.sleep(args.interval if session_id is not None else PENDING_POLL_SECONDS)

    except (OSError, RuntimeError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"silent-sentinel: {error}", file=sys.stderr)
        if state_path is not None and state is not None:
            append_new_events(
                state,
                [("SENTINEL_ERROR", "blocker", f"runtime failed with {type(error).__name__}")],
            )
            try:
                atomic_json(state_path, state)
            except OSError:
                pass
        exit_reason, exit_code = "error", 1
    finally:
        if process_record is not None and process is not None:
            stopped_at = time.time()
            if retire_state_selected:
                try:
                    if state_path is None or state is None or not state_path.exists():
                        raise OSError("sentinel state record is missing during retirement")
                    retired_path = retire_state(state_path, state, stopped_at, exit_reason)
                    process["retired_state_record"] = retired_path.relative_to(project).as_posix()
                    process["state_retired_at_utc"] = utc_iso(stopped_at)
                except OSError as error:
                    process["state_retirement_error"] = str(error)
                    print(f"silent-sentinel state retirement: {error}", file=sys.stderr)
                    exit_code = 1
            process["status"] = "stopped"
            process["exit_reason"] = exit_reason
            process["stopped_at_utc"] = utc_iso(stopped_at)
            try:
                atomic_json(process_record, process)
            except OSError as error:
                print(f"silent-sentinel cleanup: {error}", file=sys.stderr)
                exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
