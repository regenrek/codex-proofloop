# AGENTS.md

## Proofloop Sol-Luna contract

- Task source: `<issue, plan item, specification, or local path>`
- Project profile: `<project-relative path to project-profile.json>`
- Runtime owner: Sol owns intake, architecture, design-sensitive implementation, integration, and
  the final decision.
- Sole writer: Sol owns the coherent patch batch. No overlapping writers or child agents.
- Luna: `<off or one fresh bounded read-only verifier>`; no watcher or background process.
- Phase: `<build or harden>`; phase changes require a new contract and baseline.
- Allowed and forbidden paths: `<project-relative paths or globs>`
- Focused validation command: `<one literal command>`
- Optional full-suite command: `<literal command or none>`; never guess it.
- Tracked test globs: `<project-relative, case-insensitive globs>`
- Test baseline record: `<project-relative evidence path>`
- Ephemeral probe directory: `<project-relative evidence path>`
- Test admission record: `<project-relative evidence path>`
- Permanent test budget: `<new invariants / changed files / added lines>`
- Full-suite policy: `<denied or explicitly allowed in HARDEN with reason>`
- Evidence directory: `<project-relative path>`
- Time and patch budgets: `<checkpoint / hard stop / maximum coherent batches>`
- Stop conditions: `<scope change, failed hypothesis, second writer, timeout, manual boundary>`
- Manual acceptance: `<owner, required yes/no, and explicit criteria>`

Before editing, validate the profile and contract with the installed `proofloop-sol-luna` validator,
then snapshot the deterministic Test Distillation Gate. During BUILD, do not edit tracked tests. Put
temporary probes only in the declared ephemeral directory and remove them before settlement.
Classify proposed-test failures as BUG, BAD_ORACLE, or LOW_VALUE before changing production code.
Preserve the existing workspace delta and never inspect credential contents. Stop after the current
atomic action when a stop condition fires, then return an evidence-backed handoff.
