## Proofloop

- Do not write permanent unit tests after implementing code. If isolation is necessary, first list the concrete failure modes and explain what the selected E2E misses.
- Prefer E2E checks of actual user behavior. Keep a verifiable, repeatable artifact from each run.
- Do not turn every debugging probe into a permanent test. Preserve isolated checks that protect important failures the E2E does not cover.
- Use the installed `proofloop` skill with this project's `proofloop.json`. Freeze criteria and scope before editing. Execute the declared checks through its runner and finish against the same candidate.
- The skill sets up an independent native GPT-6 Luna checker with max reasoning by default. Reuse a suitable task, apply existing task-creation authorization, and resolve its actual ID before starting. Do not silently skip review when the checker is unavailable.
- Consolidate tests by protected behavior. Record the reason and surviving checks before deleting a test; consider the whole deletion group together.
- A failed, skipped, missing or stale check is incomplete. Coverage percentage, test count and a reviewer's assertion alone do not establish success.
