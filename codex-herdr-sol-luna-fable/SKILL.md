---
name: codex-herdr-sol-luna-fable
description: Coordinate project-configured Herdr workflows in which Sol owns intake, architecture, design-sensitive implementation, integration, and the final decision; Luna Max serves only as an explicitly selected read-only silent sentinel, fresh bounded verifier, or interactive operator; and Fable supplies at most one independent semantic challenge or final review. Use for bounded Sol-Luna-Fable implementation runs with explicit ownership, evidence, budgets, or pane lifecycle safety; do not use for trivial edits, hidden background processes, or overlapping writers.
---

# Codex Herdr: Sol, Luna, and Fable

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

1. Snapshot the current repository delta and record it as user-owned baseline state.
2. Preflight Herdr only when a Luna or Fable pane is selected. Do not install, upgrade, or reconfigure
   Herdr automatically.
3. Reuse a suitable pane when possible, but start a fresh Luna agent session for each verifier or
   interactive operation. Immediately record every workflow-created pane and agent session.
   For a sentinel, also record its process, state path, owner, and deadline before it starts.
4. Give each agent only the task source, contract, profile, necessary files, acceptance criteria,
   baseline facts, and handoff schema. Prohibit child agents and scope expansion.
5. Keep one coherent Sol patch batch within the contract. At checkpoint or stop conditions, finish
   only the current atomic action and return evidence-backed state.
6. Run the profile's exact validation command. Treat zero discovered tests, missing artifacts, timeouts,
   or semantic failures as non-passing evidence.
7. Use any selected independent review once. Sol checks its claims against the diff and evidence.
8. Integrate the decision, write the handoff, stop every workflow-started process, and clean up all
   workflow-owned completed panes.

Read [references/orchestration.md](references/orchestration.md) when operating Herdr panes, defining
evidence, handling stop conditions, or migrating an existing workflow.

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
