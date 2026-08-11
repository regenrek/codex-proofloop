#!/usr/bin/env python3
"""Validate Sol-Luna-Fable-Planr profiles and contracts without dependencies."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path, PurePosixPath
from typing import Any


PROFILE_KIND = "codex-herdr-sol-luna-fable-planr/project-profile"
CONTRACT_KIND = "codex-herdr-sol-luna-fable-planr/run-contract"
LUNA_MODES = {"silent-sentinel", "bounded-verifier", "interactive-operator"}
FABLE_STAGES = {"pre-implementation", "final-review"}


def _object(value: Any, path: str, errors: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append(f"{path}: expected object")
        return {}
    return value


def _keys(
    value: dict[str, Any],
    path: str,
    required: set[str],
    errors: list[str],
    optional: set[str] | None = None,
) -> None:
    optional = optional or set()
    for key in sorted(required - value.keys()):
        errors.append(f"{path}.{key}: missing required field")
    for key in sorted(value.keys() - required - optional):
        errors.append(f"{path}.{key}: unexpected field")


def _string(value: Any, path: str, errors: list[str]) -> str:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{path}: expected non-empty string")
        return ""
    return value


def _boolean(value: Any, path: str, errors: list[str]) -> bool | None:
    if not isinstance(value, bool):
        errors.append(f"{path}: expected boolean")
        return None
    return value


def _integer(value: Any, path: str, errors: list[str], minimum: int = 0) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        errors.append(f"{path}: expected integer >= {minimum}")
        return None
    return value


def _strings(value: Any, path: str, errors: list[str], allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or (not value and not allow_empty):
        qualifier = "" if allow_empty else " non-empty"
        errors.append(f"{path}: expected{qualifier} array of non-empty strings")
        return []
    result: list[str] = []
    for index, item in enumerate(value):
        text = _string(item, f"{path}[{index}]", errors)
        if text:
            result.append(text)
    if len(result) != len(set(result)):
        errors.append(f"{path}: duplicate values are not allowed")
    return result


def _relative(value: Any, path: str, errors: list[str]) -> str:
    text = _string(value, path, errors)
    if not text:
        return ""
    candidate = PurePosixPath(text)
    if candidate.is_absolute() or ".." in candidate.parts:
        errors.append(f"{path}: expected project-relative path without '..'")
    return text


def _relative_list(value: Any, path: str, errors: list[str]) -> list[str]:
    items = _strings(value, path, errors)
    for index, item in enumerate(items):
        _relative(item, f"{path}[{index}]", errors)
    return items


def _base(document: dict[str, Any], errors: list[str]) -> None:
    _integer(document.get("schema_version"), "$.schema_version", errors, 1)
    if document.get("schema_version") != 2:
        errors.append("$.schema_version: only version 2 is supported")
    _string(document.get("kind"), "$.kind", errors)


def _budgets(value: Any, path: str, errors: list[str]) -> None:
    item = _object(value, path, errors)
    _keys(item, path, {"checkpoint_minutes", "hard_stop_minutes", "max_patch_batches"}, errors)
    checkpoint = _integer(item.get("checkpoint_minutes"), f"{path}.checkpoint_minutes", errors, 1)
    hard_stop = _integer(item.get("hard_stop_minutes"), f"{path}.hard_stop_minutes", errors, 1)
    _integer(item.get("max_patch_batches"), f"{path}.max_patch_batches", errors, 1)
    if checkpoint is not None and hard_stop is not None and checkpoint >= hard_stop:
        errors.append(f"{path}: checkpoint_minutes must be less than hard_stop_minutes")


def _evidence(value: Any, path: str, errors: list[str]) -> None:
    item = _object(value, path, errors)
    _keys(item, path, {"directory", "required"}, errors)
    _relative(item.get("directory"), f"{path}.directory", errors)
    _strings(item.get("required"), f"{path}.required", errors)


def _manual_acceptance(value: Any, path: str, errors: list[str]) -> None:
    item = _object(value, path, errors)
    _keys(item, path, {"required", "owner", "criteria"}, errors)
    required = _boolean(item.get("required"), f"{path}.required", errors)
    _string(item.get("owner"), f"{path}.owner", errors)
    criteria = _strings(item.get("criteria"), f"{path}.criteria", errors, allow_empty=True)
    if required is True and not criteria:
        errors.append(f"{path}.criteria: required manual acceptance needs explicit criteria")


def _sentinel_policy(value: Any, hard_stop: Any, errors: list[str]) -> None:
    path = "$.sentinel_policy"
    item = _object(value, path, errors)
    required = {
        "default_mode", "healthy_notifications", "deduplicate_events", "user_message_fallback",
        "max_runtime_minutes", "exit_after_stop", "record_process",
    }
    _keys(item, path, required, errors)
    if item.get("default_mode") != "off":
        errors.append(f"{path}.default_mode: must be 'off'")
    if _boolean(item.get("healthy_notifications"), f"{path}.healthy_notifications", errors) is not False:
        errors.append(f"{path}.healthy_notifications: must be false")
    if _boolean(item.get("deduplicate_events"), f"{path}.deduplicate_events", errors) is not True:
        errors.append(f"{path}.deduplicate_events: must be true")
    if item.get("user_message_fallback") != "critical-only":
        errors.append(f"{path}.user_message_fallback: must be 'critical-only'")
    maximum = _integer(item.get("max_runtime_minutes"), f"{path}.max_runtime_minutes", errors, 1)
    if maximum is not None and isinstance(hard_stop, int) and not isinstance(hard_stop, bool) and maximum > hard_stop:
        errors.append(f"{path}.max_runtime_minutes: must not exceed $.budgets.hard_stop_minutes")
    for field in ("exit_after_stop", "record_process"):
        if _boolean(item.get(field), f"{path}.{field}", errors) is not True:
            errors.append(f"{path}.{field}: must be true")


def _profile(document: dict[str, Any], errors: list[str]) -> None:
    required = {
        "schema_version", "kind", "project", "roles", "paths", "validation", "evidence",
        "budgets", "stop_conditions", "manual_acceptance", "pane_policy", "sentinel_policy",
    }
    _keys(document, "$", required, errors)
    _base(document, errors)
    if document.get("kind") != PROFILE_KIND:
        errors.append(f"$.kind: expected {PROFILE_KIND!r}")

    project = _object(document.get("project"), "$.project", errors)
    _keys(project, "$.project", {"name", "root", "task_source"}, errors)
    _string(project.get("name"), "$.project.name", errors)
    _relative(project.get("root"), "$.project.root", errors)
    _string(project.get("task_source"), "$.project.task_source", errors)

    roles = _object(document.get("roles"), "$.roles", errors)
    _keys(roles, "$.roles", {"sol", "luna", "fable"}, errors)
    sol = _object(roles.get("sol"), "$.roles.sol", errors)
    _keys(sol, "$.roles.sol", {"owns", "sole_writer"}, errors)
    owns = set(_strings(sol.get("owns"), "$.roles.sol.owns", errors))
    required_ownership = {"intake", "architecture", "design-sensitive implementation", "integration", "final decision"}
    if not required_ownership.issubset(owns):
        errors.append("$.roles.sol.owns: must include all canonical Sol responsibilities")
    if _boolean(sol.get("sole_writer"), "$.roles.sol.sole_writer", errors) is False:
        errors.append("$.roles.sol.sole_writer: must be true")

    luna = _object(roles.get("luna"), "$.roles.luna", errors)
    _keys(luna, "$.roles.luna", {"enabled", "read_only", "allowed_modes"}, errors)
    _boolean(luna.get("enabled"), "$.roles.luna.enabled", errors)
    if _boolean(luna.get("read_only"), "$.roles.luna.read_only", errors) is False:
        errors.append("$.roles.luna.read_only: must be true")
    luna_modes = set(_strings(luna.get("allowed_modes"), "$.roles.luna.allowed_modes", errors, allow_empty=True))
    for mode in sorted(luna_modes - LUNA_MODES):
        errors.append(f"$.roles.luna.allowed_modes: unsupported mode {mode!r}")

    fable = _object(roles.get("fable"), "$.roles.fable", errors)
    _keys(fable, "$.roles.fable", {"enabled", "max_turns_per_hypothesis", "allowed_stages", "writer"}, errors)
    _boolean(fable.get("enabled"), "$.roles.fable.enabled", errors)
    turns = _integer(fable.get("max_turns_per_hypothesis"), "$.roles.fable.max_turns_per_hypothesis", errors)
    if turns is not None and turns > 1:
        errors.append("$.roles.fable.max_turns_per_hypothesis: must be at most 1")
    fable_stages = set(_strings(fable.get("allowed_stages"), "$.roles.fable.allowed_stages", errors, allow_empty=True))
    for stage in sorted(fable_stages - FABLE_STAGES):
        errors.append(f"$.roles.fable.allowed_stages: unsupported stage {stage!r}")
    if _boolean(fable.get("writer"), "$.roles.fable.writer", errors) is True:
        errors.append("$.roles.fable.writer: must be false")

    paths = _object(document.get("paths"), "$.paths", errors)
    _keys(paths, "$.paths", {"allowed", "forbidden"}, errors)
    _relative_list(paths.get("allowed"), "$.paths.allowed", errors)
    _relative_list(paths.get("forbidden"), "$.paths.forbidden", errors)

    validation = _object(document.get("validation"), "$.validation", errors)
    _keys(validation, "$.validation", {"cwd", "command", "timeout_seconds"}, errors)
    _relative(validation.get("cwd"), "$.validation.cwd", errors)
    _string(validation.get("command"), "$.validation.command", errors)
    _integer(validation.get("timeout_seconds"), "$.validation.timeout_seconds", errors, 1)

    _evidence(document.get("evidence"), "$.evidence", errors)
    _budgets(document.get("budgets"), "$.budgets", errors)
    budgets = document.get("budgets")
    hard_stop = budgets.get("hard_stop_minutes") if isinstance(budgets, dict) else None
    _sentinel_policy(document.get("sentinel_policy"), hard_stop, errors)
    _strings(document.get("stop_conditions"), "$.stop_conditions", errors)
    _manual_acceptance(document.get("manual_acceptance"), "$.manual_acceptance", errors)

    panes = _object(document.get("pane_policy"), "$.pane_policy", errors)
    _keys(panes, "$.pane_policy", {"reuse_suitable_existing", "record_created", "close_recorded_only", "max_completed_workflow_panes"}, errors)
    _boolean(panes.get("reuse_suitable_existing"), "$.pane_policy.reuse_suitable_existing", errors)
    if _boolean(panes.get("record_created"), "$.pane_policy.record_created", errors) is False:
        errors.append("$.pane_policy.record_created: must be true")
    if _boolean(panes.get("close_recorded_only"), "$.pane_policy.close_recorded_only", errors) is False:
        errors.append("$.pane_policy.close_recorded_only: must be true")
    completed = _integer(panes.get("max_completed_workflow_panes"), "$.pane_policy.max_completed_workflow_panes", errors)
    if completed is not None and completed != 0:
        errors.append("$.pane_policy.max_completed_workflow_panes: must be 0")


def _contract(document: dict[str, Any], errors: list[str]) -> None:
    required = {
        "schema_version", "kind", "task", "project_profile", "phase", "writer", "allowed_paths",
        "tests_allowed", "luna_mode", "fable_stage", "validation", "evidence", "budgets",
        "stop_conditions", "manual_acceptance", "cleanup",
    }
    _keys(document, "$", required, errors)
    _base(document, errors)
    if document.get("kind") != CONTRACT_KIND:
        errors.append(f"$.kind: expected {CONTRACT_KIND!r}")

    task = _object(document.get("task"), "$.task", errors)
    _keys(task, "$.task", {"id", "source", "goal", "hypothesis"}, errors)
    for field in ("id", "source", "goal", "hypothesis"):
        _string(task.get(field), f"$.task.{field}", errors)
    _relative(document.get("project_profile"), "$.project_profile", errors)
    if document.get("phase") not in {"manual", "accepted-verification"}:
        errors.append("$.phase: expected 'manual' or 'accepted-verification'")
    if document.get("writer") != "sol":
        errors.append("$.writer: expected 'sol'")
    _relative_list(document.get("allowed_paths"), "$.allowed_paths", errors)
    _boolean(document.get("tests_allowed"), "$.tests_allowed", errors)
    if document.get("luna_mode") is not None and document.get("luna_mode") not in LUNA_MODES:
        errors.append("$.luna_mode: expected null or a supported Luna mode")
    if document.get("fable_stage") is not None and document.get("fable_stage") not in FABLE_STAGES:
        errors.append("$.fable_stage: expected null or a supported Fable stage")

    validation = _object(document.get("validation"), "$.validation", errors)
    _keys(validation, "$.validation", {"cwd", "command", "timeout_seconds", "pass_criteria"}, errors)
    _relative(validation.get("cwd"), "$.validation.cwd", errors)
    _string(validation.get("command"), "$.validation.command", errors)
    _integer(validation.get("timeout_seconds"), "$.validation.timeout_seconds", errors, 1)
    _strings(validation.get("pass_criteria"), "$.validation.pass_criteria", errors)

    _evidence(document.get("evidence"), "$.evidence", errors)
    _budgets(document.get("budgets"), "$.budgets", errors)
    _strings(document.get("stop_conditions"), "$.stop_conditions", errors)
    _manual_acceptance(document.get("manual_acceptance"), "$.manual_acceptance", errors)

    cleanup = _object(document.get("cleanup"), "$.cleanup", errors)
    _keys(cleanup, "$.cleanup", {"ownership_record", "sentinel_process_record", "stop_recorded_sentinel_process", "close_recorded_workflow_panes", "leave_preexisting_panes_open", "retire_sentinel_state"}, errors)
    _relative(cleanup.get("ownership_record"), "$.cleanup.ownership_record", errors)
    _relative(cleanup.get("sentinel_process_record"), "$.cleanup.sentinel_process_record", errors)
    for field in ("stop_recorded_sentinel_process", "close_recorded_workflow_panes", "leave_preexisting_panes_open", "retire_sentinel_state"):
        if _boolean(cleanup.get(field), f"$.cleanup.{field}", errors) is False:
            errors.append(f"$.cleanup.{field}: must be true")


def validate_document(document: Any) -> list[str]:
    errors: list[str] = []
    root = _object(document, "$", errors)
    kind = root.get("kind")
    if kind == PROFILE_KIND:
        _profile(root, errors)
    elif kind == CONTRACT_KIND:
        _contract(root, errors)
    else:
        _base(root, errors)
        errors.append(f"$.kind: expected {PROFILE_KIND!r} or {CONTRACT_KIND!r}")
    return errors


def validate_file(path: Path) -> list[str]:
    try:
        with path.open(encoding="utf-8") as handle:
            document = json.load(handle)
    except OSError as error:
        return [f"cannot read file: {error}"]
    except json.JSONDecodeError as error:
        return [f"invalid JSON at line {error.lineno}, column {error.colno}: {error.msg}"]
    return validate_document(document)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", type=Path, help="JSON profile or run contract")
    args = parser.parse_args(argv)
    failed = False
    for path in args.files:
        errors = validate_file(path)
        if errors:
            failed = True
            print(f"FAIL {path}")
            for error in errors:
                print(f"  - {error}")
        else:
            print(f"OK {path}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
