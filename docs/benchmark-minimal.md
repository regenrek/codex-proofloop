# Minimal Pokedex benchmark

We ran one small comparison to see how a normal Sol run differs from a Proofloop BUILD run.

This was a simple test, not a scientific benchmark. It used only one task and one run per setup, so
the result should be treated as an example rather than proof that one workflow always performs
better.

## What we built

Both runs built the same dependency-free Pokedex application from the same task description. Each
app contains 40 local Pokemon records and supports:

- search by name or number;
- type filters and sorting;
- pagination;
- persistent favorites;
- detailed Pokemon views;
- comparing two Pokemon;
- responsive and accessible layouts.

Both runs used isolated Git repositories, the same Sol model and reasoning level, the same six
starter tests, and the same `npm test` validation command.

The only intentional workflow difference was:

- **Vanilla:** Sol used its normal judgment about implementation and tests.
- **Proofloop:** Sol followed the BUILD gate, could not add permanent tests, and received one fresh
  read-only Luna review after the candidate was frozen.

## The two results

| Vanilla Sol | Proofloop Sol + Luna |
| :---: | :---: |
| ![Vanilla Sol Pokedex](../assets/benchmark/vanilla-pokedex.png) | ![Proofloop Sol and Luna Pokedex](../assets/benchmark/proofloop-pokedex.png) |

Both applications rendered successfully in Chrome and passed their automated tests.

| Result | Vanilla Sol | Proofloop Sol + Luna |
| --- | ---: | ---: |
| Sol implementation time | about 6m 31s | about 4m 41s |
| Production and documentation lines | 1,027 | 694 |
| Passing tests | 9 | 6 |
| Tests added by the agent | 3 tests / 33 lines | 0 |
| Proofloop gate | Not used | Passed with 0 violations |
| Changed permanent test files | 1 new file | 0 |
| Temporary files left behind | Not measured | 0 |
| Fresh Luna review | Not used | `DROP` — no actionable defect found |

## Easy takeaway

For this BUILD run, Proofloop was about 28% faster, produced a smaller implementation, and guaranteed
that no temporary test became permanent by accident.

Vanilla provided broader automated verification immediately. Its three additional tests were focused
and potentially useful; this run did not produce test spam. In a complete Proofloop lifecycle, those
kinds of tests would be considered after human acceptance in a separate HARDEN run.

So Proofloop performed better at the thing it is designed to control: keeping BUILD fast and keeping
permanent test growth deliberate. This single simple test does not prove that its visual design or
product implementation is always better.

Manual visual preference and the final interactive acceptance remain human-owned.
