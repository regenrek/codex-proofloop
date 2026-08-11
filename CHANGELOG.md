# Changelog

## Unreleased

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
