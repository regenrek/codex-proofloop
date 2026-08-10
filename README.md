# Codex Herdr Orchestrator

Codex Herdr Orchestrator is a reusable Codex skill for bounded, visible multi-agent work through
Herdr. It keeps the intelligence composite without making ownership fuzzy:

- Sol owns intake, architecture, design-sensitive implementation, integration, and the final
  decision.
- Luna Max is optional and read-only: a heartbeat sentinel, fresh bounded verifier, or fresh
  interactive operator selected by project policy.
- Fable supplies at most one independent semantic challenge or final review per hypothesis.
- One coherent batch has exactly one writer.

The repository also ships an `AGENTS.md` template, validated project/run contracts, pane lifecycle
rules, and a small Planr-oriented example. It is not an agent framework, daemon, service, package
manager, or Herdr installer.

## Install

Clone or copy this repository into a Codex skill directory using the folder name
`codex-herdr-orchestrator`:

```bash
git clone https://github.com/regenrek/codex-herdr-orchestrator.git \
  ~/.agents/skills/codex-herdr-orchestrator
```

The skill is intentionally not installed globally by this repository. Herdr must already be
installed, configured, and running when a project selects a pane-backed role.

## Adopt in a project

1. Copy `assets/AGENTS.md.template.md` into the relevant project as `AGENTS.md` and replace every
   placeholder.
2. Copy `assets/project-profile.template.json` to a project-owned path and specialize the task
   source, allowed paths, command, evidence, budgets, stops, and human acceptance.
3. Copy `assets/run-contract.template.json` to a per-run location and narrow it to one task and
   hypothesis.
4. Validate the documents:

   ```bash
   python3 /path/to/codex-herdr-orchestrator/scripts/validate_config.py \
     path/to/project-profile.json path/to/run-contract.json
   ```

5. Ask Codex: `Use $codex-herdr-orchestrator to execute the selected task under this project's
   profile and run contract.`

For Planr-backed work, start from `examples/planr-project-profile.json` and
`examples/planr-AGENTS.md`. They demonstrate Planr specialization without imposing a game engine,
UI system, test framework, or Unity policy.

## Repository layout

```text
SKILL.md                              Core orchestration workflow
agents/openai.yaml                    Codex UI metadata
assets/AGENTS.md.template.md          Project policy template
assets/project-profile.template.json  Reusable project configuration
assets/run-contract.template.json     Per-run contract
references/orchestration.md           Detailed roles, evidence, and pane lifecycle
scripts/validate_config.py            Dependency-free strict validator
examples/planr-*                      Small Planr specialization
tests/test_validate_config.py         Focused validator tests
```

## Validation

Run the repository's exact accepted check:

```bash
python3 -m unittest discover -s tests -v
```

Validate the skill metadata separately with Codex's `quick_validate.py` from the installed
`skill-creator` skill.

## Migration from a project-specific Herdr workflow

1. Move project names, task IDs, absolute paths, validation commands, and framework-specific rules
   out of orchestration prose and into the consuming project's profile or `AGENTS.md`.
2. Replace any “always create a pane” rule with suitability preflight and explicit ownership. A
   fresh verifier session may reuse a safe pane; it may not reuse the old verifier's context.
3. Make Sol the sole implementation writer. Convert Luna writers into read-only sentinel, verifier,
   or operator roles, and reduce repeated reviewers to one Fable challenge or final review.
4. Replace inferred cleanup (names, positions, or timestamps) with exact recorded pane IDs and a
   `created_by_workflow` flag. Close only those panes and retire completed sentinels/verifiers.
5. Replace framework-specific recovery loops with one project-defined validation command, semantic
   pass criteria, evidence requirements, and explicit stop conditions.
6. Validate the new profile and contract before the first migrated run.

Migration is not automatic. Existing project policy still needs human review, Herdr command details
must match the installed version, and manual acceptance criteria remain owned by the project.

## Known limitations

- The validator checks structure and safety invariants; it does not prove that a command, path glob,
  Herdr target, or Planr item exists.
- Codex Herdr Orchestrator does not start Herdr, discover credentials, repair infrastructure, or
  enforce filesystem permissions outside the agent prompts and host configuration.
- Pane suitability requires inspection of live Herdr state and cannot be decided from JSON alone.
- Subjective, experiential, clinical, financial, safety, and other declared human decisions remain
  manual acceptance boundaries.

## License

MIT. See [LICENSE](LICENSE).
