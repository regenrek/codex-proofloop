# Changelog

## [2.1.1] - 2026-09-26

- Report valid negative reviews and open findings as `REVIEW_REJECTED`; reserve `REVIEW_INVALID` for malformed, mismatched or stale responses. Preserve valid negative attestations for subsequent status calls.
- Refresh `status.json` on every finish, including rejected completion. Remove old status/finish snapshots before a new execution attempt.
- Clarify the native return task ID and use finish's returned record without a redundant status round trip. Keep existing focused review and no-duplicate-preflight guidance.

## [2.1.0] - 2026-09-24

- Bind directly invoked local files and optional declared `inputs` to execution evidence, including ignored check drivers and helpers. Recheck them during execution and completion.
- Add direct `vitest-json` and supporting `exit-code` checks, avoiding Node-test wrappers for Vitest, builds, lint and typechecks. Exit-code checks claim no tests and cannot replace behavioral evidence.
- Preserve test counts for complete negative TAP reports; distinguish incomplete test outcomes from malformed reports and empty artifacts from missing files.
- Add `--version`, including copied skills, and opt-in `--compact` output linking full execution/status/finish records.
- Reduce skill overhead: compact file-based handoffs, one focused review, targeted fix reviews and no mandatory success report or feedback diary.
- Existing policy files remain supported. Finish active runs before upgrading; old execution evidence needs rerunning under the changed runner.

## [2.0.0] - 2026-09-24

- Replaced four Python variants with one native `proofloop` skill and a TypeScript CLI using Node's `parseArgs`.
- Removed Herdr/Sentinel/Fable/Planr runtimes, duplicated schemas and tests of variant text.
- Replaced manual phase contracts and test-line budgets with one frozen policy and generated execution records.
- Added full working-state fingerprints, actual check execution, reporter validation, artifact freshness and planned test retirement.
- Made native GPT-6 Luna/max review the skill default, with evidence-bound, explicitly unauthenticated review attestations.
- Ported useful Git/CLI boundary coverage to 22 repeatable system acceptance scenarios.
- Added Oxlint and Oxfmt with CI enforcement and formatted bundled runtime output.
- Requires Node 24+; bundled JavaScript has no runtime npm dependencies. No automatic conversion of v1 profiles or run records.

## Earlier unreleased v1 work

- Added a prominent Experimental warning that explains Proofloop's filesystem and recovery boundary.
- Renamed the product to Proofloop and moved every standalone skill under `skills/`.
- Added `proofloop-sol-luna`, a native Codex variant with no Herdr dependency, sentinel, pane
  lifecycle, heartbeat, or background process.
- Made all four variants discoverable and installable through `npx skills`.
- Added a small, clearly limited Vanilla-versus-Proofloop Pokedex benchmark with side-by-side
  screenshots and an easy-to-read result.
- Added a concise explanation of the Test Distillation motivation and its research inspiration.
- Updated the repository banner to feature the Codex mascot guiding three agent paths through the
  deterministic gate.

## 1.0.0 — 2026-08-11

First public release.

- Three standalone skill variants: Sol + Luna, Sol + Luna + Fable, and Sol + Luna + Fable + Planr.
- One-writer workflow with optional read-only review and monitoring.
- Opt-in, time-bounded silent sentinel with durable run evidence.
- Deterministic Git-based test gate that keeps exploratory tests temporary by default.
- Focused validation, permanent-test admission, and full-suite safeguards.
- Dependency-free runtime scripts and project templates in every variant.
- Automated tests and GitHub Actions for Python 3.11 and 3.13.
