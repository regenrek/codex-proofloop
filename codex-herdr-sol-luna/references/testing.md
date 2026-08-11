# Test distillation

**Catch aggressively. Commit reluctantly.** More tests are not automatically better. Every permanent
test adds maintenance, runtime, and a future oracle that production code may be bent around.

The lifecycle is `BUILD -> ACCEPT -> HARDEN -> DISTILL -> PROMOTE OR DROP`. Temporary probes are
ephemeral by default; a permanent test must protect a unique, important, observable invariant.

## BUILD and ACCEPT

Run the deterministic snapshot before Sol's first edit. During BUILD, implement one coherent
candidate, run the configured focused command, and keep executable probes, scripts, fixtures, and
risk mutants only in `ephemeral_directory`. Do not add tracked tests while implementation is still
changing. Do not run the configured full suite.
Do not add broad corpora, snapshot or golden updates, or permanent documentation merely because an
intermediate attempt exposed something.

Acceptance may be deterministic or human-owned. A manual-feel candidate is never declared correct by
Sol or Luna; return a short human checklist. Acceptance ends the BUILD contract. HARDEN always uses a
new contract and baseline.

## HARDEN and admission

Treat accepted production behavior as frozen. Inspect the nearest tests first and prefer merging or
parameterizing an existing test. Group examples by root invariant. Prove the candidate temporarily:

- the relevant existing suite passes on the counterfactual;
- the candidate test fails on that counterfactual;
- the final test passes on accepted behavior.

For a bug fix, the original behavior is the normal counterfactual. For a feature or refactor, at most
one realistic issue-specific risk mutant may be used. Generic mutation campaigns are out of scope.
Promote only the smallest deterministic test at a stable public or observable boundary. Write an
admission record, remove every unpromoted probe, run focused validation, then settle the gate. Coverage
and test count are telemetry, never admission evidence by themselves.

A fresh bounded Luna verifier may evaluate only the frozen diff, relevant existing tests, supplied
candidates/findings, acceptance criteria, proposed admissions, and explicit budget. It may decide:

- `CATCH`: accepted behavior has a real defect;
- `PROMOTE`: the candidate deserves permanent residence;
- `MERGE`: preserve the invariant in an existing test;
- `DROP`: the candidate is redundant, speculative, wrongly oracled, coupled, flaky, slow, or costly.

It does not invent edge cases or a broader plan and never edits source, tests, manifests, or docs. Sol
owns the final decision.

## Failed speculative tests

Production code is not subordinate to speculative tests. Classify a failing proposal first:

- `BUG`: accepted behavior is violated; Sol may repair production code.
- `BAD_ORACLE`: the expectation is wrong; correct or drop the test.
- `LOW_VALUE`: the difference is real but not important, unique, or stable; drop it.

A test-file failure does not automatically invalidate a compile-clean runtime candidate. Keep runtime,
temporary validation, permanent tests, and documentation separable so rollback stays selective.

## Full suites and limitations

Existing focused tests may run during BUILD. A full suite runs only in HARDEN when the contract
explicitly allows it, names a concrete reason, and the profile configures the literal command;
otherwise leave it to CI. The gate never guesses framework commands or executes tests itself.

Path globs cannot reliably identify inline tests embedded in production files, such as some Rust test
modules. Binary and symlink changes are detected safely, but added-line telemetry may be zero. Legacy
test retirement is a future workflow: normal BUILD/HARDEN rejects test deletion and renaming.

## Small examples

BUILD policy:

```json
{"phase":"build","test_policy":{"permanent":{"max_new_invariants":0,"max_changed_test_files":0,"max_added_test_lines":0},"full_suite":{"allowed":false,"reason":null}}}
```

Typical HARDEN policy (not a quota):

```json
{"phase":"harden","test_policy":{"permanent":{"max_new_invariants":1,"max_changed_test_files":1,"max_added_test_lines":100},"full_suite":{"allowed":false,"reason":null}}}
```

Valid admission entry:

```json
{"invariant_id":"auth.expired-token-rejected","disposition":"merge-existing","test_paths":["tests/auth/test_tokens.py"],"observable_contract":"Expired tokens cannot access tenant data","stable_boundary":"Public API authorization result","counterfactual":{"kind":"baseline","description":"Original behavior","existing_suite":{"verdict":"pass","evidence":".codex-herdr/evidence/run/existing.json"},"candidate":{"verdict":"fail","evidence":".codex-herdr/evidence/run/candidate.json"}},"final":{"verdict":"pass","evidence":".codex-herdr/evidence/run/final.json"},"distinct_signal":"Existing tests miss validly signed expired tokens","deterministic":true}
```

A valid no-test outcome has no permanent test delta, an absent admission document or
`"admissions": []`, zero admitted invariants, and an empty ephemeral directory.
