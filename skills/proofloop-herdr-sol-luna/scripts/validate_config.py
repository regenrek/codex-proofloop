#!/usr/bin/env python3
"""Validate schema-v3 Sol-Luna policy documents without dependencies."""

from __future__ import annotations

import argparse
import fnmatch
import json
import sys
from pathlib import Path, PurePosixPath
from typing import Any

PROFILE_KIND = "proofloop-herdr-sol-luna/project-profile"
CONTRACT_KIND = "proofloop-herdr-sol-luna/run-contract"
ADMISSION_KIND = "proofloop-herdr-sol-luna/test-admission"
LUNA_MODES = {"silent-sentinel", "bounded-verifier", "interactive-operator"}
MAX_HARDEN = {"max_new_invariants": 3, "max_changed_test_files": 3, "max_added_test_lines": 240}
_VARIANT_PARTS = PROFILE_KIND.split("/", 1)[0].split("-")
EXTRA_REVIEWER = _VARIANT_PARTS[4] if len(_VARIANT_PARTS) > 4 else None


def _obj(value: Any, path: str, errors: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append(f"{path}: expected object")
        return {}
    return value


def _keys(value: dict[str, Any], path: str, required: set[str], errors: list[str], optional: set[str] | None = None) -> None:
    for key in sorted(required - value.keys()):
        errors.append(f"{path}.{key}: missing required field")
    for key in sorted(value.keys() - required - (optional or set())):
        errors.append(f"{path}.{key}: unexpected field")


def _str(value: Any, path: str, errors: list[str], nullable: bool = False) -> str | None:
    if nullable and value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{path}: expected {'null or ' if nullable else ''}non-empty string")
        return None
    return value


def _bool(value: Any, path: str, errors: list[str]) -> bool | None:
    if not isinstance(value, bool):
        errors.append(f"{path}: expected boolean")
        return None
    return value


def _int(value: Any, path: str, errors: list[str], minimum: int = 0) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        errors.append(f"{path}: expected integer >= {minimum}")
        return None
    return value


def _strings(value: Any, path: str, errors: list[str], allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or (not allow_empty and not value):
        errors.append(f"{path}: expected {'possibly empty' if allow_empty else 'non-empty'} array of non-empty strings")
        return []
    result = []
    for index, item in enumerate(value):
        text = _str(item, f"{path}[{index}]", errors)
        if text is not None:
            result.append(text)
    if len(result) != len(set(result)):
        errors.append(f"{path}: duplicate values are not allowed")
    return result


def normalize_path(value: str) -> str:
    normalized = value.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.rstrip("/")


def _relative(value: Any, path: str, errors: list[str]) -> str:
    text = _str(value, path, errors)
    if text is None:
        return ""
    candidate = PurePosixPath(text.replace("\\", "/"))
    if candidate.is_absolute() or ".." in candidate.parts:
        errors.append(f"{path}: expected project-relative path without '..'")
    return normalize_path(text)


def _rel_list(value: Any, path: str, errors: list[str]) -> list[str]:
    values = _strings(value, path, errors)
    return [_relative(item, f"{path}[{index}]", errors) for index, item in enumerate(values)]


def path_matches(path: str, patterns: list[str]) -> bool:
    target = normalize_path(path).casefold()
    for raw in patterns:
        pattern = normalize_path(raw).casefold()
        candidates = [pattern]
        if pattern.startswith("**/"):
            candidates.append(pattern[3:])
        if any(fnmatch.fnmatchcase(target, candidate) for candidate in candidates):
            return True
        if pattern.endswith("/**") and target.startswith(pattern[:-3].rstrip("/") + "/"):
            return True
    return False


def path_inside(path: str, directory: str) -> bool:
    item, parent = normalize_path(path), normalize_path(directory)
    return item == parent or item.startswith(parent + "/")


def _base(document: dict[str, Any], errors: list[str]) -> None:
    version = document.get("schema_version")
    if version == 2:
        errors.append("$.schema_version: schema 2 must migrate to schema 3; replace tests_allowed with test_policy and phases manual/accepted-verification with build/harden")
    elif version != 3:
        errors.append("$.schema_version: expected version 3")
    _str(document.get("kind"), "$.kind", errors)


def _budgets(value: Any, path: str, errors: list[str]) -> None:
    item = _obj(value, path, errors)
    _keys(item, path, {"checkpoint_minutes", "hard_stop_minutes", "max_patch_batches"}, errors)
    checkpoint = _int(item.get("checkpoint_minutes"), f"{path}.checkpoint_minutes", errors, 1)
    hard_stop = _int(item.get("hard_stop_minutes"), f"{path}.hard_stop_minutes", errors, 1)
    _int(item.get("max_patch_batches"), f"{path}.max_patch_batches", errors, 1)
    if checkpoint is not None and hard_stop is not None and checkpoint >= hard_stop:
        errors.append(f"{path}: checkpoint_minutes must be less than hard_stop_minutes")


def _evidence(value: Any, path: str, errors: list[str]) -> None:
    item = _obj(value, path, errors)
    _keys(item, path, {"directory", "required"}, errors)
    _relative(item.get("directory"), f"{path}.directory", errors)
    _strings(item.get("required"), f"{path}.required", errors)


def _manual(value: Any, path: str, errors: list[str]) -> None:
    item = _obj(value, path, errors)
    _keys(item, path, {"required", "owner", "criteria"}, errors)
    required = _bool(item.get("required"), f"{path}.required", errors)
    _str(item.get("owner"), f"{path}.owner", errors)
    criteria = _strings(item.get("criteria"), f"{path}.criteria", errors, True)
    if required and not criteria:
        errors.append(f"{path}.criteria: required manual acceptance needs explicit criteria")


def _permanent(value: Any, path: str, errors: list[str]) -> dict[str, int]:
    item = _obj(value, path, errors)
    _keys(item, path, set(MAX_HARDEN), errors)
    result: dict[str, int] = {}
    for field in MAX_HARDEN:
        parsed = _int(item.get(field), f"{path}.{field}", errors)
        if parsed is not None:
            result[field] = parsed
    return result


def _testing(value: Any, errors: list[str]) -> None:
    path = "$.testing"
    item = _obj(value, path, errors)
    _keys(item, path, {"strategy", "tracked_test_globs", "build", "harden"}, errors)
    if item.get("strategy") != "distill":
        errors.append(f"{path}.strategy: expected 'distill'")
    globs = _strings(item.get("tracked_test_globs"), f"{path}.tracked_test_globs", errors)
    for index, pattern in enumerate(globs):
        candidate = PurePosixPath(pattern.replace("\\", "/"))
        if candidate.is_absolute() or ".." in candidate.parts:
            errors.append(f"{path}.tracked_test_globs[{index}]: expected relative glob without '..'")
    build = _obj(item.get("build"), f"{path}.build", errors)
    _keys(build, f"{path}.build", {"permanent_test_edits", "full_suite"}, errors)
    if build.get("permanent_test_edits") != "deny":
        errors.append(f"{path}.build.permanent_test_edits: must be 'deny'")
    if build.get("full_suite") != "deny":
        errors.append(f"{path}.build.full_suite: must be 'deny'")
    harden = _obj(item.get("harden"), f"{path}.harden", errors)
    _keys(harden, f"{path}.harden", {"permanent_test_edits", "max_new_invariants", "max_changed_test_files", "max_added_test_lines", "full_suite"}, errors)
    if harden.get("permanent_test_edits") != "admission-required":
        errors.append(f"{path}.harden.permanent_test_edits: must be 'admission-required'")
    if harden.get("full_suite") != "ci-or-explicit":
        errors.append(f"{path}.harden.full_suite: must be 'ci-or-explicit'")
    for field, cap in MAX_HARDEN.items():
        parsed = _int(harden.get(field), f"{path}.harden.{field}", errors)
        if parsed is not None and parsed > cap:
            errors.append(f"{path}.harden.{field}: must not exceed absolute safety cap {cap}")


def _sentinel(value: Any, hard_stop: Any, errors: list[str]) -> None:
    path = "$.sentinel_policy"
    item = _obj(value, path, errors)
    required = {"default_mode", "healthy_notifications", "deduplicate_events", "user_message_fallback", "max_runtime_minutes", "exit_after_stop", "record_process"}
    _keys(item, path, required, errors)
    expected = {"default_mode": "off", "healthy_notifications": False, "deduplicate_events": True, "user_message_fallback": "critical-only", "exit_after_stop": True, "record_process": True}
    for field, wanted in expected.items():
        if item.get(field) != wanted:
            errors.append(f"{path}.{field}: must be {wanted!r}")
    maximum = _int(item.get("max_runtime_minutes"), f"{path}.max_runtime_minutes", errors, 1)
    if maximum is not None and isinstance(hard_stop, int) and maximum > hard_stop:
        errors.append(f"{path}.max_runtime_minutes: must not exceed $.budgets.hard_stop_minutes")


def _profile(document: dict[str, Any], errors: list[str]) -> None:
    required = {"schema_version", "kind", "project", "roles", "paths", "validation", "testing", "evidence", "budgets", "stop_conditions", "manual_acceptance", "pane_policy", "sentinel_policy"}
    _keys(document, "$", required, errors)
    _base(document, errors)
    if document.get("kind") != PROFILE_KIND:
        errors.append(f"$.kind: expected {PROFILE_KIND!r}")
    project = _obj(document.get("project"), "$.project", errors)
    _keys(project, "$.project", {"name", "root", "task_source"}, errors)
    _str(project.get("name"), "$.project.name", errors); _relative(project.get("root"), "$.project.root", errors); _str(project.get("task_source"), "$.project.task_source", errors)
    roles = _obj(document.get("roles"), "$.roles", errors)
    role_keys = {"sol", "luna"} | ({EXTRA_REVIEWER} if EXTRA_REVIEWER else set())
    _keys(roles, "$.roles", role_keys, errors)
    sol = _obj(roles.get("sol"), "$.roles.sol", errors); _keys(sol, "$.roles.sol", {"owns", "sole_writer"}, errors)
    owns = set(_strings(sol.get("owns"), "$.roles.sol.owns", errors))
    if not {"intake", "architecture", "design-sensitive implementation", "integration", "final decision"}.issubset(owns):
        errors.append("$.roles.sol.owns: must include all canonical Sol responsibilities")
    if _bool(sol.get("sole_writer"), "$.roles.sol.sole_writer", errors) is not True:
        errors.append("$.roles.sol.sole_writer: must be true")
    luna = _obj(roles.get("luna"), "$.roles.luna", errors); _keys(luna, "$.roles.luna", {"enabled", "read_only", "allowed_modes"}, errors)
    _bool(luna.get("enabled"), "$.roles.luna.enabled", errors)
    if _bool(luna.get("read_only"), "$.roles.luna.read_only", errors) is not True:
        errors.append("$.roles.luna.read_only: must be true")
    modes = set(_strings(luna.get("allowed_modes"), "$.roles.luna.allowed_modes", errors, True))
    for mode in sorted(modes - LUNA_MODES): errors.append(f"$.roles.luna.allowed_modes: unsupported mode {mode!r}")
    if EXTRA_REVIEWER:
        review_path = f"$.roles.{EXTRA_REVIEWER}"
        reviewer = _obj(roles.get(EXTRA_REVIEWER), review_path, errors)
        _keys(reviewer, review_path, {"enabled", "max_turns_per_hypothesis", "allowed_stages", "writer"}, errors)
        _bool(reviewer.get("enabled"), f"{review_path}.enabled", errors)
        turns = _int(reviewer.get("max_turns_per_hypothesis"), f"{review_path}.max_turns_per_hypothesis", errors)
        if turns is not None and turns > 1: errors.append(f"{review_path}.max_turns_per_hypothesis: must be at most 1")
        stages = set(_strings(reviewer.get("allowed_stages"), f"{review_path}.allowed_stages", errors, True))
        for stage in sorted(stages - {"pre-implementation", "final-review"}): errors.append(f"{review_path}.allowed_stages: unsupported stage {stage!r}")
        if _bool(reviewer.get("writer"), f"{review_path}.writer", errors) is not False: errors.append(f"{review_path}.writer: must be false")
    paths = _obj(document.get("paths"), "$.paths", errors); _keys(paths, "$.paths", {"allowed", "forbidden"}, errors)
    _rel_list(paths.get("allowed"), "$.paths.allowed", errors); _rel_list(paths.get("forbidden"), "$.paths.forbidden", errors)
    validation = _obj(document.get("validation"), "$.validation", errors); _keys(validation, "$.validation", {"cwd", "command", "full_suite_command", "timeout_seconds"}, errors)
    _relative(validation.get("cwd"), "$.validation.cwd", errors); focused = _str(validation.get("command"), "$.validation.command", errors); full_suite = _str(validation.get("full_suite_command"), "$.validation.full_suite_command", errors, True); _int(validation.get("timeout_seconds"), "$.validation.timeout_seconds", errors, 1)
    if focused is not None and full_suite == focused: errors.append("$.validation.full_suite_command: must differ from the focused command")
    _testing(document.get("testing"), errors); _evidence(document.get("evidence"), "$.evidence", errors); _budgets(document.get("budgets"), "$.budgets", errors)
    budgets = document.get("budgets") if isinstance(document.get("budgets"), dict) else {}
    _sentinel(document.get("sentinel_policy"), budgets.get("hard_stop_minutes"), errors)
    _strings(document.get("stop_conditions"), "$.stop_conditions", errors); _manual(document.get("manual_acceptance"), "$.manual_acceptance", errors)
    panes = _obj(document.get("pane_policy"), "$.pane_policy", errors); _keys(panes, "$.pane_policy", {"reuse_suitable_existing", "record_created", "close_recorded_only", "max_completed_workflow_panes"}, errors)
    _bool(panes.get("reuse_suitable_existing"), "$.pane_policy.reuse_suitable_existing", errors)
    for field in ("record_created", "close_recorded_only"):
        if _bool(panes.get(field), f"$.pane_policy.{field}", errors) is not True: errors.append(f"$.pane_policy.{field}: must be true")
    if _int(panes.get("max_completed_workflow_panes"), "$.pane_policy.max_completed_workflow_panes", errors) not in (None, 0): errors.append("$.pane_policy.max_completed_workflow_panes: must be 0")


def _test_policy(value: Any, phase: Any, evidence_dir: str, errors: list[str]) -> None:
    path = "$.test_policy"; item = _obj(value, path, errors)
    _keys(item, path, {"baseline_record", "result_record", "ephemeral_directory", "admission_record", "permanent", "full_suite"}, errors)
    paths = [_relative(item.get(field), f"{path}.{field}", errors) for field in ("baseline_record", "result_record", "ephemeral_directory", "admission_record")]
    if len(paths) != len(set(paths)): errors.append(f"{path}: policy paths must be distinct")
    for index, field in enumerate(("baseline_record", "result_record", "ephemeral_directory", "admission_record")):
        if paths[index] and evidence_dir and not path_inside(paths[index], evidence_dir): errors.append(f"{path}.{field}: must resolve inside $.evidence.directory")
    permanent = _permanent(item.get("permanent"), f"{path}.permanent", errors)
    suite = _obj(item.get("full_suite"), f"{path}.full_suite", errors); _keys(suite, f"{path}.full_suite", {"allowed", "reason"}, errors)
    allowed = _bool(suite.get("allowed"), f"{path}.full_suite.allowed", errors); reason = _str(suite.get("reason"), f"{path}.full_suite.reason", errors, True)
    if phase == "build":
        if any(permanent.get(field, -1) != 0 for field in MAX_HARDEN): errors.append(f"{path}.permanent: BUILD requires all permanent budgets to equal zero")
        if allowed is not False: errors.append(f"{path}.full_suite.allowed: BUILD requires false")
        if reason is not None: errors.append(f"{path}.full_suite.reason: BUILD requires null")
    if allowed and phase != "harden": errors.append(f"{path}.full_suite.allowed: only HARDEN may allow a full suite")
    if allowed and not reason: errors.append(f"{path}.full_suite.reason: explicit full-suite use requires a concrete reason")


def _contract(document: dict[str, Any], errors: list[str]) -> None:
    required = {"schema_version", "kind", "task", "project_profile", "phase", "writer", "allowed_paths", "test_policy", "luna_mode", "validation", "evidence", "budgets", "stop_conditions", "manual_acceptance", "cleanup"}
    if EXTRA_REVIEWER: required.add(f"{EXTRA_REVIEWER}_stage")
    _keys(document, "$", required, errors); _base(document, errors)
    if document.get("kind") != CONTRACT_KIND: errors.append(f"$.kind: expected {CONTRACT_KIND!r}")
    task = _obj(document.get("task"), "$.task", errors); _keys(task, "$.task", {"id", "source", "goal", "hypothesis"}, errors)
    for field in ("id", "source", "goal", "hypothesis"): _str(task.get(field), f"$.task.{field}", errors)
    _relative(document.get("project_profile"), "$.project_profile", errors)
    phase = document.get("phase")
    if phase not in {"build", "harden"}: errors.append("$.phase: expected 'build' or 'harden'")
    if document.get("writer") != "sol": errors.append("$.writer: expected 'sol'")
    _rel_list(document.get("allowed_paths"), "$.allowed_paths", errors)
    if document.get("luna_mode") is not None and document.get("luna_mode") not in LUNA_MODES: errors.append("$.luna_mode: expected null or a supported Luna mode")
    if EXTRA_REVIEWER:
        stage = document.get(f"{EXTRA_REVIEWER}_stage")
        if stage is not None and stage not in {"pre-implementation", "final-review"}: errors.append(f"$.{EXTRA_REVIEWER}_stage: expected null or a supported review stage")
    validation = _obj(document.get("validation"), "$.validation", errors); _keys(validation, "$.validation", {"cwd", "command", "timeout_seconds", "pass_criteria"}, errors)
    _relative(validation.get("cwd"), "$.validation.cwd", errors); _str(validation.get("command"), "$.validation.command", errors); _int(validation.get("timeout_seconds"), "$.validation.timeout_seconds", errors, 1); _strings(validation.get("pass_criteria"), "$.validation.pass_criteria", errors)
    _evidence(document.get("evidence"), "$.evidence", errors); evidence = document.get("evidence") if isinstance(document.get("evidence"), dict) else {}
    _test_policy(document.get("test_policy"), phase, normalize_path(str(evidence.get("directory", ""))), errors)
    _budgets(document.get("budgets"), "$.budgets", errors); _strings(document.get("stop_conditions"), "$.stop_conditions", errors); _manual(document.get("manual_acceptance"), "$.manual_acceptance", errors)
    cleanup = _obj(document.get("cleanup"), "$.cleanup", errors); required_cleanup = {"ownership_record", "sentinel_process_record", "sentinel_state_record", "stop_recorded_sentinel_process", "close_recorded_workflow_panes", "leave_preexisting_panes_open", "retire_sentinel_state"}; _keys(cleanup, "$.cleanup", required_cleanup, errors)
    for field in ("ownership_record", "sentinel_process_record", "sentinel_state_record"): _relative(cleanup.get(field), f"$.cleanup.{field}", errors)
    for field in ("stop_recorded_sentinel_process", "close_recorded_workflow_panes", "leave_preexisting_panes_open", "retire_sentinel_state"):
        if _bool(cleanup.get(field), f"$.cleanup.{field}", errors) is not True: errors.append(f"$.cleanup.{field}: must be true")


def _verdict(value: Any, path: str, expected: str, evidence_dir: str, errors: list[str]) -> None:
    item = _obj(value, path, errors); _keys(item, path, {"verdict", "evidence"}, errors)
    if item.get("verdict") != expected: errors.append(f"{path}.verdict: expected {expected!r}")
    evidence = _relative(item.get("evidence"), f"{path}.evidence", errors)
    if evidence and evidence_dir and not path_inside(evidence, evidence_dir): errors.append(f"{path}.evidence: must resolve inside contract evidence directory")


def _admission(document: dict[str, Any], errors: list[str], evidence_dir: str = "") -> None:
    _keys(document, "$", {"schema_version", "kind", "task_id", "admissions"}, errors); _base(document, errors)
    if document.get("kind") != ADMISSION_KIND: errors.append(f"$.kind: expected {ADMISSION_KIND!r}")
    _str(document.get("task_id"), "$.task_id", errors)
    admissions = document.get("admissions")
    if not isinstance(admissions, list): errors.append("$.admissions: expected array"); return
    ids: list[str] = []
    for index, raw in enumerate(admissions):
        path = f"$.admissions[{index}]"; item = _obj(raw, path, errors)
        _keys(item, path, {"invariant_id", "disposition", "test_paths", "observable_contract", "stable_boundary", "counterfactual", "final", "distinct_signal", "deterministic"}, errors)
        invariant = _str(item.get("invariant_id"), f"{path}.invariant_id", errors)
        if invariant: ids.append(invariant)
        if item.get("disposition") not in {"new-test", "merge-existing"}: errors.append(f"{path}.disposition: expected 'new-test' or 'merge-existing'")
        _rel_list(item.get("test_paths"), f"{path}.test_paths", errors)
        for field in ("observable_contract", "stable_boundary", "distinct_signal"): _str(item.get(field), f"{path}.{field}", errors)
        counter = _obj(item.get("counterfactual"), f"{path}.counterfactual", errors); _keys(counter, f"{path}.counterfactual", {"kind", "description", "existing_suite", "candidate"}, errors)
        if counter.get("kind") not in {"baseline", "risk-mutant"}: errors.append(f"{path}.counterfactual.kind: expected 'baseline' or 'risk-mutant'")
        _str(counter.get("description"), f"{path}.counterfactual.description", errors)
        _verdict(counter.get("existing_suite"), f"{path}.counterfactual.existing_suite", "pass", evidence_dir, errors); _verdict(counter.get("candidate"), f"{path}.counterfactual.candidate", "fail", evidence_dir, errors); _verdict(item.get("final"), f"{path}.final", "pass", evidence_dir, errors)
        if _bool(item.get("deterministic"), f"{path}.deterministic", errors) is not True: errors.append(f"{path}.deterministic: must be true")
    if len(ids) != len(set(ids)): errors.append("$.admissions: duplicate invariant_id values are not allowed")


def validate_document(document: Any) -> list[str]:
    errors: list[str] = []; root = _obj(document, "$", errors); kind = root.get("kind")
    if kind == PROFILE_KIND: _profile(root, errors)
    elif kind == CONTRACT_KIND: _contract(root, errors)
    elif kind == ADMISSION_KIND: _admission(root, errors)
    else: _base(root, errors); errors.append(f"$.kind: expected {PROFILE_KIND!r}, {CONTRACT_KIND!r}, or {ADMISSION_KIND!r}")
    return errors


def validate_bundle(profile: Any, contract: Any, admission: Any = None) -> list[str]:
    errors = validate_document(profile) + validate_document(contract)
    if errors: return errors
    harden = profile["testing"]["harden"]; permanent = contract["test_policy"]["permanent"]
    if contract["phase"] == "harden":
        for field in MAX_HARDEN:
            if permanent[field] > harden[field]: errors.append(f"$.test_policy.permanent.{field}: exceeds project harden cap {harden[field]}")
    suite = contract["test_policy"]["full_suite"]
    if suite["allowed"] and profile["validation"]["full_suite_command"] is None: errors.append("$.test_policy.full_suite.allowed: profile has no configured full_suite_command")
    if contract["validation"]["command"] != profile["validation"]["command"]: errors.append("$.validation.command: must equal the profile focused validation command")
    if contract["validation"]["cwd"] != profile["validation"]["cwd"]: errors.append("$.validation.cwd: must equal the profile validation cwd")
    for field in ("baseline_record", "result_record", "ephemeral_directory", "admission_record"):
        policy_path = contract["test_policy"][field]
        if path_matches(policy_path, profile["testing"]["tracked_test_globs"]): errors.append(f"$.test_policy.{field}: must not overlap permanent tracked test globs")
    if admission is not None:
        admission_errors: list[str] = []; _admission(_obj(admission, "$", admission_errors), admission_errors, contract["evidence"]["directory"]); errors.extend(admission_errors)
        if not admission_errors:
            if admission["task_id"] != contract["task"]["id"]: errors.append("$.task_id: must equal run contract task.id")
            paths: set[str] = set()
            for index, item in enumerate(admission["admissions"]):
                for path in item["test_paths"]:
                    normalized = normalize_path(path); paths.add(normalized)
                    if not path_matches(normalized, profile["testing"]["tracked_test_globs"]): errors.append(f"$.admissions[{index}].test_paths: {path!r} is not a tracked test path")
                    if not any(path_matches(normalized, [pattern]) for pattern in contract["allowed_paths"]): errors.append(f"$.admissions[{index}].test_paths: {path!r} is outside contract allowed paths")
            if len(admission["admissions"]) > permanent["max_new_invariants"]: errors.append("$.admissions: exceeds contract invariant budget")
            if len(paths) > permanent["max_changed_test_files"]: errors.append("$.admissions: exceeds contract changed-file budget")
    return errors


def validate_file(path: Path) -> tuple[Any | None, list[str]]:
    try: document = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error: return None, [f"cannot read file: {error}"]
    except json.JSONDecodeError as error: return None, [f"invalid JSON at line {error.lineno}, column {error.colno}: {error.msg}"]
    return document, validate_document(document)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("files", nargs="+", type=Path); args = parser.parse_args(argv)
    failed = False; documents: list[Any] = []
    for path in args.files:
        document, errors = validate_file(path); documents.append(document)
        if errors:
            failed = True; print(f"FAIL {path}")
            for error in errors: print(f"  - {error}")
        else: print(f"OK {path}")
    profile = next((item for item in documents if isinstance(item, dict) and item.get("kind") == PROFILE_KIND), None)
    contract = next((item for item in documents if isinstance(item, dict) and item.get("kind") == CONTRACT_KIND), None)
    admission = next((item for item in documents if isinstance(item, dict) and item.get("kind") == ADMISSION_KIND), None)
    if profile is not None and contract is not None:
        bundle_errors = validate_bundle(profile, contract, admission)
        individual = validate_document(profile) + validate_document(contract) + (validate_document(admission) if admission is not None else [])
        novel = [error for error in bundle_errors if error not in individual]
        if novel:
            failed = True; print("FAIL bundle")
            for error in novel: print(f"  - {error}")
    return 1 if failed else 0


if __name__ == "__main__": raise SystemExit(main())
