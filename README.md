# Proofloop command runner

> [!IMPORTANT]
> **New skill home: [Proofloop in instructa/agent-skills](https://github.com/instructa/agent-skills/blob/main/skills/engineering/proofloop/README.md).**
> This repository contains the optional command runner.

That skill brings live verification forward, limits new permanent tests to meaningful gaps and
bounds repeated checks. It uses the agent's existing tools and does not require this runner.

Install the skill from its new home:

```sh
npx skills add instructa/agent-skills --skill proofloop -g
```

This repository retains the optional command runner and its development tooling. It no longer
contains a discoverable `SKILL.md`, activation template or second copy of the skill's strategy.
The historical `skills/proofloop/` runtime path remains because published packages expose it.

## Use the runner

Use this runner only when a task explicitly needs frozen automated execution records. It captures
selected command results and binds them to a Git working state. It does not choose agents, launch
reviewers or import manual browser observations. Do not create artificial tests to fit its protocol.

The npm package name remains `codex-proofloop`; its executable is `proofloop`. Node 24+ and Git are
required. Version 3.0.0 is not released on npm. To use this checkout directly:

```sh
node skills/proofloop/scripts/cli.mjs --help
node skills/proofloop/scripts/cli.mjs --version
```

[Runner instructions](skills/proofloop/references/runner.md) cover `start`, `run`, `status`, `finish`,
policy setup, reporters and an optional assigned review. Its policy template defaults to no reviewer;
when the project requires one, reuse that actual assignment. The runner reruns the selected list
from the start, so keep it to the required final command set.

The public CLI, policy schema and persisted formats are retained. Finish active runs with their
pinned runner before upgrading; a changed runner digest requires fresh execution. There is no
migration or second legacy implementation. Local records are attestations, not proof of reviewer
identity or live deployment behavior.

## Development

```sh
npm ci
npm run format
npm run lint
npm run format:check
npm run build
npm run acceptance
```

Edit `src/*.mts` and regenerate the bundled runtime with `npm run build`. The existing acceptance
checks exercise real Git repositories and CLI processes and write `.proofloop/acceptance/result.json`.
See the [runner acceptance contract](docs/runner-acceptance.md) and [CHANGELOG](CHANGELOG.md).
The runtime has no npm dependencies. Skill changes belong in
[instructa/agent-skills](https://github.com/instructa/agent-skills/tree/main/skills/engineering/proofloop).

MIT licensed. See [LICENSE](LICENSE).
