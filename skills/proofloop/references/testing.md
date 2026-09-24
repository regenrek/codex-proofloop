# Keep behavior, remove repetition

Assess assertions, not file extensions. A `node:test` file that drives real CLI processes or restarts
a Worker is an integration/system check. A browser test that mocks every meaningful boundary may
still provide little confidence.

For each removal or merge, name the observable behavior and the **remaining** check that would catch
its failure. Compare the whole proposed deletion group: two deleted tests cannot replace each other.
Where the requirement itself is intentionally removed, state that explicitly. Do not infer coverage
from similar test names.

Useful removal candidates include comparisons to the same production lookup table, incidental copy
or private call ordering, and repeated fixture scaffolding with no distinct outcome. Check history
before claiming that a test caused repeated refactor failures. A suspected burden is not a measured
one.

Preserve targeted isolated tests for meaningful state combinations, authorization, malformed
protocols, concurrency or controlled faults that a selected E2E journey misses. State the risk first.
No blanket deletion percentage, coverage target or line budget.

Example planned deletion in the single policy:

```json
{"path":"tests/copied-title.test.mjs","action":"delete","reason":"Restates the production lookup; the retained journey checks the rendered result","checks":["journey"]}
```

`action` is `add`, `modify` or `delete`. A rename has a deletion and addition. The runner checks exact
paths and actions and requires the named checks to execute. It cannot infer semantic equivalence,
detect arbitrary inline tests, or prove a rationale is sound. Use checker review for those decisions.
For permanent isolated additions, explain the E2E gap in `reason`, and list failure modes in the
relevant criteria before implementation.

Use a prior real failure or one relevant controlled fault to establish detection when warranted.
Run it in a disposable fixture or separately authorized environment; preserve the steps and evidence.
Do not mutate a shared checkout while another task checks it. Avoid broad mutation campaigns as a
routine admission tax. Existing useful tests need no ceremonial re-proving merely to stay.
