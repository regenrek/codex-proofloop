---
name: proofloop
description: Verify coding changes with executed behavioral checks, repeatable artifacts and an independent native GPT-6 Luna checker at max reasoning. Consolidate low-signal tests. Use when the user requests Proofloop or evidence-based test reduction.
---

# Proofloop

Prefer a small set of repeatable checks of actual behavior. Temporary diagnostic probes do not
need to become permanent tests. The current task owns implementation; a native `gpt-6-luna` task with
`max` reasoning independently checks the candidate by default. Keep the current implementation model.
The user supplies the project outcome; this skill supplies the checker model and coordination.

## Set up the checker

Read [orchestration.md](references/orchestration.md) before starting a run. Reuse a suitable existing
project checker task; when task creation is authorized, create the missing checker using the native
host tools. Apply standing user authorization without asking again. Do not ask the user to repeat
the default model, reasoning level or checker role in each project prompt.

Resolve the actual checker task ID and return task ID before `start`, then fill the policy's `review`
assignment. The empty ID in the template deliberately requires setup; never invent an ID. If host
capabilities or required task-creation authorization are missing, report that specific blocker.
The skill does not override host authorization rules. Never silently drop the checker or substitute
another model. Use `review: null` only when the user explicitly chooses execution without independent
review, and identify that limitation in the handoff.

## Define the check before editing

Read applicable project instructions and existing tests. State the intended user-visible behavior,
concrete failure modes and the checks that cover them in one `proofloop.json`, using
[the policy template](assets/proofloop.template.json). Select commands the project actually provides.
Do not infer a full-suite command or invent an available environment. Define the target and synthetic
seed; use no credentials in policy or artifacts. Add `.proofloop/` to the project's root `.gitignore`.

Prefer E2E at the public boundary: browser for a web journey, real processes for a CLI. A permanent
isolated test needs a concrete failure that the selected E2E cannot adequately expose. List those
failures before implementing it. Do not append unit tests that restate newly written code.

For existing tests, read [testing.md](references/testing.md). Declare each intended add, modification
or deletion in `testChanges` with its reason and surviving checks. Unknown coverage is not proof of
redundancy. Keep unrelated user changes.

## Execute against one candidate

Use the absolute path to this installed skill's `scripts/cli.mjs` below. The skill includes compiled
JavaScript and needs only Node 24+ and Git; installation does not start anything.

```sh
node /absolute/skill/path/scripts/cli.mjs start --project /absolute/project --id task-123
# Implement within the frozen policy. Temporary probes may live under .proofloop/.
node /absolute/skill/path/scripts/cli.mjs run --project /absolute/project --id task-123
# After the assigned checker returns its actual review:
node /absolute/skill/path/scripts/cli.mjs finish --project /absolute/project --id task-123 --review .proofloop/checker-response.json
```

Read [runner.md](references/runner.md) when selecting reporters, artifact paths or diagnosing an
incomplete run. Never edit generated run records to make a check pass. A policy change requires a
new run ID. Source changes after a check require rerunning the checks. An intermediate commit does
not hide file changes from the baseline.

The runner records process results; it cannot decide whether an assertion represents the right
product requirement. Classify failures as a real defect, wrong expectation or low-value check before
changing production behavior. Do not relax the policy just to obtain a green result.

## Independent check before completion

After execution, hand the frozen candidate and evidence to the assigned Luna checker using
[orchestration.md](references/orchestration.md). Collect its actual response before completing the
run with `finish --review`. A missing required checker leaves the run incomplete. Do not add Herdr,
a watcher, or another manager.

## Completion

Return the executed command, verified behavior, changed/retired tests and their reasons, artifact
paths, checker findings and remaining limitations. `status` recalculates freshness. Do not report a
historical `finish.json` as current after further edits. An E2E trace or result must be repeatable on
the declared environment; a screenshot or a typed `pass` is insufficient.
