# Planr specialization example

- Task source: the selected Planr live-map item and its active FeatureRun acceptance criteria.
- Project profile: `examples/planr-project-profile.json` (copy and adapt it into the consuming
  project).
- Ownership: Sol is the sole implementation writer and final decision owner.
- Allowed paths: derive the narrow path set from the selected Planr item; the example profile caps
  it at `src/**`, `tests/**`, and `docs/**`.
- Phase: start with BUILD and zero permanent-test budget; create a new HARDEN contract only after
  acceptance. A Planr item does not require a new test by default.
- Focused validation command: `python3 -m unittest tests.test_selected -v` from the repository root.
- Optional CI/full-suite command: `python3 -m unittest discover -s tests -v`, denied during BUILD.
- Evidence: Planr item state, baseline, diff, semantic validation result, and final handoff under the
  configured evidence directory.
- Budgets: checkpoint at 15 minutes, hard stop at 35 minutes, one coherent patch batch.
- Stop conditions: changed Planr dependency/state, disproved hypothesis, scope expansion, second
  writer, out-of-scope write, or elapsed budget.
- Human acceptance: add explicit criteria when the Planr item crosses a manual product boundary; it
  is the boundary between BUILD and a possible HARDEN run.
- Cleanup: record every workflow-created pane; close only recorded workflow-created panes and leave
  reused pre-existing panes open.

Luna may serve only as a read-only sentinel or fresh bounded verifier for this profile. Fable may
perform one final semantic review. This example intentionally contains no engine, UI framework, or
Unity-specific policy.
