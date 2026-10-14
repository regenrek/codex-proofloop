# Optional command runner

Use this only for an explicitly selected frozen command run. The separate Proofloop skill is
maintained in [instructa/agent-skills](https://github.com/instructa/agent-skills/tree/main/skills/engineering/proofloop)
and uses the host's existing tools and records; it needs no runner, policy or installed Node.
The runner records selected automated checks. It does not import browser-session or human evidence,
provision environments, choose models or start reviewers. Do not create a wrapper test merely to
make a live observation fit this protocol.

## Start a run

Adapt [the policy template](../assets/proofloop.template.json) to existing project commands and save
it as `proofloop.json`. Keep the selected check set small: `run` starts the whole list again and
stops at its first failure. It has no affected-check selection or evidence carry-forward across
changed candidates. For iterative live debugging, use the ordinary skill workflow instead.

The template uses `review: null`: the runner verifies execution, not independent review. If the
task requires a review attestation here, assign the actual existing reviewer before `start` as
described below. The runner cannot override the project's review requirement.

```sh
proofloop start --project /path/to/project --id feature-123
# Implement within the declared scope.
proofloop run --project /path/to/project --id feature-123 --compact
proofloop finish --project /path/to/project --id feature-123 --compact
```

The npm package exposes these commands as `proofloop`. From a checkout, replace `proofloop` with
`node /absolute/path/to/codex-proofloop/skills/proofloop/scripts/cli.mjs`. Paths below refer to the
project being checked, not the runner installation.

## Workspace and policy

Node 24+ and Git. The project must be the Git worktree root and have at least one commit. The root
`.proofloop/` must be ignored and untracked. All paths are project-relative, except the executable in
`command`. Scope patterns support `*`, `**`, `?`; braces and character classes are not supported.
`cwd` is a literal relative directory. Commands are argument arrays executed without a shell.

The only editable input is `proofloop.json` (or the path supplied to `start --policy`). It holds the
goal, allowed paths, test detection, criteria with failure modes, checks, planned test changes,
environment labels and optional review assignment. All criteria need a check. Change the policy
before starting a new run; do not overwrite an existing baseline.

In `testChanges`, declare each intended `add`, `modify` or `delete` with its exact path, reason and
surviving check IDs. A rename is a deletion plus an addition. For a permanent isolated addition,
describe the gap in the selected journey in `reason` and the concrete failure in its criterion.
The runner checks declarations and execution; it cannot judge the semantic value of a test.

```json
{"path":"tests/copied-title.test.mjs","action":"delete","reason":"Restates the production lookup; the retained journey checks the rendered result","checks":["journey"]}
```

## Commands

- `start --project PATH --id ID [--policy PATH]`: snapshot policy and existing working content.
- `run --project PATH --id ID`: invalidate old execution and execute all checks sequentially. Stop on
  the first failure. Each attempt has a fresh directory. `run` does not imply final acceptance.
- `status --project PATH --id ID`: recalculate scope, evidence and review freshness.
- `finish --project PATH --id ID [--review PATH]`: perform the same checks and write `finish.json`.
- `--version`: print the installed runner version.

Add `--compact` to `run`, `status` or `finish` for short JSON with outcomes, problems and a full
`record` path. Use this in agent conversations; load detailed records only as needed. The default
full JSON output remains available for existing callers. `status` also saves its recalculated
packet to `status.json` beside the execution records; this derived packet is never trusted as state.
`finish` refreshes that same snapshot, including on rejection. A new execution attempt removes the
previous `status.json` and `finish.json` before spawning checks. Copies saved elsewhere remain
historical snapshots. Use finish's returned result without an immediate redundant status call.

A correctly assigned, evidence-bound FAIL review (or PASS with open findings) yields
`REVIEW_REJECTED` and exit 2. Valid negative reviews are stored so subsequent status remains rejected.
Malformed/unreadable responses, invalid structure, wrong task IDs or stale evidence yield
`REVIEW_INVALID`. Rejection does not mean the review file needs a formatting fix.

Exit 0 means that command succeeded; `start` success is not verification. `status`/`finish` exit 2 for
incomplete evidence. Errors in configuration or invocation exit 1. An active runner holds
`.proofloop/runner.lock` across the worktree. If killed without cleanup, inspect the recorded PID and
remove the lock only after confirming that process has ended. No automatic stale-lock takeover.

## Optional assigned review

Reviewer choice and authorization belong to the user or existing orchestrator. Record that actual
assignment in the policy before `start`; there is no model or reasoning-level default:

```json
{"review":{"threadId":"actual-reviewer-task-id","model":"actual-selected-model","reasoning":"actual-selected-effort"}}
```

After execution, use the returned record or `status --compact` to give the assigned reviewer the
relevant diff and evidence. Reuse that review; do not add a second Proofloop reviewer. The host
owns delegation, waiting and delivery. A required missing review leaves completion open.

Store the reviewer's actual response under the project's `.proofloop/`:

```json
{
  "threadId": "actual-reviewer-task-id",
  "evidence": "digest-from-status",
  "verdict": "pass",
  "criteria": ["journey"],
  "findings": [],
  "summary": "What was checked, limits and any nonblocking follow-ups."
}
```

`findings` contains unresolved blocking findings; nonblocking notes belong in `summary`. Do not
reclassify a product defect or unmet requirement just to finish. Run `finish --review
.proofloop/review.json --compact`. The runner validates the assignment reference and evidence
binding, not the reviewer's identity or model: this is an unauthenticated local attestation. Never
invent a response. Corrections require new execution; review the fix and affected risks against
the new evidence. Use finish's returned result without a redundant status call.

## Reporters and artifacts

Supported reporters:

- **node-tap**: direct `node --test --test-reporter=tap ...`; requires one complete summary, positive
  test count, all tests passing, zero failures/cancellations/skips/todos. Do not combine summaries.
- **playwright-json**: direct Playwright CLI with `--reporter=json`; requires positive expected count,
  zero unexpected/flaky/skipped tests, suites and no reporter errors. Use an installed project CLI,
  e.g. `node node_modules/@playwright/test/cli.js test e2e/cards.spec.ts --reporter=json`. An npm wrapper
  that mixes banners into stdout is unsuitable. Configure trace/output paths under the environment
  variable below; the runner does not launch or configure browsers itself.
- **vitest-json**: run the project's installed Vitest once (`run`) with its JSON reporter on stdout.
  For versions that default to a file, configure `test.reporters: [["json", { stdout: true }]]`.
  Older versions can use `--reporter=json` directly. Require a positive count, successful suites and
  assertions, and no failed, pending or todo tests. Do not mix other reporters/banners into stdout.
  See [Vitest reporter options](https://vitest.dev/guide/reporters). No Node-test wrapper is needed.
- **exit-code**: supporting build, lint or typecheck command; successful exit, no signal/timeout.
  Stdout/stderr may be empty and are still captured. This reports zero tests and cannot be the sole
  check for any behavior criterion. Every criterion must also reference a test-reporter check.

Complete negative reports retain their test count and produce `TESTS_INCOMPLETE`; malformed or
truncated reports produce `REPORT_INVALID`. A nonzero process exit also produces `CHECK_FAILED`.

Every process receives a fresh absolute `PROOFLOOP_OUTPUT_DIR`. Write declared artifact paths below
that directory, for example `writeFileSync(join(process.env.PROOFLOOP_OUTPUT_DIR, 'outcome.json'), ...)`.
A Playwright config can set `outputDir` there and select a deterministic per-test trace path to list
in `artifacts`. The runner records stdout/stderr and additional nonempty regular files, then hashes
them. Each declared file must exist in the current attempt. A failed check still retains its logs.
An existing empty declared artifact produces `ARTIFACT_EMPTY`; an absent one `ARTIFACT_MISSING`.
`PLAYWRIGHT_JSON_OUTPUT_*` overrides are removed to keep the JSON report on stdout.
The parent Node test runner's `NODE_TEST_CONTEXT` is removed so nested checks execute normally.
Runner attempt records live beside output directories and cannot overwrite a project's `result.json`.

`artifacts` may be empty for checks whose structured stdout is the complete artifact. Browser journeys
should declare a trace or equivalent replay evidence. Reporter data establishes execution; it does
not prove a meaningful oracle. The runner trusts the selected executable and reporter implementation.
No arbitrary user-authored `ok: true` document substitutes for the reporter.

## Ignored check inputs

Existing local file arguments in `command` are automatically hashed, resolving from `cwd`, even
under `.proofloop/`. Declare other ignored inputs explicitly as project-relative literal paths:

```json
"inputs": [".proofloop/probe-runtime.mjs", ".proofloop/synthetic-seed.json"]
```

This optional list covers helpers, imported fixtures and configs that Git ignores. Files must exist
at `start`; keep generated outputs and runner-owned records out of the list. Content/mode hashes are
captured before execution, compared afterwards and recomputed by `status`/`finish`. Changed or removed
inputs invalidate the evidence and review. Unrelated ignored outputs do not. There is no automatic
import graph, package-script, shell or option-value (`--config=path`) resolution; explicitly declare
ignored files reached that way. External executables/dependencies remain outside this local check.
Secret-like paths, symlinks, `.git/` and `.proofloop/runs/` are rejected as declared inputs.

## Evidence boundaries

The fingerprint contains repository identity, HEAD, index entries, and content/mode hashes of tracked
and nonignored untracked files, including source, tests, config and lockfiles. It compares working
content to the initial snapshot, so intermediate commits cannot hide the net file delta. Unchanged
pre-existing edits are baseline content. File restoration removes its net delta; this is not a
complete edit-history recorder. Ignored outputs and external dependencies are not fingerprinted;
the check-input mechanism above separately binds selected ignored files into the evidence digest.
Symlinks and submodule entries among source inputs are unsupported and rejected. Secret-like paths
(`.env*`, keys, credentials, secrets directories) are recorded by metadata only, never read for
content hashing, and changes to them are rejected. This heuristic cannot identify every secret;
keep credentials ignored and out of commands/output. Child processes inherit the environment;
environment values are not captured in evidence.

Checks must not change their fingerprinted inputs. A changed source, staged state, commit, runner or
artifact requires another execution. External services can change without changing a local hash;
`environment.target` and `seed` are declared context, not measured deployment identities. Pin and
reset the actual environment in the project-owned check when reproducibility requires it.

Finish active runs with their pinned runner before upgrading. The published `codex-proofloop` npm
name, CLI commands, policy schema and on-disk records remain public contracts. Version 3 separates
the skill into its own collection without changing those formats. There is no migration, alias, alternate parser or legacy-format
branch. A different runner/version digest requires fresh execution; do not overwrite old evidence.

A local agent can edit this runner and its records. This is an execution guardrail, not a tamper-proof
sandbox or attestation service. Windows timeout cleanup guarantees the child process only; POSIX
cleanup also terminates its process group. Do not use checks to start shared persistent services.
