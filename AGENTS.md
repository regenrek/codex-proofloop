# Proofloop runner development

- The agent-neutral skill is maintained in `instructa/agent-skills`, under `skills/engineering/proofloop`. This repository owns the optional runner only; do not reintroduce a skill entrypoint or duplicate its strategy here. Model, reviewer and transport choices belong to the caller.
- New permanent tests need a concrete failure and a gap in existing checks before implementation. Prefer the public CLI, real Git repositories and real subprocesses. Do not test copied wording or private helper structure.
- The optional runner has real external contracts: `package.json` owns the published package name and executable; `src/policy.mts::validatePolicy` owns the policy schema; `src/cli.mts::main` and `execute` expose commands and consume or produce persisted run records. Preserve these existing consumer boundaries unless deliberately changing them; do not add legacy-shape parsers, aliases or migration code.
- Edit `src/*.mts`; `npm run build` regenerates `skills/proofloop/scripts/*.mjs` and version metadata. Include source and generated runtime changes together. Keep runtime npm dependencies at zero unless a concrete need justifies one.
- Use `npm run format`, `npm run lint`, `npm run format:check` and `npm run build`. `npm run acceptance` exercises the public CLI in disposable repositories and writes `.proofloop/acceptance/result.json`; its contract is in `docs/runner-acceptance.md`.
- Keep one runner. No model-specific variants, background watchers, duplicate review workflow or new verification framework.
- Treat local review files as attestations. Local validation does not prove live product behavior, host skill loading, reviewer identity or delivery-speed improvement.
