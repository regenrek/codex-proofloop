#!/usr/bin/env python3
"""Deterministic, dependency-free Test Distillation Gate."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_config import normalize_path, path_inside, path_matches, validate_bundle  # noqa: E402

RESULT_KIND = "codex-herdr/test-distillation-result"
BASELINE_KIND = "codex-herdr/test-distillation-baseline"


class GateError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def atomic_bytes(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("wb") as handle:
        handle.write(value); handle.flush(); os.fsync(handle.fileno())
    os.replace(temporary, path)


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise GateError(f"{path}: {error}") from error
    if not isinstance(value, dict):
        raise GateError(f"{path}: expected JSON object")
    return value


def configured_path(project: Path, raw: Any, field: str) -> Path:
    if not isinstance(raw, str) or not raw:
        raise GateError(f"{field}: expected project-relative path")
    candidate = (project / raw).resolve(strict=False)
    try: candidate.relative_to(project)
    except ValueError as error: raise GateError(f"{field}: path escapes project") from error
    return candidate


def run_git(root: Path, *arguments: str) -> bytes:
    try:
        result = subprocess.run(["git", "-C", str(root), *arguments], capture_output=True, check=False)
    except OSError as error:
        raise GateError(f"Git unavailable: {error}") from error
    if result.returncode:
        detail = result.stderr.decode("utf-8", "replace").strip()
        raise GateError(f"Git command failed: {detail or f'exit {result.returncode}'}")
    return result.stdout


def git_context(project: Path) -> tuple[Path, str, str]:
    root = Path(run_git(project, "rev-parse", "--show-toplevel").decode().strip()).resolve()
    try: relative = project.relative_to(root).as_posix()
    except ValueError as error: raise GateError("project is outside enclosing Git worktree") from error
    head = run_git(root, "rev-parse", "--verify", "HEAD").decode().strip()
    return root, (relative if relative != "." else ""), head


def project_path(git_path: str, prefix: str) -> str | None:
    normalized = normalize_path(git_path)
    if not prefix: return normalized
    prefix = normalize_path(prefix)
    if normalized == prefix: return ""
    if normalized.startswith(prefix + "/"): return normalized[len(prefix) + 1:]
    return None


def status_map(git_root: Path, prefix: str) -> dict[str, str]:
    pathspec = prefix or "."
    raw = run_git(git_root, "status", "--porcelain=v1", "-z", "--untracked-files=all", "--", pathspec)
    parts = raw.split(b"\0"); result: dict[str, str] = {}; index = 0
    while index < len(parts):
        entry = parts[index]
        if not entry: index += 1; continue
        text = entry.decode("utf-8", "surrogateescape")
        if len(text) < 4: raise GateError("unparseable NUL-delimited Git status")
        code, raw_path = text[:2], text[3:]
        relative = project_path(raw_path, prefix)
        if relative is not None: result[relative] = code
        if "R" in code or "C" in code:
            index += 1
            if index >= len(parts) or not parts[index]: raise GateError("incomplete Git rename record")
            source = parts[index].decode("utf-8", "surrogateescape")
            source_relative = project_path(source, prefix)
            if source_relative is not None: result[source_relative] = code + ":source"
        index += 1
    return result


def safe_bytes(path: Path) -> bytes | None:
    try:
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode): return os.readlink(path).encode("utf-8", "surrogateescape")
        if not stat.S_ISREG(mode): return None
        return path.read_bytes()
    except (OSError, UnicodeError): return None


def fingerprint(path: Path) -> dict[str, Any]:
    try: info = path.lstat()
    except FileNotFoundError: return {"exists": False}
    data = safe_bytes(path)
    return {"exists": True, "mode": stat.S_IFMT(info.st_mode), "size": info.st_size, "sha256": hashlib.sha256(data).hexdigest() if data is not None else None}


def load_inputs(project: Path, profile_path: Path, contract_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    if not project.is_absolute() or not project.is_dir(): raise GateError("--project must be an existing absolute directory")
    for label, path in (("--project-profile", profile_path), ("--run-contract", contract_path)):
        try: path.relative_to(project)
        except ValueError as error: raise GateError(f"{label} must resolve inside --project") from error
    profile, contract = load_json(profile_path), load_json(contract_path)
    errors = validate_bundle(profile, contract)
    if errors: raise GateError("configuration failed validation: " + "; ".join(errors))
    expected = configured_path(project, contract["project_profile"], "$.project_profile")
    if expected != profile_path.resolve(): raise GateError("$.project_profile does not resolve to --project-profile")
    return profile, contract


def internal_directory(baseline_path: Path) -> Path:
    return baseline_path.with_name(f".{baseline_path.name}.files")


def is_forbidden(path: str, profile: dict[str, Any]) -> bool:
    return path_matches(path, profile["paths"]["forbidden"])


def is_permanent_test(path: str, profile: dict[str, Any], contract: dict[str, Any]) -> bool:
    ephemeral = contract["test_policy"]["ephemeral_directory"]
    return not path_inside(path, ephemeral) and path_matches(path, profile["testing"]["tracked_test_globs"])


def snapshot(project: Path, profile: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    policy = contract["test_policy"]
    baseline_path = configured_path(project, policy["baseline_record"], "$.test_policy.baseline_record")
    digest = canonical_digest(contract)
    if baseline_path.exists():
        existing = load_json(baseline_path)
        code = "BASELINE_MISMATCH"
        detail = "existing baseline belongs to another contract" if existing.get("contract_digest") != digest else "existing baseline cannot be reset or overwritten"
        return {"schema_version": 1, "kind": BASELINE_KIND, "task_id": contract["task"]["id"], "contract_digest": digest, "violations": [{"code": code, "detail": detail}], "verdict": "fail", "snapshotted_at_utc": utc_now()}
    git_root, prefix, head = git_context(project)
    status = status_map(git_root, prefix)
    dirty: dict[str, Any] = {}; copies = internal_directory(baseline_path)
    for path, code in sorted(status.items()):
        if path_inside(path, contract["evidence"]["directory"]): continue
        if is_forbidden(path, profile): raise GateError(f"cannot establish trustworthy baseline: forbidden path is dirty: {path}")
        absolute = project / path; meta = fingerprint(absolute); meta["status"] = code
        if is_permanent_test(path, profile, contract) and meta.get("exists"):
            data = safe_bytes(absolute)
            if data is not None:
                name = hashlib.sha256(path.encode("utf-8", "surrogateescape")).hexdigest() + ".bin"
                atomic_bytes(copies / name, data); meta["snapshot"] = name
        dirty[path] = meta
    record = {"schema_version": 1, "kind": BASELINE_KIND, "task_id": contract["task"]["id"], "contract_digest": digest, "git_root": str(git_root), "project_prefix": prefix, "head": head, "preexisting_changes": dirty, "snapshotted_at_utc": utc_now(), "violations": [], "verdict": "pass"}
    atomic_json(baseline_path, record)
    return record


def read_baseline(project: Path, contract: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    baseline_path = configured_path(project, contract["test_policy"]["baseline_record"], "$.test_policy.baseline_record")
    if not baseline_path.exists(): raise GateError("BASELINE_MISSING: run snapshot before editing")
    baseline = load_json(baseline_path)
    if baseline.get("kind") != BASELINE_KIND or baseline.get("contract_digest") != canonical_digest(contract): raise GateError("BASELINE_MISMATCH: baseline does not match exact contract digest")
    return baseline_path, baseline


def current_agent_changes(project: Path, profile: dict[str, Any], contract: dict[str, Any], baseline: dict[str, Any]) -> tuple[list[str], dict[str, str]]:
    git_root = Path(baseline["git_root"]); prefix = str(baseline["project_prefix"])
    current = status_map(git_root, prefix); before = baseline.get("preexisting_changes", {})
    paths = set(current) | set(before); changed: list[str] = []
    for path in sorted(paths):
        if path_inside(path, contract["evidence"]["directory"]): continue
        if path in before:
            if fingerprint(project / path) != {key: value for key, value in before[path].items() if key in {"exists", "mode", "size", "sha256"}}: changed.append(path)
        elif path in current:
            changed.append(path)
    return changed, current


def added_lines(project: Path, path: str, baseline_path: Path, baseline: dict[str, Any]) -> int:
    current = safe_bytes(project / path)
    if current is None or b"\0" in current: return 0
    meta = baseline.get("preexisting_changes", {}).get(path)
    if meta and meta.get("snapshot"):
        try: original = (internal_directory(baseline_path) / meta["snapshot"]).read_bytes()
        except OSError: raise GateError(f"baseline snapshot missing for {path}")
    elif meta:
        original = b""
    else:
        git_root = Path(baseline["git_root"]); prefix = str(baseline["project_prefix"])
        git_path = f"{prefix}/{path}" if prefix else path
        result = subprocess.run(["git", "-C", str(git_root), "show", f"{baseline['head']}:{git_path}"], capture_output=True, check=False)
        original = result.stdout if result.returncode == 0 else b""
    if b"\0" in original: return 0
    old = original.decode("utf-8", "replace").splitlines(); new = current.decode("utf-8", "replace").splitlines()
    return sum(1 for line in difflib.ndiff(old, new) if line.startswith("+ "))


def violation(code: str, detail: str, path: str | None = None) -> dict[str, str]:
    item = {"code": code, "detail": detail}
    if path is not None: item["path"] = path
    return item


def deduplicate(items: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str | None]] = set(); result = []
    for item in items:
        key = (item["code"], item.get("path"))
        if key not in seen: seen.add(key); result.append(item)
    return result


def remaining_ephemeral(project: Path, contract: dict[str, Any]) -> list[str]:
    raw = contract["test_policy"]["ephemeral_directory"]; root = configured_path(project, raw, "$.test_policy.ephemeral_directory")
    if not root.exists(): return []
    if root.is_symlink() or root.is_file(): return [normalize_path(raw)]
    return [normalize_path(str(path.relative_to(project))) for path in sorted(root.rglob("*")) if path.is_file() or path.is_symlink()]


def admission_checks(project: Path, profile: dict[str, Any], contract: dict[str, Any], changed_tests: list[str], line_count: int) -> tuple[list[dict[str, str]], list[str]]:
    violations: list[dict[str, str]] = []; admitted: list[str] = []; policy = contract["test_policy"]; admission_path = configured_path(project, policy["admission_record"], "$.test_policy.admission_record")
    if not changed_tests and not admission_path.exists(): return violations, admitted
    if not admission_path.exists(): return [violation("TEST_ADMISSION_MISSING", "permanent test changes require an admission document")], admitted
    try: admission = load_json(admission_path)
    except GateError as error: return [violation("TEST_ADMISSION_INVALID", str(error))], admitted
    errors = validate_bundle(profile, contract, admission)
    if errors: violations.append(violation("TEST_ADMISSION_INVALID", "; ".join(errors)))
    admissions = admission.get("admissions", []) if isinstance(admission.get("admissions"), list) else []
    covered = {normalize_path(path) for item in admissions if isinstance(item, dict) for path in item.get("test_paths", []) if isinstance(path, str)}
    admitted = [str(item.get("invariant_id")) for item in admissions if isinstance(item, dict) and item.get("invariant_id")]
    for path in changed_tests:
        if path not in covered: violations.append(violation("TEST_ADMISSION_MISSING", "changed test path is not covered by an admission", path))
    for item in admissions:
        if not isinstance(item, dict): continue
        counter = item.get("counterfactual", {}); final = item.get("final", {})
        for evidence in (counter.get("existing_suite", {}).get("evidence"), counter.get("candidate", {}).get("evidence"), final.get("evidence")):
            if isinstance(evidence, str) and not configured_path(project, evidence, "admission evidence").is_file(): violations.append(violation("TEST_EVIDENCE_MISSING", "admission evidence does not exist", normalize_path(evidence)))
    budget = policy["permanent"]
    if len(admitted) > budget["max_new_invariants"] or len(changed_tests) > budget["max_changed_test_files"] or line_count > budget["max_added_test_lines"]:
        violations.append(violation("TEST_BUDGET", "admission exceeds invariant, file, or added-line budget"))
    return violations, admitted


def evaluate(command: str, project: Path, profile: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    baseline_path, baseline = read_baseline(project, contract)
    changed, statuses = current_agent_changes(project, profile, contract, baseline)
    tests = sorted(path for path in changed if is_permanent_test(path, profile, contract)); violations: list[dict[str, str]] = []
    for path in changed:
        if is_forbidden(path, profile) or not path_matches(path, contract["allowed_paths"]): violations.append(violation("OUT_OF_SCOPE_WRITE", "agent change is outside contract scope", path))
    for path in tests:
        code = statuses.get(path, "")
        if not (project / path).exists() or "D" in code or "R" in code: violations.append(violation("TEST_REMOVAL_UNSUPPORTED", "test deletion or rename requires a future retirement workflow", path))
        elif contract["phase"] == "build": violations.append(violation("PERMANENT_TEST_EDIT", "BUILD prohibits tracked permanent test edits", path))
    line_count = sum(added_lines(project, path, baseline_path, baseline) for path in tests if (project / path).exists())
    budget = contract["test_policy"]["permanent"]
    if len(tests) > budget["max_changed_test_files"] or line_count > budget["max_added_test_lines"]: violations.append(violation("TEST_BUDGET", "permanent test file or line budget exceeded"))
    remaining = remaining_ephemeral(project, contract) if command == "settle" else []
    if remaining: violations.extend(violation("EPHEMERAL_LEAK", "temporary probe remains at settlement", path) for path in remaining)
    admitted: list[str] = []
    if command == "settle" and contract["phase"] == "harden":
        extra, admitted = admission_checks(project, profile, contract, tests, line_count); violations.extend(extra)
    result = {"schema_version": 1, "kind": RESULT_KIND, "task_id": contract["task"]["id"], "phase": contract["phase"], "contract_digest": canonical_digest(contract), "changed_paths": changed, "changed_test_paths": tests, "added_test_lines": line_count, "admitted_invariants": admitted, "remaining_ephemeral_paths": remaining, "violations": deduplicate(violations), "verdict": "fail" if violations else "pass", "settled_at_utc": utc_now()}
    if command == "settle":
        result_path = configured_path(project, contract["test_policy"]["result_record"], "$.test_policy.result_record"); atomic_json(result_path, result)
        if result["verdict"] == "pass": shutil.rmtree(internal_directory(baseline_path), ignore_errors=True)
    return result


def ensure_baseline(project: Path, profile: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    path = configured_path(project, contract["test_policy"]["baseline_record"], "$.test_policy.baseline_record")
    if not path.exists(): return snapshot(project, profile, contract)
    _, baseline = read_baseline(project, contract); return baseline


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__); sub = parser.add_subparsers(dest="command", required=True)
    for name in ("snapshot", "check", "settle"):
        item = sub.add_parser(name); item.add_argument("--project", required=True, type=Path); item.add_argument("--project-profile", required=True, type=Path); item.add_argument("--run-contract", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv); result: dict[str, Any]; project: Path | None = None; contract: dict[str, Any] | None = None
    try:
        project = args.project.resolve(); profile, contract = load_inputs(project, args.project_profile.resolve(), args.run_contract.resolve())
        result = snapshot(project, profile, contract) if args.command == "snapshot" else evaluate(args.command, project, profile, contract)
        code = 0 if result.get("verdict") == "pass" else 2
    except Exception as error:
        message = str(error); violation_code = "GIT_UNAVAILABLE" if "Git" in message or "git" in message else ("BASELINE_MISSING" if "BASELINE_MISSING" in message else ("BASELINE_MISMATCH" if "BASELINE_MISMATCH" in message else "GATE_ERROR"))
        policy_failure = violation_code in {"BASELINE_MISSING", "BASELINE_MISMATCH"}
        result = {"schema_version": 1, "kind": RESULT_KIND, "violations": [violation(violation_code, message)], "verdict": "fail" if policy_failure else "error", "settled_at_utc": utc_now()}; code = 2 if policy_failure else 1
        if args.command == "settle" and project is not None and contract is not None:
            try:
                result.update({"task_id": contract["task"]["id"], "phase": contract["phase"], "contract_digest": canonical_digest(contract)})
                atomic_json(configured_path(project, contract["test_policy"]["result_record"], "$.test_policy.result_record"), result)
            except (GateError, OSError, KeyError):
                pass
        print(f"test-distillation-gate: {error}", file=sys.stderr)
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return code


if __name__ == "__main__": raise SystemExit(main())
