---
name: proofloop-sol-luna
description: Run bounded Sol implementation work with an enforceable Git-based test-distillation gate and an optional fresh read-only Luna review, without Herdr or a background watcher. Use when agent-generated tests should remain temporary during BUILD and require proof before permanent admission in HARDEN.
---

# Proofloop: Sol and Luna

Keep Sol responsible for intake, architecture, the sole-writer patch, integration, and the final
decision. Luna is optional and read-only. This variant runs directly in Codex and does not require an
orchestrator, pane manager, watcher, daemon, or long-lived heartbeat.

## Start from project policy

1. Find the repository root and read every applicable `AGENTS.md`.
2. Locate the project profile named there. If none exists, adapt
   [assets/project-profile.template.json](assets/project-profile.template.json) and the
   [AGENTS.md template](assets/AGENTS.md.template.md) inside the project.
3. Create one run contract from [assets/run-contract.template.json](assets/run-contract.template.json).
   Keep paths project-relative and use one literal focused validation command.
4. Validate both documents:

   ```bash
   python3 scripts/validate_config.py path/to/project-profile.json path/to/run-contract.json
   ```

Stop if policy, scope, ownership, or the source task is ambiguous. Never inspect credential contents
or copy credentials into prompts, logs, contracts, or evidence.

## Run the loop

1. Validate the profile and run contract.
2. Before the first edit, run `python3 scripts/test_distillation_gate.py snapshot` with absolute
   project, profile, and contract paths.
3. Execute BUILD or HARDEN exactly as the contract declares.
4. Run the literal focused validation command.
5. Run `test_distillation_gate.py settle` with the same three paths.
6. If `luna_mode` selects `bounded-verifier`, start one fresh read-only Luna review only after the
   candidate is frozen. If the host cannot provide that capability, stop and report it; never fake
   the review or replace it with a background watcher.
7. Let Sol integrate the result and return one evidence-backed handoff.

The test lifecycle is `BUILD -> ACCEPT -> HARDEN -> DISTILL -> PROMOTE OR DROP`. Do not add tracked
tests while implementation is still changing. Temporary probes belong only in the declared ephemeral
directory and must be removed before settlement. Acceptance starts a new HARDEN contract and a new
baseline; never switch phases inside one contract.

Production code is not subordinate to speculative tests. Classify a failed proposal as `BUG`,
`BAD_ORACLE`, or `LOW_VALUE` before changing production code. Keep runtime changes, temporary
validation, permanent tests, and documentation separable. Read
[references/testing.md](references/testing.md) for admission evidence and
[references/orchestration.md](references/orchestration.md) for the native run lifecycle.

## Keep Luna bounded

Use Sol only by default. A selected Luna verifier receives only the frozen accepted diff, relevant
existing tests, temporary candidates or findings, acceptance criteria, proposed admissions, and the
explicit test budget. Luna may return `CATCH`, `PROMOTE`, `MERGE`, or `DROP`; it must not edit files,
invent more edge cases, broaden the test plan, or delegate further. Sol owns the final decision.

## Return one handoff

Report the task, source, phase, sole writer, files changed, focused validation result, gate verdict,
admission decision, evidence paths, manual acceptance still required, and any stop condition. Do not
claim subjective or manual quality without its human owner's acceptance.
