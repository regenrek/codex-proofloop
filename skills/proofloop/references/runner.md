# Runner contract

Node 24+ and Git. The project must be the Git worktree root and have at least one commit. The root
`.proofloop/` must be ignored and untracked. All paths are project-relative, except the executable in
`command`. Scope patterns support `*`, `**`, `?`; braces and character classes are not supported.
`cwd` is a literal relative directory. Commands are argument arrays executed without a shell.

The only editable input is `proofloop.json` (or the path supplied to `start --policy`). It holds the
goal, allowed paths, test detection, criteria with failure modes, checks, planned test changes,
environment labels and optional review assignment. All criteria need a check. Change the policy
before starting a new run; do not overwrite an existing baseline.

## Commands

- `start --project PATH --id ID [--policy PATH]`: snapshot policy and existing working content.
- `run --project PATH --id ID`: invalidate old execution and execute all checks sequentially. Stop on
  the first failure. Each attempt has a fresh directory. `run` does not imply final acceptance.
- `status --project PATH --id ID`: recalculate scope, evidence and review freshness.
- `finish --project PATH --id ID [--review PATH]`: perform the same checks and write `finish.json`.

Exit 0 means that command succeeded; `start` success is not verification. `status`/`finish` exit 2 for
incomplete evidence. Errors in configuration or invocation exit 1. An active runner holds
`.proofloop/runner.lock` across the worktree. If killed without cleanup, inspect the recorded PID and
remove the lock only after confirming that process has ended. No automatic stale-lock takeover.

## Reporters and artifacts

Supported reporters:

- **node-tap**: direct `node --test --test-reporter=tap ...`; requires one complete summary, positive
  test count, all tests passing, zero failures/cancellations/skips/todos. Do not combine summaries.
- **playwright-json**: direct Playwright CLI with `--reporter=json`; requires positive expected count,
  zero unexpected/flaky/skipped tests, suites and no reporter errors. Use an installed project CLI,
  e.g. `node node_modules/@playwright/test/cli.js test e2e/cards.spec.ts --reporter=json`. An npm wrapper
  that mixes banners into stdout is unsuitable. Configure trace/output paths under the environment
  variable below; the runner does not launch or configure browsers itself.

Every process receives a fresh absolute `PROOFLOOP_OUTPUT_DIR`. Write declared artifact paths below
that directory, for example `writeFileSync(join(process.env.PROOFLOOP_OUTPUT_DIR, 'outcome.json'), ...)`.
A Playwright config can set `outputDir` there and select a deterministic per-test trace path to list
in `artifacts`. The runner records stdout/stderr and additional nonempty regular files, then hashes
them. Each declared file must exist in the current attempt. A failed check still retains its logs.
`PLAYWRIGHT_JSON_OUTPUT_*` overrides are removed to keep the JSON report on stdout.
The parent Node test runner's `NODE_TEST_CONTEXT` is removed so nested checks execute normally.
Runner attempt records live beside output directories and cannot overwrite a project's `result.json`.

`artifacts` may be empty for checks whose structured stdout is the complete artifact. Browser journeys
should declare a trace or equivalent replay evidence. Reporter data establishes execution; it does
not prove a meaningful oracle. The runner trusts the selected executable and reporter implementation.
No arbitrary user-authored `ok: true` document substitutes for the reporter.

## Evidence boundaries

The fingerprint contains repository identity, HEAD, index entries, and content/mode hashes of tracked
and nonignored untracked files, including source, tests, config and lockfiles. It compares working
content to the initial snapshot, so intermediate commits cannot hide the net file delta. Unchanged
pre-existing edits are baseline content. File restoration removes its net delta; this is not a
complete edit-history recorder. Ignored outputs and external dependencies are not fingerprinted.
Symlinks and submodule entries among source inputs are unsupported and rejected. Secret-like paths
(`.env*`, keys, credentials, secrets directories) are recorded by metadata only, never read for
content hashing, and changes to them are rejected. This heuristic cannot identify every secret;
keep credentials ignored and out of commands/output. Child processes inherit the environment;
environment values are not captured in evidence.

Checks must not change their fingerprinted inputs. A changed source, staged state, commit, runner or
artifact requires another execution. External services can change without changing a local hash;
`environment.target` and `seed` are declared context, not measured deployment identities. Pin and
reset the actual environment in the project-owned check when reproducibility requires it.

A local agent can edit this runner and its records. This is an execution guardrail, not a tamper-proof
sandbox or attestation service. Windows timeout cleanup guarantees the child process only; POSIX
cleanup also terminates its process group. Do not use checks to start shared persistent services.
