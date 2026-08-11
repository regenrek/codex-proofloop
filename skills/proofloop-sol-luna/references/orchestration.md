# Native orchestration reference

Use this reference after the project profile and run contract validate. Test policy and permanent
admission are defined in [testing.md](testing.md).

## Ownership

Sol owns intake, architecture, design-sensitive implementation, integration, direct validation, and
the final decision. Sol is the sole writer for a coherent patch batch.

Luna is optional, fresh, bounded, and read-only. It may inspect a frozen candidate once when the run
contract selects `bounded-verifier`. It does not edit source, tests, task state, or documentation; it
does not invent a broader test plan; and it does not create child agents.

No process starts when this skill is installed. This native variant has no sentinel, pane lifecycle,
heartbeat, daemon, or Herdr dependency.

## Agent packet

Give a selected Luna verifier only:

- the frozen accepted diff;
- relevant existing tests;
- temporary candidate tests or findings;
- acceptance criteria;
- proposed admission records;
- the explicit permanent-test budget.

Ask only for `CATCH`, `PROMOTE`, `MERGE`, or `DROP` decisions with concise evidence. Do not send the
parent transcript. Sol decides whether to accept a finding.

## Evidence and settlement

Run the deterministic gate snapshot before Sol's first edit. BUILD returns a candidate without
tracked test edits. Human-owned or deterministic acceptance ends that contract. A separate HARDEN
contract distills temporary candidates and settles with proof-carrying admission.

Record the literal validation command, working directory, duration, exit code, semantic verdict,
required artifacts, gate result, and any manual acceptance still needed. Zero executed tests do not
count as a passing test run.

## Stop conditions

Finish only the current atomic action when a contract stop condition occurs, including an
out-of-scope write, second writer, disproved hypothesis, new subsystem, budget breach, repeated
unchanged validation, context compaction during design-sensitive work, or a manual acceptance
boundary. Return an evidence-backed handoff instead of silently expanding scope.
