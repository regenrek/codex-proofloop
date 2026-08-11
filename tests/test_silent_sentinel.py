from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VARIANT = ROOT / "skills" / "proofloop-herdr-sol-luna"
SCRIPT = VARIANT / "scripts" / "silent_sentinel.py"
GATE = VARIANT / "scripts" / "test_distillation_gate.py"


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")


def retired_state(root: Path, process: dict) -> tuple[Path, dict]:
    path = root / process["retired_state_record"]
    return path, load_json(path)


class SentinelRuntimeTests(unittest.TestCase):
    def snapshot_gate(self, root: Path, profile: Path, contract: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, str(GATE), "snapshot", "--project", str(root.resolve()), "--project-profile", str(profile.resolve()), "--run-contract", str(contract.resolve())], check=False, capture_output=True, text=True)

    def fixture(self, root: Path, *, selected: bool = True) -> tuple[Path, Path, Path]:
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "--allow-empty", "-qm", "initial"], check=True)
        profile = load_json(VARIANT / "assets" / "project-profile.template.json")
        profile["project"]["name"] = "sentinel-test"
        profile["sentinel_policy"]["max_runtime_minutes"] = 1
        profile_path = root / "profile.json"
        write_json(profile_path, profile)

        contract = load_json(VARIANT / "assets" / "run-contract.template.json")
        contract["project_profile"] = "profile.json"
        contract["luna_mode"] = "silent-sentinel" if selected else None
        contract["allowed_paths"] = ["src/**"]
        contract["test_policy"]["baseline_record"] = ".proofloop/evidence/run/test-baseline.json"
        contract["test_policy"]["result_record"] = ".proofloop/evidence/run/test-gate.json"
        contract["test_policy"]["ephemeral_directory"] = ".proofloop/evidence/run/probes"
        contract["test_policy"]["admission_record"] = ".proofloop/evidence/run/test-admission.json"
        contract["evidence"]["directory"] = ".proofloop/evidence/run"
        contract["cleanup"]["ownership_record"] = ".proofloop/evidence/run/ownership.json"
        contract["cleanup"]["sentinel_process_record"] = ".proofloop/evidence/run/process.json"
        contract["cleanup"]["sentinel_state_record"] = ".proofloop/evidence/run/state.json"
        contract_path = root / "contract.json"
        write_json(contract_path, contract)

        session_path = root / "session.jsonl"
        session_path.write_text("", encoding="utf-8")
        return profile_path, contract_path, session_path

    def run_sentinel(
        self,
        root: Path,
        profile: Path,
        contract: Path,
        session: Path,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--target",
                "fixture-writer",
                "--project",
                str(root),
                "--project-profile",
                str(profile),
                "--run-contract",
                str(contract),
                "--session-file",
                str(session),
                "--once",
                "--dry-run",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

    def test_healthy_once_run_is_silent_and_records_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile, contract, session = self.fixture(root)
            result = self.run_sentinel(root, profile, contract, session)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual("", result.stdout)
            process = load_json(root / ".proofloop" / "evidence" / "run" / "process.json")
            retired_path, state = retired_state(root, process)
            self.assertEqual("stopped", process["status"])
            self.assertEqual("once-complete", process["exit_reason"])
            self.assertIsNotNone(process["stopped_at_utc"])
            self.assertIsNotNone(process["state_retired_at_utc"])
            self.assertIsNone(process["state_retirement_error"])
            self.assertTrue(retired_path.name.startswith("state.retired."))
            self.assertFalse((root / ".proofloop" / "evidence" / "run" / "state.json").exists())
            self.assertEqual("once-complete", state["sentinel_exit_reason"])
            self.assertEqual(process["state_retired_at_utc"], state["retired_at_utc"])
            self.assertEqual([], state["events"])

            archived_before = retired_path.read_bytes()
            restarted = self.run_sentinel(root, profile, contract, session)
            self.assertEqual(1, restarted.returncode)
            self.assertIn("sentinel run is already finalized", restarted.stderr)
            self.assertEqual(archived_before, retired_path.read_bytes())
            self.assertFalse((root / ".proofloop" / "evidence" / "run" / "state.json").exists())

    def test_critical_events_are_deduplicated_into_one_fallback_message(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile, contract, session = self.fixture(root)
            records = [
                {
                    "type": "event_msg",
                    "payload": {
                        "type": "item_completed",
                        "turn_id": "one",
                        "item": {
                            "type": "FileChange",
                            "status": "completed",
                            "changes": {"outside/first.py": {}},
                        },
                    },
                },
                {
                    "type": "event_msg",
                    "payload": {
                        "type": "item_completed",
                        "turn_id": "two",
                        "item": {
                            "type": "FileChange",
                            "status": "completed",
                            "changes": {"outside/second.py": {}},
                        },
                    },
                },
            ]
            session.write_text("".join(json.dumps(item) + "\n" for item in records), encoding="utf-8")
            result = self.run_sentinel(root, profile, contract, session)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(1, result.stdout.count("[LUNA-SENTINEL][STOP]"))
            self.assertIn("PATCH_BUDGET", result.stdout)
            process = load_json(root / ".proofloop" / "evidence" / "run" / "process.json")
            self.assertEqual("mandatory-stop", process["exit_reason"])

    def test_runtime_deadline_cannot_be_reset_by_restart(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile, contract_path, session = self.fixture(root)
            contract = load_json(contract_path)
            digest = hashlib.sha256(
                json.dumps(contract, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
            write_json(
                root / ".proofloop" / "evidence" / "run" / "state.json",
                {
                    "schema_version": 1,
                    "kind": "proofloop/silent-sentinel-state",
                    "contract_digest": digest,
                    "session_id": None,
                    "offset": 0,
                    "started_at": time.time() - 120,
                    "last_material_at": time.time(),
                    "last_validation_patch_count": None,
                    "patch_turns": [],
                    "event_codes": [],
                    "events": [],
                    "target_seen_working": False,
                },
            )
            result = self.run_sentinel(root, profile, contract_path, session)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(1, result.stdout.count("RUNTIME_DEADLINE"))
            process = load_json(root / ".proofloop" / "evidence" / "run" / "process.json")
            self.assertEqual("mandatory-stop", process["exit_reason"])

    def test_null_mode_refuses_to_start_or_write_runtime_records(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile, contract, session = self.fixture(root, selected=False)
            result = self.run_sentinel(root, profile, contract, session)
            self.assertEqual(1, result.returncode)
            self.assertIn("must explicitly select 'silent-sentinel'", result.stderr)
            self.assertFalse((root / ".proofloop" / "evidence" / "run" / "process.json").exists())

    def test_shared_gate_catches_shell_created_test(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); profile, contract, session = self.fixture(root)
            self.assertEqual(0, self.snapshot_gate(root, profile, contract).returncode)
            test = root / "tests" / "test_shell.py"; test.parent.mkdir(); test.write_text("assert True\n", encoding="utf-8")
            result = self.run_sentinel(root, profile, contract, session)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("PERMANENT_TEST_EDIT", result.stdout)

    def test_full_suite_command_stops_build_but_focused_command_does_not(self) -> None:
        for command_kind in ("full", "focused"):
            with self.subTest(command_kind=command_kind), tempfile.TemporaryDirectory() as directory:
                root = Path(directory); profile_path, contract_path, session = self.fixture(root)
                profile = load_json(profile_path); profile["validation"]["full_suite_command"] = "python -m unittest discover"; write_json(profile_path, profile)
                contract = load_json(contract_path)
                command = profile["validation"]["full_suite_command"] if command_kind == "full" else contract["validation"]["command"]
                session.write_text(json.dumps({"type": "response_item", "payload": {"type": "custom_tool_call", "input": command}}) + "\n", encoding="utf-8")
                result = self.run_sentinel(root, profile_path, contract_path, session)
                if command_kind == "full": self.assertIn("FULL_SUITE_EARLY", result.stdout)
                else: self.assertEqual("", result.stdout)

    def test_sigterm_stops_a_pending_sentinel_and_finalizes_its_record(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile, contract, _session = self.fixture(root)
            fake_bin = root / "bin"
            fake_bin.mkdir()
            fake_herdr = fake_bin / "herdr"
            fake_herdr.write_text(
                "#!/bin/sh\nprintf '%s\\n' '{\"result\":{\"agent\":{\"agent_status\":\"idle\"}}}'\n",
                encoding="utf-8",
            )
            fake_herdr.chmod(0o755)
            environment = dict(os.environ)
            environment["PATH"] = f"{fake_bin}{os.pathsep}{environment.get('PATH', '')}"
            process = subprocess.Popen(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--target",
                    "pending-writer",
                    "--project",
                    str(root),
                    "--project-profile",
                    str(profile),
                    "--run-contract",
                    str(contract),
                    "--interval",
                    "10",
                ],
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            process_record = root / ".proofloop" / "evidence" / "run" / "process.json"
            for _ in range(40):
                if process_record.exists():
                    break
                time.sleep(0.05)
            self.assertTrue(process_record.exists())
            process.terminate()
            stdout, stderr = process.communicate(timeout=5)
            self.assertEqual(0, process.returncode, stderr)
            self.assertEqual("", stdout)
            record = load_json(process_record)
            self.assertEqual("stopped", record["status"])
            self.assertEqual("sigterm", record["exit_reason"])
            self.assertIsNotNone(record["stopped_at_utc"])
            retired_path, state = retired_state(root, record)
            self.assertTrue(retired_path.exists())
            self.assertEqual("sigterm", state["sentinel_exit_reason"])
            self.assertFalse((root / ".proofloop" / "evidence" / "run" / "state.json").exists())

    def test_startup_working_without_session_then_idle_remains_pending(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile, contract, _session = self.fixture(root)
            fake_bin = root / "bin"
            fake_bin.mkdir()
            fake_herdr = fake_bin / "herdr"
            fake_herdr.write_text(
                "#!/bin/sh\n"
                "if test ! -f \"$FAKE_COUNTER\"; then\n"
                "  touch \"$FAKE_COUNTER\"\n"
                "  printf '%s\\n' '{\"result\":{\"agent\":{\"agent_status\":\"working\"}}}'\n"
                "else\n"
                "  printf '%s\\n' '{\"result\":{\"agent\":{\"agent_status\":\"idle\"}}}'\n"
                "fi\n",
                encoding="utf-8",
            )
            fake_herdr.chmod(0o755)
            environment = dict(os.environ)
            environment["FAKE_COUNTER"] = str(
                root / ".proofloop" / "evidence" / "run" / "herdr-counter"
            )
            environment["PATH"] = f"{fake_bin}{os.pathsep}{environment.get('PATH', '')}"
            process = subprocess.Popen(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--target",
                    "settled-writer",
                    "--project",
                    str(root),
                    "--project-profile",
                    str(profile),
                    "--run-contract",
                    str(contract),
                    "--interval",
                    "10",
                ],
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            process_record = root / ".proofloop" / "evidence" / "run" / "process.json"
            for _ in range(40):
                if process_record.exists():
                    break
                time.sleep(0.05)
            self.assertTrue(process_record.exists())
            time.sleep(2.3)
            self.assertIsNone(process.poll())
            process.terminate()
            stdout, stderr = process.communicate(timeout=5)
            self.assertEqual(0, process.returncode, stderr)
            self.assertEqual("", stdout)
            process_state = load_json(process_record)
            _retired_path, state = retired_state(root, process_state)
            self.assertEqual("sigterm", process_state["exit_reason"])
            self.assertFalse(state["target_seen_working"])
            self.assertFalse(state["target_activity_observed"])
            self.assertTrue(state["target_observed_pending"])
            self.assertEqual([], state["events"])

    def test_fast_finish_settles_through_shared_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile, contract, _session = self.fixture(root)
            fake_home = root / "home"
            sessions = fake_home / ".codex" / "sessions"
            sessions.mkdir(parents=True)
            session_file = sessions / "rollout-fast-session.jsonl"
            session_file.write_text(
                json.dumps(
                    {
                        "type": "event_msg",
                        "payload": {
                            "type": "item_completed",
                            "turn_id": "fast",
                            "item": {
                                "type": "FileChange",
                                "status": "completed",
                                "changes": {"outside/final.py": {}},
                            },
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            fake_bin = root / "bin"
            fake_bin.mkdir()
            fake_herdr = fake_bin / "herdr"
            fake_herdr.write_text(
                "#!/bin/sh\n"
                "if test ! -f \"$FAKE_COUNTER\"; then\n"
                "  touch \"$FAKE_COUNTER\"\n"
                "  printf '%s\\n' '{\"result\":{\"agent\":{\"agent_status\":\"done\"}}}'\n"
                "else\n"
                "  printf '%s\\n' '{\"result\":{\"agent\":{\"agent_status\":\"done\",\"agent_session\":{\"value\":\"fast-session\"}}}}'\n"
                "fi\n",
                encoding="utf-8",
            )
            fake_herdr.chmod(0o755)
            environment = dict(os.environ)
            environment["HOME"] = str(fake_home)
            environment["FAKE_COUNTER"] = str(root / ".proofloop" / "evidence" / "run" / "herdr-counter")
            environment["PATH"] = f"{fake_bin}{os.pathsep}{environment.get('PATH', '')}"
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--target",
                    "fast-writer",
                    "--project",
                    str(root),
                    "--project-profile",
                    str(profile),
                    "--run-contract",
                    str(contract),
                    "--interval",
                    "10",
                ],
                env=environment,
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual("", result.stdout)
            process = load_json(root / ".proofloop" / "evidence" / "run" / "process.json")
            _retired_path, state = retired_state(root, process)
            self.assertEqual("target-settled", process["exit_reason"])
            self.assertIn("TARGET_SETTLED", state["event_codes"])

    def test_settled_target_gate_failure_never_prompts_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); profile, contract, _ = self.fixture(root)
            self.assertEqual(0, self.snapshot_gate(root, profile, contract).returncode)
            test = root / "tests" / "test_late.py"; test.parent.mkdir(); test.write_text("assert True\n", encoding="utf-8")
            fake_home = root / "home"; sessions = fake_home / ".codex" / "sessions"; sessions.mkdir(parents=True)
            (sessions / "rollout-settled-session.jsonl").write_text(
                json.dumps({"type": "event_msg", "payload": {"type": "agent_message"}}) + "\n",
                encoding="utf-8",
            )
            fake_bin = root / "bin"; fake_bin.mkdir(); prompt_log = root / ".proofloop" / "evidence" / "run" / "prompted"
            fake_herdr = fake_bin / "herdr"
            fake_herdr.write_text("#!/bin/sh\nif test \"$2\" = prompt; then touch \"$PROMPT_LOG\"; fi\nprintf '%s\\n' '{\"result\":{\"agent\":{\"agent_status\":\"done\",\"agent_session\":{\"value\":\"settled-session\"}}}}'\n", encoding="utf-8"); fake_herdr.chmod(0o755)
            environment = dict(os.environ); environment["HOME"] = str(fake_home); environment["PROMPT_LOG"] = str(prompt_log); environment["PATH"] = f"{fake_bin}{os.pathsep}{environment.get('PATH', '')}"
            result = subprocess.run([sys.executable, str(SCRIPT), "--target", "settled", "--project", str(root), "--project-profile", str(profile), "--run-contract", str(contract), "--interval", "10"], env=environment, check=False, capture_output=True, text=True, timeout=5)
            self.assertEqual(2, result.returncode, result.stderr); self.assertFalse(prompt_log.exists())
            process = load_json(root / ".proofloop" / "evidence" / "run" / "process.json")
            self.assertEqual("gate-failed-after-settlement", process["exit_reason"])


if __name__ == "__main__":
    unittest.main()
