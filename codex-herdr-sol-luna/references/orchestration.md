# Orchestration reference

Use this reference only after the project profile and run contract validate.

## Contents

- [Role invariants](#role-invariants)
- [Mode selection](#mode-selection)
- [Silent sentinel lifecycle](#silent-sentinel-lifecycle)
- [Herdr preflight and pane reuse](#herdr-preflight-and-pane-reuse)
- [Ownership record](#ownership-record)
- [Agent packets](#agent-packets)
- [Evidence and settlement](#evidence-and-settlement)
- [Stop conditions](#stop-conditions)
- [Cleanup](#cleanup)

## Role invariants

Sol owns intake, architecture, design-sensitive production changes, integration, direct validation,
and the final decision. Sol is the sole writer for a coherent batch.

Luna runs at the Luna model's maximum reasoning setting and remains read-only. Project policy may
select exactly one of these roles for a run:

- silent sentinel: watch scope, time, patch, and validation budgets without healthy messages;
- bounded verifier: independently execute or inspect the frozen validation target;
- interactive operator: operate a UI or manual process and capture observations.

Start a fresh Luna agent session for bounded verification or interactive operation. A silent
sentinel may remain attached only for the bounded active run it watches.

## Mode selection

Prefer a direct Sol run. Add an agent only for a distinct need declared by the project profile:

| Need | Role | Source access | Writes |
| --- | --- | --- | --- |
| Silent scope/time checks during a long run | Luna sentinel | Read-only | External state and process record only |
| Independent frozen-source validation | Fresh Luna verifier | Read-only | Declared evidence artifacts only |
| Sustained UI/manual interaction | Fresh Luna operator | Read-only | Declared evidence artifacts only |

Do not silently switch modes. A new hypothesis, second subsystem, or changed owner requires a new
contract and run.

## Silent sentinel lifecycle

Installing this skill starts nothing. Keep `luna_mode` set to `null` unless the run explicitly needs
a sentinel. When selected, use `silent-sentinel` and run one bounded watcher in a recorded
workflow-owned pane; never detach it as a daemon or leave it running for a later run.

Create a pending process record before launch, then add the exact process id immediately after
startup. Record its owner, state path, start time, and deadline. Poll internally at the configured
interval and write health to external state. Do not send healthy, acknowledgement, or unchanged
status messages.

Send one deduplicated notice only for a new warning, stop, blocker, or completion. Prefer a native
advisory message that does not start a user turn. If the host lacks that capability, use a normal
user message only for a critical stop or blocker. Keep durable detail in the state file and send a
short pointer; advisory messages still consume model context and may survive compaction.

Exit the watcher at the earliest of target settlement, mandatory stop, owner cleanup, target loss,
or the configured runtime deadline. The parent workflow remains responsible for stopping the exact
recorded process in a cleanup path even when the writer fails or the notice transport is unavailable.

## Herdr preflight and pane reuse

Before creating or reusing a pane:

1. Confirm `herdr` is available and the server is healthy with the installed CLI's documented status
   command.
2. Inspect installed CLI help instead of assuming a version-specific command surface.
3. Resolve the exact workspace target and canonical project directory from the profile.
4. Inventory existing panes and agents without modifying them.
5. Reject any pane with active or ambiguous user work.

A pane is suitable only when its workspace target and working directory match, its role is compatible,
and it is idle or intentionally owned by the same active run. Reusing a pane means attaching a new
agent session when freshness is required; it never means inheriting an old verifier's context.

If no pane is suitable, split one using the installed CLI. Capture the returned pane ID before
starting an agent. Use a unique run-derived agent name rather than a fixed project or task name.
Configure Luna with the available Luna model at maximum reasoning and a read-only prompt. Do not
grant product write permission merely because the local process has broad filesystem access.

## Ownership record

Store the ownership record in the contract's evidence directory. Append an entry immediately after
creating or reusing a pane:

```json
{
  "run_id": "generated-unique-run-id",
  "panes": [
    {
      "pane_id": "exact-id-from-herdr",
      "agent_name": "unique-agent-name",
      "purpose": "silent-sentinel",
      "project_root": "/canonical/project/root",
      "pane_preexisting": false,
      "created_by_workflow": true,
      "agent_session_created_by_workflow": true,
      "created_at_utc": "ISO-8601 timestamp",
      "closed_at_utc": null
    }
  ],
  "processes": [
    {
      "process_id": 12345,
      "purpose": "silent-sentinel",
      "started_by_workflow": true,
      "started_at_utc": "ISO-8601 timestamp",
      "deadline_utc": "ISO-8601 timestamp",
      "stopped_at_utc": null
    }
  ]
}
```

Never infer ownership from a pane name. The exact recorded ID and `created_by_workflow` flag control
cleanup.

## Agent packets

Send minimal English packets. Include:

- exact role and read/write prohibition;
- task ID, source, goal, and causal hypothesis;
- canonical project root and project-relative allowed paths;
- baseline workspace facts and files necessary for the role;
- selected phase, time budget, and stop conditions;
- one validation command or exact interactive sequence;
- evidence destinations and pass criteria;
- handoff schema;
- prohibition on child agents, credentials, scope expansion, and architecture changes.

Do not send the parent transcript. A sentinel receives the contract, policy, and current run
identifiers, not product decision authority. A verifier receives frozen source and cannot repair
failures.

## Evidence and settlement

Record semantic results, not only exit codes. Evidence should identify the literal command, working
directory, start and duration, timeout, exit code, tests discovered/executed/passed/failed when
applicable, required artifacts, observations, and verdict (`pass`, `fail`, `infrastructure`, or
`timeout`). Zero executed tests do not pass.

A handoff is settled only when the agent is idle, done, blocked, or stopped at its budget. Read one
final handoff, then let Sol inspect the actual diff and evidence. Sol decides whether an independent
finding is accepted, rejected, or requires a new contract.

## Stop conditions

Stop after the current atomic action when any contract stop condition occurs. Typical stops include:

- a write outside allowed paths;
- a second writer or nested delegation;
- a disproved hypothesis or new subsystem;
- a checkpoint or hard-stop budget breach;
- a patch-batch budget breach;
- repeated unchanged validation;
- context compaction during design-sensitive work;
- missing or ambiguous task ownership;
- a manual acceptance boundary.

Do not automatically continue after a mandatory stop. Return the smallest evidence-backed handoff
that another Sol session can resume.

## Cleanup

After integration:

1. Stop each exact workflow-started process and record its exit time.
2. Stop each workflow-started agent session and read its final state once.
3. Retire unique sentinel state so another run cannot load old notices.
4. Close each exact pane whose record says `created_by_workflow: true`.
5. Leave every pre-existing pane open, even when its temporary agent session has stopped.
6. Mark closed entries with a timestamp and confirm no completed workflow-created sentinel or
   verifier panes remain.

If cleanup cannot complete, report the exact pane ID, owner flag, agent state, and blocker.
