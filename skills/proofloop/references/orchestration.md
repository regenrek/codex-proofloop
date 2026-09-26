# Native checker task

The current main task implements. The default checker is a native task running `gpt-6-luna` with
`max` reasoning. Resolve this setup from the skill; the user need not specify it again in the project
prompt. Reuse an existing suitable project task, checking its role and model before reuse. Create
one only when the user has authorized task creation. Apply authorization already given in the
session; do not request it again. The skill cannot grant permission that the host requires from the
user. Inspect the host's current tool schemas and available model identifiers. If unavailable,
report the specific missing capability; do not default to unreviewed completion or another model.
No Herdr, SDK daemon, polling loop or additional manager is required.

Use the host's native task/project listing, task creation and task messaging tools. When creation
is authorized, select `gpt-6-luna` and `max` using the tool's supported model and reasoning fields.
Select the existing project checkout when requested. Provide both task IDs and persist the return ID and
ownership in the task context. The checker owns verification outputs; the main task owns source
edits. Coordinate shared browser/server use. Freeze production edits while checking.
Label the IDs explicitly as `checkerTaskId` and `returnTaskId` in the assignment. Resolve the return
ID from the actual implementing task; never infer it from the checker ID or an old handoff. Return
the result once to `returnTaskId` when messaging is authorized; otherwise expose it to the caller.

Before `start`, put the actual assignment in the policy:

```json
{"review":{"threadId":"actual-checker-task-id","model":"gpt-6-luna","reasoning":"max"}}
```

If the user explicitly opts out of independent review, set `review: null` before starting and state
that the run contains execution evidence only. Do not use this to bypass an unavailable checker.

After `run`, use `status --compact`. Send its record path, a short objective, the relevant diff/files,
any test-retirement rationale and the main task's return ID. The record already contains the
candidate, evidence digest, criteria, commands and artifact paths. Do not copy whole logs, hashes or
previous reports into messages. Reuse checker context and send only changes on subsequent handoffs.

Start with one focused review pass: inspect the relevant diff and selected execution evidence, then
independently probe a concrete, material coverage gap if needed. Do not rerun the entire suite merely
to duplicate existing evidence, or add unit tests mirroring the implementation. Small changes need
small reviews. No nested delegation or broader feature work. End the handoff turn when using
asynchronous return messaging; no polling, acknowledgment exchanges or progress-only messages.

The checker returns the compact attestation below. For a failure, include the behavior, file or
reproduction and required correction in `findings`; mention material limits in `summary`. A separate
Markdown success report is unnecessary. After a real host response, store that actual response under
`.proofloop/`, e.g.:

```json
{
  "threadId":"actual-checker-task-id",
  "evidence":"digest-from-status",
  "verdict":"pass",
  "criteria":["journey"],
  "findings":[],
  "summary":"What was independently checked, and any nonblocking limits."
}
```

Run `finish --review .proofloop/checker-response.json`. Missing/mismatched review, unresolved findings
or any failed execution remains incomplete. A valid review is stored for later `status` calls. Fixes
require new execution and review of the new evidence; do not reuse an earlier digest.
`REVIEW_REJECTED` means a valid FAIL response or open findings; fix those findings rather than
rewriting the response to satisfy validation. `REVIEW_INVALID` means malformed, mismatched or stale
review evidence. Use finish's returned record as the completion result; an immediate extra status
call is unnecessary. Recalculate status only when freshness needs checking after later work.
Re-review the fix and affected risks only. Continue review rounds only for concrete unresolved
findings; report a blocker when those cannot be resolved within the assignment. Stop when the
required checks and review pass. Do not expand a successful review into speculative hardening.

**Provenance:** the runner validates the reference and completeness, not the model or task identity.
It labels this as an unauthenticated attestation. The host task history supplies its origin. Never
fabricate that history or silently replace a required independent check with the implementer's
self-review. Runner execution evidence and reviewer judgment have separate roles.
