# Proofloop

![Proofloop banner](assets/proofloop-banner.png)

Proofloop keeps coding-agent tests useful without letting every debugging experiment become permanent.

`BUILD → ACCEPT → HARDEN → DISTILL`

**Catch aggressively. Commit reluctantly.**

## Why this exists

Sol may create temporary tests, probes, scripts, fixtures, and diagnostics while exploring a change.
Those can be valuable in the moment, but they should not automatically live in your repository
forever.

Proofloop makes them ephemeral by default. A test stays only when it protects a unique, accepted,
observable behavior that existing tests do not already cover.

## Choose a skill

| Skill | Includes | Needs Herdr? |
| --- | --- | --- |
| `proofloop-sol-luna` | Native Sol + optional bounded Luna review | No |
| `proofloop-herdr-sol-luna` | Sol + optional Luna sentinel or review | Yes |
| `proofloop-herdr-sol-luna-fable` | Sol + Luna + one bounded Fable review | Yes |
| `proofloop-herdr-sol-luna-fable-planr` | Sol + Luna + Fable + Planr task evidence | Yes |

Each directory under `skills/` is standalone. Install only the one you need.

## How it works

1. **BUILD:** Sol implements the candidate. Temporary probes stay in a run-owned evidence folder;
   tracked tests cannot be changed.
2. **ACCEPT:** Deterministic checks or a human accept the behavior.
3. **HARDEN:** Only tests with explicit evidence and a small declared budget may enter the permanent
   suite.
4. **DISTILL:** Keep the smallest stable test that protects the invariant. Drop the rest.

The deterministic gate uses Git to notice changes even when files were created by shell commands. It
preserves changes that were already present before the run and works with Sol alone. Luna remains
optional.

## A small comparison

We ran one simple Pokedex test with the same task and starter tests: normal Sol on one side,
Proofloop Sol + Luna on the other. Both produced a working app. Proofloop finished faster and added no
permanent tests; Vanilla added three focused tests.

| Vanilla Sol | Proofloop Sol + Luna |
| :---: | :---: |
| ![Vanilla Sol Pokedex](assets/benchmark/vanilla-pokedex.png) | ![Proofloop Sol and Luna Pokedex](assets/benchmark/proofloop-pokedex.png) |

This was only one simple test, not a scientific or definitive benchmark.
[Read the understandable benchmark result.](docs/benchmark-minimal.md)

## Install with `npx skills`

Browse and choose interactively:

```bash
npx skills add regenrek/codex-proofloop
```

Or install one skill directly for Codex:

```bash
npx skills add regenrek/codex-proofloop --skill proofloop-sol-luna -g -a codex -y
```

For the smallest Herdr setup:

```bash
npx skills add regenrek/codex-proofloop --skill proofloop-herdr-sol-luna -g -a codex -y
```

You can also clone the repository and copy any single directory from `skills/` into your skills
folder. Installing a skill starts no watcher, daemon, heartbeat, or background service.

## Safety by default

- Sol is the only implementation writer.
- Luna and Fable are read-only and optional.
- The native skill has no Herdr dependency or sentinel runtime.
- The Herdr sentinel is opt-in, attached to one run, and time-bounded.
- BUILD defaults to zero permanent test changes.
- A full test suite is never guessed or used as the normal iteration command.
- Credential paths are excluded from evidence and baseline snapshots.

## Development

```bash
python3 -m compileall skills/*/scripts
python3 -m unittest discover -s tests -v
npx skills add . --list
```

See [CHANGELOG.md](CHANGELOG.md) for releases. MIT licensed; see [LICENSE](LICENSE).

## Sources

Proofloop is inspired by Meta's distinction between temporary catching tests and permanent hardening
tests, together with research suggesting that test quantity alone is a weak signal of coding-agent
success.

- [Rethinking the Value of Agent-Generated Tests](https://arxiv.org/abs/2602.07900)
- [The Death of Traditional Testing: JiTTesting at Meta](https://engineering.fb.com/2026/02/11/developer-tools/the-death-of-traditional-testing-agentic-development-jit-testing-revival/)
- [Mutation-Guided LLM-based Test Generation at Meta](https://arxiv.org/abs/2501.12862)
- [SWE-Mutation: Can LLMs Generate Reliable Test Suites?](https://arxiv.org/abs/2605.22175)
