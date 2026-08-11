# Codex Herdr Orchestrator

![Codex Herdr Orchestrator banner](assets/codex-herdr-orchestrator-banner.png)

Three standalone Codex skills for clear, bounded workflows in Herdr: one writer, optional reviewers,
and no hidden background service.

**Catch aggressively. Commit reluctantly.**

## Choose a version

| Directory | Includes | Best when |
| --- | --- | --- |
| `codex-herdr-sol-luna/` | Sol + Luna | You want the smallest workflow |
| `codex-herdr-sol-luna-fable/` | Sol + Luna + Fable | You also have Fable for one independent review |
| `codex-herdr-sol-luna-fable-planr/` | Sol + Luna + Fable + Planr | Your tasks and evidence live in Planr |

Each directory is complete by itself. Copy only the variant you need.

## What you get

- **One implementation owner:** Sol is the only writer.
- **Optional review:** Luna, Fable, and Planr appear only in variants that include them.
- **No surprise processes:** installing a skill starts nothing. Luna's silent sentinel is opt-in,
  bounded, and stops at settlement or its deadline.
- **Durable evidence:** contracts, validation results, and the sentinel's final state remain attached
  to the run.
- **Test discipline:** temporary probes stay temporary unless they prove a valuable invariant.

## Test Distillation Gate

Every variant ships the same dependency-free deterministic gate. It works in Sol-only runs with Luna
disabled:

`BUILD -> ACCEPT -> HARDEN -> DISTILL -> PROMOTE OR DROP`

BUILD starts with a zero-permanent-test budget. After acceptance, HARDEN may promote a small test only
with explicit budget and counterfactual evidence. Luna can review an admission, but never writes tests.

```bash
python3 scripts/test_distillation_gate.py snapshot --project /absolute/project \
  --project-profile /absolute/project/policy/profile.json \
  --run-contract /absolute/project/policy/build-run.json
# implement and run the configured focused validation command
python3 scripts/test_distillation_gate.py settle --project /absolute/project \
  --project-profile /absolute/project/policy/profile.json \
  --run-contract /absolute/project/policy/build-run.json
```

Schema 3 replaces `tests_allowed` with `test_policy` and renames the old phases to `build` and
`harden`. Migrate v2 files explicitly; the validator returns a migration-oriented error instead of
silently coercing them. Add `validation.full_suite_command` (often `null`) and the profile's `testing`
policy, replace the contract boolean with baseline/result/ephemeral/admission paths and explicit
budgets, then create a fresh baseline. Do not reuse a v2 baseline across this boundary.

The gate classifies tests through configurable paths. Inline tests inside production files cannot be
reliably classified this way. Binary and symlink changes are handled safely, but their added-line count
may be zero. Test deletion, renaming, and legacy-suite retirement are intentionally out of scope.

## Install

Copy one directory into your Codex skills folder:

```bash
cp -R codex-herdr-sol-luna ~/.agents/skills/
```

Then ask Codex to use it:

```text
Use $codex-herdr-sol-luna for this task.
```

For pane-based modes, Herdr must already be installed and running. Each variant includes its own
templates, validator, sentinel, and test gate. Sol-only gate runs need only Python and Git.

## Check the repository

```bash
python3 -m compileall codex-herdr-sol-luna/scripts codex-herdr-sol-luna-fable/scripts codex-herdr-sol-luna-fable-planr/scripts
python3 -m unittest discover -s tests -v
```

The shipped BUILD contract has a zero permanent-test budget. Validate its profile and contract
together; validate the non-empty admission example separately or with a matching HARDEN contract.

MIT licensed. See [LICENSE](LICENSE).
