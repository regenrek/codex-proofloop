# Proofloop

[![Status: Experimental](https://img.shields.io/badge/status-experimental-orange)](https://github.com/regenrek/codex-proofloop)

![Proofloop banner](https://raw.githubusercontent.com/regenrek/codex-proofloop/main/assets/proofloop-banner.png)

Keep coding-agent tests useful. Define behavior and failure modes before implementation, run focused
E2E or integration checks, retain repeatable artifacts, and justify permanent test changes.

**One native Codex skill. One TypeScript runner. No runtime npm dependencies.**

## Install

Requires Node 24+ and Git. Install the CLI:

```sh
npm install -g codex-proofloop
proofloop --help
```

Or run it without a global install:

```sh
npx --yes codex-proofloop@2.0.0 --help
```

For the complete Codex workflow, install the self-contained skill:

```sh
npx skills add regenrek/codex-proofloop --skill proofloop -g -a codex -y
```

Then invoke `$proofloop`. It includes compiled JavaScript; skill users do not need Python, a compiler,
Herdr or a background service. The installation command uses the version on GitHub; local unpushed
changes can be installed with `npx skills add . --skill proofloop -g -a codex -y` from this repository.

## Run

Adapt [the policy template](skills/proofloop/assets/proofloop.template.json) to the project's actual
commands and save it as `proofloop.json`. Add `.proofloop/` to the root `.gitignore`. Define criteria,
concrete failure modes, allowed paths and planned test changes **before editing**.

From this repository checkout:

```sh
node skills/proofloop/scripts/cli.mjs start --project /path/to/project --id feature-123
# Implement within the policy.
node skills/proofloop/scripts/cli.mjs run --project /path/to/project --id feature-123
# After the assigned Luna checker returns its review:
node skills/proofloop/scripts/cli.mjs finish --project /path/to/project --id feature-123 --review .proofloop/checker-response.json
```

From an installed skill, use the absolute path to its `scripts/cli.mjs`. The npm package exposes
the same runner as `proofloop`; replace the `node .../cli.mjs` prefix above with `proofloop`.
The CLI executes checks; the Codex skill coordinates the independent Luna task.

The runner records real process exits, standard Node TAP or Playwright JSON reports, fresh artifacts
and the checked Git working state. Failed, skipped, zero-test and stale runs cannot finish. Source
changes committed during a run still count. Planned test deletions are supported; unexplained changes
are rejected. Test count and line budgets do not determine quality.

[Runner contract](skills/proofloop/references/runner.md) covers reporter setup, paths and limitations.
[Testing guidance](skills/proofloop/references/testing.md) explains admission and consolidation.

## Independent Luna check

The skill uses a native GPT-6 Luna checker with max reasoning by default. It resolves the assignment
and reuses a suitable existing project task, or creates one when task creation is authorized. Apply
existing authorization without asking again. The implementation task keeps its chosen model.
The project prompt only needs `$proofloop` and the desired outcome; model and role are skill defaults.
Missing capabilities or required authorization are reported explicitly, without silently skipping
review. Execution without independent review requires an explicit user choice.

The policy template contains an empty checker task ID. The skill fills it with the actual assigned
task ID before `start`. Direct CLI use supports `review: null` for execution-only workflows, including
this repository's CLI self-check; that does not constitute the skill's default independent review.

[Native task workflow](skills/proofloop/references/orchestration.md) describes ownership, handoff and
review. Required review remains incomplete until supplied. A local review file is explicitly an
unauthenticated attestation; the host task history establishes who actually performed it.

## What this does and does not establish

A completed run establishes that the selected checks passed against the recorded local state and
that scope/artifact/review requirements were satisfied. It does not establish that those checks cover
every product risk, that an external deployment stayed unchanged, or that an agent cannot edit local
records. There is no filesystem sandbox. Use meaningful acceptance criteria and inspect the diff.

## Development

```sh
npm ci
npm run format
npm run lint
npm run format:check
npm run build
npm run acceptance
```

Oxlint checks source and acceptance code; Oxfmt keeps code and configuration consistently formatted.
CI enforces both. `npm run lint:fix` applies safe lint fixes. Generated runtime files are formatted
automatically during the build.

The CLI acceptance script uses disposable real Git repositories and subprocesses. It writes a
repeatable report to `.proofloop/acceptance/result.json`. [Failure cases were recorded before the
implementation](https://github.com/regenrek/codex-proofloop/blob/main/docs/runner-acceptance.md). Generated `.mjs` files are committed with the skill so it
works when copied alone; regenerate them from `src/*.mts`, never edit them independently.

This is a breaking simplification of the experimental v1 workflow: four Python variants become one
TypeScript skill. Old profiles, contracts and run records are not migrated. Finish existing runs
with their installed version, then create one new policy and run for v2. The prior
[Pokedex comparison](https://github.com/regenrek/codex-proofloop/blob/main/docs/benchmark-minimal.md) describes v1 and is not evidence of v2 effectiveness.

MIT licensed. See [CHANGELOG.md](https://github.com/regenrek/codex-proofloop/blob/main/CHANGELOG.md) and [LICENSE](LICENSE).
