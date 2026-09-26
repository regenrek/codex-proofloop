# Runner acceptance: failure cases written before implementation

The reduced TypeScript CLI must exercise its public commands against disposable real Git repositories. These are system/CLI scenarios, not mocks of internal helpers. The reproducible report belongs in `.proofloop/acceptance/`.

1. Clean baseline, an in-scope source edit and an actually passing behavioral check with a fresh artifact can finish.
2. The same edit committed after start is still part of the delta. New, modified, renamed and removed tests require an exact, predeclared reason and replacement check.
3. Pre-existing uncommitted content is baseline content; changing it afterwards counts, and unchanged user edits are preserved.
4. A changed policy cannot widen paths, alter test detection or replace the command within a run. Restart is explicit and uses a new ID.
5. Nonzero exit, process spawn failure, timeout, zero tests, skips, failures or malformed/missing reporter output never pass. Old artifacts cannot substitute for new execution.
6. Any source, untracked input or artifact change after execution invalidates completion. File content, modes and staged state matter; a checkout identity change invalidates evidence.
7. A failed later retry cannot reuse an earlier success. A check that changes its own inputs cannot pass. Concurrent runner mutations are refused.
8. A planned deletion succeeds only with the declared surviving behavioral checks; unplanned deletions/renames fail. Unknown or incomplete coverage is not inferred from a green exit code.
9. Pending required review stays pending. A reported host review must reference the exact candidate/evidence, assigned checker and all criteria; it cannot replace execution. The local file is an attestation, not authenticated tool provenance.
10. Runs cannot overwrite baselines; paths cannot escape the repository/run through traversal or symlinks. All generated evidence lives in an ignored root `.proofloop/` directory. Secrets are not read by snapshot hashing.

Scope: worktree root only; tracked files and nonignored untracked files, plus the Git index. No automatic environment provisioning, provider calls, model orchestration, global mutation campaign or sandbox claim. The project owns report quality, target/seed and expected artifacts. Ignored build outputs and external dependencies are not source fingerprints.

## 2.1 pilot corrections — failure cases before implementation

- A directly invoked ignored script, or an explicitly declared ignored helper/fixture, changes or disappears after execution: status/finish must reject the old evidence. Mutation during execution must fail too. Unrelated ignored outputs must not invalidate a run. Reject secret paths, symlinks, traversal and runner-owned records as declared inputs. Inputs are project-relative; command file arguments resolve from the check's cwd.
- A complete negative TAP report must preserve its test count and report test failure, not malformed output. Zero/skipped/cancelled/todo tests still block completion.
- A silent successful build/lint command must finish with captured empty logs and zero claimed tests; a failed or timed-out process must fail. An exit-code check cannot be the sole behavioral evidence for a criterion.
- An existing empty required artifact must report ARTIFACT_EMPTY, a missing one ARTIFACT_MISSING. Neither may pass.
- A copied skill must identify the package version without its repository. Compact CLI output must retain failures and evidence references, with full records available on disk; existing full JSON output remains available.
- Exercise the Vitest JSON path using an actual installed Vitest process with passing, failing, skipped and zero-test runs before release. Malformed reports must not pass. Do not wrap builds or Vitest suites in synthetic Node tests.

Use the existing public CLI acceptance driver for regression cases. Keep reporter-specific real-tool release probes temporary; do not add private-helper unit tests.

## 2.1.1 pilot corrections — failure cases before implementation

- A correctly assigned, evidence-bound FAIL review is a valid rejection: report REVIEW_REJECTED, preserve the actual response, and keep subsequent status rejected. Wrong identity/digest, malformed JSON or invalid shape remain REVIEW_INVALID. A PASS with open findings must not finish.
- After finish, status.json must contain the same recalculated outcome, including an incomplete or rejected finish. A new run attempt removes old derived status/finish snapshots before execution so failed retries cannot leave a visible verified snapshot. The stored review must still be tied to its original evidence.
- Exercise rejection, invalid responses, correction to PASS and snapshot freshness through the existing public CLI review scenario; no helper unit tests.
