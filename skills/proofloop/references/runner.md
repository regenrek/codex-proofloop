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
- `--version`: print the installed version, including from a copied skill directory.

Add `--compact` to `run`, `status` or `finish` for short JSON with outcomes, problems and a full
`record` path. Use this in agent conversations; load detailed records only as needed. The default
full JSON output remains available for existing callers. `status` also saves its recalculated
packet to `status.json` beside the execution records; this derived packet is never trusted as state.

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

Finish active runs with their installed runner before upgrading. Existing 2.0 policies remain valid;
2.0 execution evidence must be rerun under 2.1 because the runner and input binding changed.

A local agent can edit this runner and its records. This is an execution guardrail, not a tamper-proof
sandbox or attestation service. Windows timeout cleanup guarantees the child process only; POSIX
cleanup also terminates its process group. Do not use checks to start shared persistent services.
