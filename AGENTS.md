# Proofloop development

- Do not add permanent unit tests after implementing code. Before an isolated test is justified, write the failure modes and explain the gap in existing E2E coverage.
- Prefer checks through the public CLI, real Git repositories and real subprocesses. Keep a repeatable result artifact. Do not test copied wording or private helper structure.
- Edit `src/*.mts`; `npm run build` regenerates the self-contained `skills/proofloop/scripts/*.mjs` runtime. Include both source and generated runtime in changes. Keep runtime npm dependencies at zero unless a concrete need justifies one.
- Use `npm run format` for Oxfmt formatting and `npm run lint` for Oxlint checks. Keep two-space indentation and braces on control-flow bodies. The build also formats generated runtime files; do not edit them by hand.
- `npm run acceptance` exercises disposable repositories and writes `.proofloop/acceptance/result.json`. The acceptance contract is in `docs/runner-acceptance.md`.
- There is one skill, one policy per project and generated records per run. Avoid adding model-specific variants, phase contracts, background watchers or an external orchestrator dependency.
- Treat local review files as attestations. Do not claim authenticated model identity, live product verification or deployment coverage from a local passing check.
