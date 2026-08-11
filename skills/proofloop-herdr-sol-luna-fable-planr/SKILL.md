---
name: proofloop-herdr-sol-luna-fable-planr
description: Coordinate Planr-backed or project-configured Herdr workflows in which Sol owns intake, architecture, design-sensitive implementation, integration, and the final decision; Luna Max serves only as an explicitly selected read-only silent sentinel, fresh bounded verifier, or interactive operator; and Fable supplies at most one independent semantic challenge or final review. Use for bounded Sol-Luna-Fable implementation runs with Planr task sources, explicit ownership, evidence, budgets, or pane lifecycle safety; do not use for trivial edits, hidden background processes, or overlapping writers.
---

# Proofloop Herdr: Sol, Luna, Fable, and Planr

Keep Sol responsible for the task, architecture, sole-writer implementation, integration, and final
decision. Add another agent only when its distinct role materially improves the run.

## Start from project policy

1. Discover the repository root with its version-control or project tooling; otherwise use the
   explicit working directory.
2. Read the applicable `AGENTS.md` files and locate the project profile they name. If none exists,
   adapt [assets/project-profile.template.json](assets/project-profile.template.json) and the
   [AGENTS.md template](assets/AGENTS.md.template.md) inside the project before orchestrating.
3. Create one run contract from [assets/run-contract.template.json](assets/run-contract.template.json).
   Keep allowed paths project-relative and choose one literal validation command.
4. Validate both documents:

   ```bash
   python3 scripts/validate_config.py path/to/project-profile.json path/to/run-contract.json
   ```

Stop if policy, scope, ownership, or the source task is ambiguous. Never inspect credential
contents or copy credentials into prompts, logs, contracts, or evidence.

## Select the smallest useful topology

- Use **Sol only** for ordinary implementation and deterministic validation.
- Add **one Luna Max silent sentinel** only when the run contract explicitly selects it for a
  long-running Sol implementation. `luna_mode: null` creates no Luna pane or process.
  Start it only with [scripts/silent_sentinel.py](scripts/silent_sentinel.py); the script refuses an
  unselected mode and exits at settlement, owner loss, mandatory stop, or its deadline.
- Add **one fresh Luna Max bounded verifier** only when project policy selects it and independent
  verification is worth a separate session.
- Add **one fresh Luna Max interactive operator** only for sustained UI or manual interaction that
  cannot be represented by the validation command.
- Ask **Fable once per hypothesis**, either before implementation to challenge it or afterward for
  final semantic review. Do not use both by default.

Do not overlap writers. Luna never edits product source, tests, task state, or documentation.
Fable challenges or reviews but does not write. Human owners decide subjective or manual
acceptance. Sol resolves all findings and makes the final decision.

## Run the loop

1. Read policy and validate the profile and run contract.
2. Run `python3 scripts/test_distillation_gate.py snapshot` before the first edit.
3. Start the optional silent sentinel only when selected.
4. Execute the declared BUILD or HARDEN phase; do not add tracked tests while implementation changes.
5. Run the exact focused validation command, then `test_distillation_gate.py settle`.
6. Use optional independent review once. Sol integrates the decision.
7. Stop workflow-owned processes, clean panes, and return one evidence-backed handoff.

When a sentinel stops, its bundled runtime atomically archives the final state and records the
archive path in the process record. Sol and the parent workflow must never delete or manually rename
the sentinel state. Resolve `cleanup.sentinel_process_record` to an absolute path before prompting
Luna; require Luna to repeat that exact path verbatim after exit or report `MISSING` at that path.
Never let an agent infer an evidence filename from a naming convention.

The lifecycle is `BUILD -> ACCEPT -> HARDEN -> DISTILL -> PROMOTE OR DROP`. New HARDEN work requires a
new contract and baseline. Temporary probes stay in the ephemeral directory and are removed before
settlement. Production code is not subordinate to speculative tests: classify failures as `BUG`,
`BAD_ORACLE`, or `LOW_VALUE`. See [references/testing.md](references/testing.md).

Read [references/orchestration.md](references/orchestration.md) when operating Herdr panes, defining
evidence, handling stop conditions, or migrating an existing workflow. Use the
[Planr example](examples/planr-project-profile.json) when the task source is a Planr item.

## Preserve pane ownership

Reuse a pane only when its target, working directory, purpose, and current state are known and it
contains no active user work. Record whether each pane pre-existed and whether the workflow created
it. Close only exact pane IDs marked `created_by_workflow: true`. Stop workflow-started sessions in
reused panes but leave those panes open. A sentinel remains silent while healthy, sends only
deduplicated event notices, exits at its deadline or settlement, and is never detached as a daemon.
Never leave completed sentinel or verifier panes behind.

## Return one handoff

Report the task and source, sole writer, topology used, files changed, validation command and semantic
result, evidence paths, independent findings and Sol's decision, manual acceptance still required,
stop conditions encountered, and pane cleanup status. Do not claim manual quality without its human
owner's acceptance.
