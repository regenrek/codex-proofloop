# AGENTS.md

## Codex Herdr Sol-Luna contract

- Task source: `<issue, plan item, specification, or local path>`
- Project profile: `<project-relative path to project-profile.json>`
- Runtime owner: Sol owns intake, architecture, design-sensitive implementation, integration, and
  the final decision.
- Sole writer: Sol owns the coherent patch batch. No overlapping writers or child agents.
- Allowed paths: `<project-relative paths or globs>`
- Forbidden paths: `<credentials, generated state, user-owned areas, or other exclusions>`
- Validation command: `<one literal command>`
- Validation working directory: `<project-relative path>`
- Evidence directory: `<project-relative path>`
- Required evidence: `<baseline, diff, semantic validation result, artifacts, handoff>`
- Checkpoint budget: `<minutes>`
- Hard-stop budget: `<minutes>`
- Patch budget: `<maximum coherent batches>`
- Stop conditions: `<scope change, failed hypothesis, second writer, timeout, manual boundary, etc.>`
- Manual/human acceptance: `<owner, required yes/no, and explicit criteria>`
- Cleanup: reuse only suitable panes; record workflow-created pane IDs; close only recorded
  workflow-created panes; stop workflow sessions in reused panes; leave pre-existing panes open.

## Optional specialists

- Luna Max: disabled unless selected by the project profile as a read-only heartbeat sentinel, fresh
  bounded verifier, or fresh interactive operator. Luna may write only declared external evidence.
- Human: owns subjective, experiential, safety, or other declared manual acceptance.

## Execution

Before editing, validate the project profile and run contract with the installed
`codex-herdr-sol-luna`
validator. Preserve the existing workspace delta. Stop after the current atomic action when a stop
condition fires, then return an evidence-backed handoff. Never expose credentials or inspect their
contents.
