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
