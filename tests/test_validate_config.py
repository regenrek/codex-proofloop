from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = ROOT / "scripts" / "validate_config.py"
SPEC = importlib.util.spec_from_file_location("validate_config", VALIDATOR_PATH)
assert SPEC is not None and SPEC.loader is not None
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


def load(relative_path: str) -> dict:
    with (ROOT / relative_path).open(encoding="utf-8") as handle:
        return json.load(handle)


class ConfigValidationTests(unittest.TestCase):
    def test_shipped_templates_and_planr_example_are_valid(self) -> None:
        for path in (
            "assets/project-profile.template.json",
            "assets/run-contract.template.json",
            "examples/planr-project-profile.json",
        ):
            with self.subTest(path=path):
                self.assertEqual([], VALIDATOR.validate_document(load(path)))

    def test_cli_validates_multiple_documents(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(VALIDATOR_PATH),
                str(ROOT / "assets/project-profile.template.json"),
                str(ROOT / "assets/run-contract.template.json"),
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual(2, result.stdout.count("OK "))

    def test_profile_rejects_noncanonical_agent_ownership(self) -> None:
        profile = load("assets/project-profile.template.json")
        profile["roles"]["sol"]["sole_writer"] = False
        profile["roles"]["luna"]["read_only"] = False
        profile["roles"]["fable"]["max_turns_per_hypothesis"] = 2
        errors = VALIDATOR.validate_document(profile)
        self.assertTrue(any("sole_writer" in error for error in errors))
        self.assertTrue(any("luna.read_only" in error for error in errors))
        self.assertTrue(any("max_turns_per_hypothesis" in error for error in errors))

    def test_contract_rejects_absolute_paths_and_invalid_budget(self) -> None:
        contract = load("assets/run-contract.template.json")
        contract["allowed_paths"] = ["/tmp/outside"]
        contract["budgets"]["checkpoint_minutes"] = 45
        contract["budgets"]["hard_stop_minutes"] = 20
        errors = VALIDATOR.validate_document(contract)
        self.assertTrue(any("project-relative path" in error for error in errors))
        self.assertTrue(any("checkpoint_minutes must be less" in error for error in errors))

    def test_manual_acceptance_requires_explicit_criteria(self) -> None:
        contract = load("assets/run-contract.template.json")
        contract["manual_acceptance"]["required"] = True
        contract["manual_acceptance"]["criteria"] = []
        errors = VALIDATOR.validate_document(contract)
        self.assertTrue(any("required manual acceptance" in error for error in errors))

    def test_cleanup_and_pane_invariants_cannot_be_disabled(self) -> None:
        profile = load("assets/project-profile.template.json")
        profile["pane_policy"]["close_recorded_only"] = False
        profile["pane_policy"]["max_completed_workflow_panes"] = 1
        errors = VALIDATOR.validate_document(profile)
        self.assertTrue(any("close_recorded_only" in error for error in errors))
        self.assertTrue(any("max_completed_workflow_panes" in error for error in errors))

        contract = load("assets/run-contract.template.json")
        contract["cleanup"]["leave_preexisting_panes_open"] = False
        errors = VALIDATOR.validate_document(contract)
        self.assertTrue(any("leave_preexisting_panes_open" in error for error in errors))

    def test_unexpected_fields_are_rejected(self) -> None:
        profile = copy.deepcopy(load("assets/project-profile.template.json"))
        profile["validation"]["retry_count"] = 10
        errors = VALIDATOR.validate_document(profile)
        self.assertTrue(any("unexpected field" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
