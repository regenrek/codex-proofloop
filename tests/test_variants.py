from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VARIANTS = {
    "codex-herdr-sol-luna": {"fable": False, "planr": False},
    "codex-herdr-sol-luna-fable": {"fable": True, "planr": False},
    "codex-herdr-sol-luna-fable-planr": {"fable": True, "planr": True},
}


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_validator(variant: str):
    path = ROOT / variant / "scripts" / "validate_config.py"
    spec = importlib.util.spec_from_file_location(f"validate_{variant.replace('-', '_')}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def variant_text(directory: Path) -> str:
    suffixes = {".json", ".md", ".py", ".yaml"}
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(directory.rglob("*"))
        if path.is_file() and path.suffix in suffixes
    ).lower()


class VariantTests(unittest.TestCase):
    def test_skill_names_match_their_directories(self) -> None:
        for variant in VARIANTS:
            with self.subTest(variant=variant):
                skill = (ROOT / variant / "SKILL.md").read_text(encoding="utf-8")
                metadata = (ROOT / variant / "agents" / "openai.yaml").read_text(encoding="utf-8")
                self.assertIn(f"name: {variant}\n", skill)
                self.assertIn(f"${variant}", metadata)

    def test_each_variant_validates_its_shipped_documents(self) -> None:
        for variant, features in VARIANTS.items():
            with self.subTest(variant=variant):
                directory = ROOT / variant
                validator = load_validator(variant)
                documents = [
                    directory / "assets" / "project-profile.template.json",
                    directory / "assets" / "run-contract.template.json",
                    directory / "assets" / "test-admission.template.json",
                ]
                if features["planr"]:
                    documents.append(directory / "examples" / "planr-project-profile.json")
                for document in documents:
                    self.assertEqual([], validator.validate_document(load_json(document)), document)

    def test_cli_works_in_every_standalone_directory(self) -> None:
        for variant in VARIANTS:
            with self.subTest(variant=variant):
                directory = ROOT / variant
                result = subprocess.run(
                    [
                        sys.executable,
                        str(directory / "scripts" / "validate_config.py"),
                        str(directory / "assets" / "project-profile.template.json"),
                        str(directory / "assets" / "run-contract.template.json"),
                    ],
                    cwd=directory,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)
                self.assertEqual(2, result.stdout.count("OK "))

    def test_profiles_expose_only_the_selected_agents(self) -> None:
        for variant, features in VARIANTS.items():
            with self.subTest(variant=variant):
                profile = load_json(ROOT / variant / "assets" / "project-profile.template.json")
                expected_roles = {"sol", "luna", "fable"} if features["fable"] else {"sol", "luna"}
                self.assertEqual(expected_roles, set(profile["roles"]))
                contract = load_json(ROOT / variant / "assets" / "run-contract.template.json")
                self.assertEqual(features["fable"], "fable_stage" in contract)

    def test_sentinel_is_off_by_default_silent_and_bounded(self) -> None:
        for variant in VARIANTS:
            with self.subTest(variant=variant):
                directory = ROOT / variant
                profile = load_json(directory / "assets" / "project-profile.template.json")
                contract = load_json(directory / "assets" / "run-contract.template.json")
                policy = profile["sentinel_policy"]
                self.assertEqual(3, profile["schema_version"])
                self.assertEqual(3, contract["schema_version"])
                self.assertNotIn("tests_allowed", contract)
                self.assertEqual("build", contract["phase"])
                self.assertEqual(0, contract["test_policy"]["permanent"]["max_new_invariants"])
                self.assertIn("silent-sentinel", profile["roles"]["luna"]["allowed_modes"])
                self.assertNotIn("heartbeat-sentinel", profile["roles"]["luna"]["allowed_modes"])
                self.assertEqual("off", policy["default_mode"])
                self.assertFalse(policy["healthy_notifications"])
                self.assertTrue(policy["deduplicate_events"])
                self.assertEqual("critical-only", policy["user_message_fallback"])
                self.assertLessEqual(policy["max_runtime_minutes"], profile["budgets"]["hard_stop_minutes"])
                self.assertTrue(policy["exit_after_stop"])
                self.assertTrue(policy["record_process"])
                self.assertIsNone(contract["luna_mode"])
                self.assertTrue(contract["cleanup"]["stop_recorded_sentinel_process"])
                self.assertTrue(contract["cleanup"]["sentinel_state_record"].endswith(".json"))
                self.assertTrue((directory / "scripts" / "silent_sentinel.py").is_file())
                self.assertFalse(any(
                    "heartbeat" in path.name.lower() or "watcher" in path.name.lower()
                    for path in (directory / "scripts").iterdir()
                ))

    def test_variants_ship_one_identical_sentinel_runtime(self) -> None:
        scripts = [
            (ROOT / variant / "scripts" / "silent_sentinel.py").read_bytes()
            for variant in VARIANTS
        ]
        self.assertTrue(all(script == scripts[0] for script in scripts[1:]))

    def test_variants_ship_one_identical_test_gate_runtime(self) -> None:
        scripts = [(ROOT / variant / "scripts" / "test_distillation_gate.py").read_bytes() for variant in VARIANTS]
        self.assertTrue(all(script == scripts[0] for script in scripts[1:]))
        references = [(ROOT / variant / "references" / "testing.md").read_bytes() for variant in VARIANTS]
        self.assertTrue(all(item == references[0] for item in references[1:]))

    def test_sentinel_packet_requires_the_exact_process_record_path(self) -> None:
        for variant in VARIANTS:
            with self.subTest(variant=variant):
                directory = ROOT / variant
                skill = (directory / "SKILL.md").read_text(encoding="utf-8")
                orchestration = (directory / "references" / "orchestration.md").read_text(
                    encoding="utf-8"
                )
                self.assertIn("cleanup.sentinel_process_record", skill)
                self.assertIn("repeat that exact path verbatim", skill)
                self.assertIn("report `MISSING` at that path", skill)
                self.assertIn("repeat this exact process-record path verbatim", orchestration)
                self.assertIn("Do not substitute, shorten, or infer a filename", orchestration)

    def test_optional_tool_names_are_absent_from_smaller_variants(self) -> None:
        sol_luna_text = variant_text(ROOT / "codex-herdr-sol-luna")
        self.assertNotIn("fable", sol_luna_text)
        self.assertNotIn("planr", sol_luna_text)

        fable_text = variant_text(ROOT / "codex-herdr-sol-luna-fable")
        self.assertNotIn("planr", fable_text)

    def test_safety_invariants_are_enforced_by_every_validator(self) -> None:
        for variant, features in VARIANTS.items():
            with self.subTest(variant=variant):
                directory = ROOT / variant
                validator = load_validator(variant)
                profile = load_json(directory / "assets" / "project-profile.template.json")
                profile["roles"]["sol"]["sole_writer"] = False
                profile["roles"]["luna"]["read_only"] = False
                profile["pane_policy"]["close_recorded_only"] = False
                profile["sentinel_policy"]["healthy_notifications"] = True
                profile["sentinel_policy"]["max_runtime_minutes"] = (
                    profile["budgets"]["hard_stop_minutes"] + 1
                )
                if features["fable"]:
                    profile["roles"]["fable"]["max_turns_per_hypothesis"] = 2
                errors = validator.validate_document(profile)
                self.assertTrue(any("sole_writer" in error for error in errors))
                self.assertTrue(any("luna.read_only" in error for error in errors))
                self.assertTrue(any("close_recorded_only" in error for error in errors))
                self.assertTrue(any("healthy_notifications" in error for error in errors))
                self.assertTrue(any("max_runtime_minutes" in error for error in errors))
                if features["fable"]:
                    self.assertTrue(any("max_turns_per_hypothesis" in error for error in errors))

                contract = load_json(directory / "assets" / "run-contract.template.json")
                contract["cleanup"]["stop_recorded_sentinel_process"] = False
                errors = validator.validate_document(contract)
                self.assertTrue(any("stop_recorded_sentinel_process" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
