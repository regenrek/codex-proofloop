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

Before `start`, put the actual assignment in the policy:

```json
{"review":{"threadId":"actual-checker-task-id","model":"gpt-6-luna","reasoning":"max"}}
```

If the user explicitly opts out of independent review, set `review: null` before starting and state
that the run contains execution evidence only. Do not use this to bypass an unavailable checker.

After `run`, `status` returns the candidate, evidence digest, criteria, commands and artifacts. Send
this packet, the relevant diff and test-retirement rationale to the checker, with the main task's
return ID. Ask it to inspect the actual artifacts and observable behavior, identify relevant missing
cases, and return actionable findings. Do not ask it to mirror the implementation with new unit tests.
No nested delegation or broader feature work. End the handoff turn when using asynchronous return
messaging; do not run a progress-only polling conversation.

The checker returns criteria assessed, concrete findings, limitations and the evidence digest it
reviewed. After a real host response, record the response as an attestation under `.proofloop/`, e.g.:

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

**Provenance:** the runner validates the reference and completeness, not the model or task identity.
It labels this as an unauthenticated attestation. The host task history supplies its origin. Never
fabricate that history or silently replace a required independent check with the implementer's
self-review. Runner execution evidence and reviewer judgment have separate roles.
