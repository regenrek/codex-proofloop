from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VARIANT = ROOT / "skills" / "proofloop-sol-luna"
GATE = VARIANT / "scripts" / "test_distillation_gate.py"


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def load_validator():
    path = VARIANT / "scripts" / "validate_config.py"
    spec = importlib.util.spec_from_file_location("gate_validator", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


class Fixture:
    def __init__(self, root: Path, project: Path | None = None) -> None:
        self.root = root; self.project = project or root
        self.project.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        git(root, "config", "user.email", "test@example.invalid"); git(root, "config", "user.name", "Test")
        (root / ".gitignore").write_text(".proofloop/\n", encoding="utf-8")
        (self.project / "src").mkdir(); (self.project / "src" / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
        self.profile = read(VARIANT / "assets" / "project-profile.template.json")
        self.contract = read(VARIANT / "assets" / "run-contract.template.json")
        self.profile["project"]["name"] = "fixture"
        self.contract["task"]["id"] = "gate-fixture"
        self.contract["project_profile"] = "policy/profile.json"
        self.contract["allowed_paths"] = ["src/**", "tests/**", "test_*.*", "*_test.*", "*.test.*", "*.spec.*"]
        base = ".proofloop/evidence/run"
        self.contract["evidence"]["directory"] = base
        self.contract["test_policy"].update({"baseline_record": f"{base}/baseline.json", "result_record": f"{base}/result.json", "ephemeral_directory": f"{base}/probes", "admission_record": f"{base}/admission.json"})
        self.profile_path = self.project / "policy" / "profile.json"; self.contract_path = self.project / "policy" / "contract.json"
        self.save(); git(root, "add", "."); git(root, "commit", "-qm", "initial")

    def save(self) -> None:
        write(self.profile_path, self.profile); write(self.contract_path, self.contract)

    def gate(self, command: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, str(GATE), command, "--project", str(self.project.resolve()), "--project-profile", str(self.profile_path.resolve()), "--run-contract", str(self.contract_path.resolve())], check=False, capture_output=True, text=True)

    def result(self, command: str) -> tuple[subprocess.CompletedProcess[str], dict]:
        process = self.gate(command); return process, json.loads(process.stdout)


class ValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = load_validator()
        self.profile = read(VARIANT / "assets" / "project-profile.template.json")
        self.contract = read(VARIANT / "assets" / "run-contract.template.json")

    def test_schema_migration_and_removed_field(self) -> None:
        old = dict(self.contract); old["schema_version"] = 2
        self.assertTrue(any("must migrate" in item for item in self.validator.validate_document(old)))
        current = dict(self.contract); current["tests_allowed"] = True
        self.assertTrue(any("tests_allowed" in item and "unexpected" in item for item in self.validator.validate_document(current)))

    def test_phase_and_full_suite_invariants(self) -> None:
        build = json.loads(json.dumps(self.contract)); build["test_policy"]["permanent"]["max_new_invariants"] = 1
        self.assertTrue(any("BUILD requires" in item for item in self.validator.validate_document(build)))
        build = json.loads(json.dumps(self.contract)); build["test_policy"]["full_suite"] = {"allowed": True, "reason": "broad check"}
        self.assertTrue(any("BUILD" in item for item in self.validator.validate_document(build)))
        harden = json.loads(json.dumps(self.contract)); harden["phase"] = "harden"; harden["test_policy"]["permanent"] = {"max_new_invariants": 3, "max_changed_test_files": 3, "max_added_test_lines": 240}
        self.profile["testing"]["harden"]["max_new_invariants"] = 1
        self.assertTrue(any("exceeds project" in item for item in self.validator.validate_bundle(self.profile, harden)))
        harden["test_policy"]["full_suite"] = {"allowed": True, "reason": "release candidate"}
        self.assertTrue(any("no configured" in item for item in self.validator.validate_bundle(self.profile, harden)))

    def test_cross_language_case_insensitive_globs(self) -> None:
        paths = ["test_root.py", "nested/token_test.go", "x/value.test.js", "X/VALUE.SPEC.TS", "ThingTest.java", "nested/ThingTests.kt", "WidgetTests.cs", "tests/unit/a.py"]
        for path in paths:
            with self.subTest(path=path): self.assertTrue(self.validator.path_matches(path, self.profile["testing"]["tracked_test_globs"]))

    def test_admission_duplicates_and_static_budgets(self) -> None:
        contract = json.loads(json.dumps(self.contract)); contract["phase"] = "harden"; contract["allowed_paths"] = ["tests/**"]
        contract["test_policy"]["permanent"] = {"max_new_invariants": 1, "max_changed_test_files": 1, "max_added_test_lines": 10}
        admission = read(VARIANT / "assets" / "test-admission.template.json"); admission["task_id"] = contract["task"]["id"]
        admission["admissions"].append(json.loads(json.dumps(admission["admissions"][0])))
        errors = self.validator.validate_bundle(self.profile, contract, admission)
        self.assertTrue(any("duplicate invariant_id" in item for item in errors))
        admission["admissions"][1]["invariant_id"] = "auth.second-invariant"
        errors = self.validator.validate_bundle(self.profile, contract, admission)
        self.assertTrue(any("invariant budget" in item for item in errors))


class GateTests(unittest.TestCase):
    def test_clean_build_and_shell_created_tests(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fix = Fixture(Path(tmp)); process, result = fix.result("snapshot"); self.assertEqual(0, process.returncode, result)
            process, result = fix.result("settle"); self.assertEqual(0, process.returncode, result)
        for relative in ("test_shell.py", "tests/nested/test_shell.py", "nested/name_test.go"):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as tmp:
                fix = Fixture(Path(tmp)); self.assertEqual(0, fix.gate("snapshot").returncode)
                path = fix.project / relative; path.parent.mkdir(parents=True, exist_ok=True); path.write_text("assert True\n", encoding="utf-8")
                process, result = fix.result("check"); self.assertEqual(2, process.returncode); self.assertIn(relative, result["changed_test_paths"]); self.assertIn("PERMANENT_TEST_EDIT", {item["code"] for item in result["violations"]})

    def test_preexisting_dirty_is_preserved_and_further_change_counts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fix = Fixture(Path(tmp)); test = fix.project / "tests" / "test_existing.py"; test.parent.mkdir(); test.write_text("one\n", encoding="utf-8"); git(fix.root, "add", "."); git(fix.root, "commit", "-qm", "test")
            test.write_text("user change\n", encoding="utf-8"); self.assertEqual(0, fix.gate("snapshot").returncode)
            _, unchanged = fix.result("check"); self.assertEqual([], unchanged["changed_test_paths"])
            test.write_text("agent change\n", encoding="utf-8"); _, changed = fix.result("check"); self.assertEqual(["tests/test_existing.py"], changed["changed_test_paths"])
            test.write_text("user change\n", encoding="utf-8"); _, restored = fix.result("check"); self.assertEqual([], restored["changed_test_paths"])

    def test_baseline_cannot_reset_or_cross_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fix = Fixture(Path(tmp)); self.assertEqual(0, fix.gate("snapshot").returncode)
            (fix.project / "src" / "app.py").write_text("VALUE = 2\n", encoding="utf-8")
            process, result = fix.result("snapshot"); self.assertEqual(2, process.returncode); self.assertEqual("BASELINE_MISMATCH", result["violations"][0]["code"])
            fix.contract["task"]["goal"] = "another"; fix.save(); process, result = fix.result("check"); self.assertEqual(2, process.returncode); self.assertEqual("BASELINE_MISMATCH", result["violations"][0]["code"])

    def test_ephemeral_cleanup_and_test_removal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fix = Fixture(Path(tmp)); test = fix.project / "tests" / "test_old.py"; test.parent.mkdir(); test.write_text("old\n", encoding="utf-8"); git(fix.root, "add", "."); git(fix.root, "commit", "-qm", "old test")
            self.assertEqual(0, fix.gate("snapshot").returncode)
            probe = fix.project / fix.contract["test_policy"]["ephemeral_directory"] / "probe.py"; probe.parent.mkdir(parents=True); probe.write_text("probe\n", encoding="utf-8")
            _, result = fix.result("settle"); self.assertIn("EPHEMERAL_LEAK", {item["code"] for item in result["violations"]})
            probe.unlink(); process, cleaned = fix.result("settle"); self.assertEqual(0, process.returncode, cleaned)
            test.unlink(); _, result = fix.result("settle"); self.assertIn("TEST_REMOVAL_UNSUPPORTED", {item["code"] for item in result["violations"]})

    def test_rename_and_zero_budget_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fix = Fixture(Path(tmp)); old = fix.project / "tests" / "test_old.py"; old.parent.mkdir(); old.write_text("old\n", encoding="utf-8"); git(fix.root, "add", "."); git(fix.root, "commit", "-qm", "old")
            fix.contract["phase"] = "harden"; fix.contract["test_policy"]["permanent"] = {"max_new_invariants": 0, "max_changed_test_files": 0, "max_added_test_lines": 0}; fix.save(); git(fix.root, "add", "."); git(fix.root, "commit", "-qm", "contract")
            self.assertEqual(0, fix.gate("snapshot").returncode); old.rename(fix.project / "tests" / "test_new.py")
            _, result = fix.result("settle"); codes = {item["code"] for item in result["violations"]}; self.assertIn("TEST_REMOVAL_UNSUPPORTED", codes); self.assertIn("TEST_BUDGET", codes)

    def test_valid_harden_admission_and_missing_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fix = Fixture(Path(tmp)); test = fix.project / "tests" / "test_auth.py"; test.parent.mkdir(); test.write_text("old = True\n", encoding="utf-8"); git(fix.root, "add", "."); git(fix.root, "commit", "-qm", "test")
            fix.contract["phase"] = "harden"; fix.contract["test_policy"]["permanent"] = {"max_new_invariants": 1, "max_changed_test_files": 1, "max_added_test_lines": 100}; fix.save(); git(fix.root, "add", "."); git(fix.root, "commit", "-qm", "harden contract")
            self.assertEqual(0, fix.gate("snapshot").returncode); test.write_text("old = True\nnew = True\n", encoding="utf-8")
            _, missing = fix.result("settle"); self.assertIn("TEST_ADMISSION_MISSING", {item["code"] for item in missing["violations"]})
            base = fix.contract["evidence"]["directory"]; evidence = [f"{base}/existing.json", f"{base}/candidate.json", f"{base}/final.json"]
            admission = read(VARIANT / "assets" / "test-admission.template.json"); admission["task_id"] = "gate-fixture"; item = admission["admissions"][0]; item["test_paths"] = ["tests/test_auth.py"]; item["counterfactual"]["existing_suite"]["evidence"] = evidence[0]; item["counterfactual"]["candidate"]["evidence"] = evidence[1]; item["final"]["evidence"] = evidence[2]
            write(fix.project / fix.contract["test_policy"]["admission_record"], admission)
            item["test_paths"] = ["tests/test_other.py"]; write(fix.project / fix.contract["test_policy"]["admission_record"], admission)
            _, uncovered = fix.result("settle"); self.assertIn("TEST_ADMISSION_MISSING", {entry["code"] for entry in uncovered["violations"]})
            item["test_paths"] = ["tests/test_auth.py"]; write(fix.project / fix.contract["test_policy"]["admission_record"], admission)
            _, absent = fix.result("settle"); self.assertIn("TEST_EVIDENCE_MISSING", {item["code"] for item in absent["violations"]})
            for path in evidence: write(fix.project / path, {"ok": True})
            process, passed = fix.result("settle"); self.assertEqual(0, process.returncode, passed); self.assertEqual(["auth.expired-token-rejected"], passed["admitted_invariants"])

    def test_project_below_worktree_and_spaces(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "outer repo"; project = root / "packages" / "project with spaces"; fix = Fixture(root, project)
            self.assertEqual(0, fix.gate("snapshot").returncode); changed = project / "src" / "space file.py"; changed.write_text("x = 1\n", encoding="utf-8")
            process, result = fix.result("settle"); self.assertEqual(0, process.returncode, result); self.assertIn("src/space file.py", result["changed_paths"])


if __name__ == "__main__": unittest.main()
