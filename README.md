# Codex Herdr Orchestrator

![Codex Herdr Orchestrator banner](assets/codex-herdr-orchestrator-banner.png)

Three ready-to-use Codex skills for running focused, bounded workflows in Herdr.

One agent writes. Optional agents watch or review. Nothing runs behind your back.

## Choose your version

| Directory | Includes | Choose this when |
| --- | --- | --- |
| `codex-herdr-sol-luna/` | Sol + Luna | You want the smallest setup |
| `codex-herdr-sol-luna-fable/` | Sol + Luna + Fable | You also want one independent Fable review |
| `codex-herdr-sol-luna-fable-planr/` | Sol + Luna + Fable + Planr | You manage tasks and evidence with Planr |

Each directory works on its own. Copy only the one you need.

## How it works

1. **Sol builds.** Sol is the only agent allowed to change your project.
2. **Luna watches when invited.** The optional sentinel can stop unsafe or runaway work. It has a
   deadline and shuts down with the run.
3. **Tests stay lean.** Temporary probes do not become permanent tests automatically. Only useful,
   stable checks are kept after the behavior is accepted.
4. **Review stays bounded.** Fable and Planr are used only by the variants that include them.
5. **You get a clean handoff.** Changes, validation, and important run evidence are summarized at the
   end.

**Catch aggressively. Commit reluctantly.**

## Safety by default

- Installing a skill starts no watcher, daemon, or background service.
- Luna is optional and read-only.
- Sol remains the single implementation writer.
- The sentinel is opt-in, tied to one run, and time-bounded.
- The test gate uses Git to detect changes, including files created from the shell.
- Existing user changes are preserved as the starting point.

## Install

Clone this repository, then copy one variant into your Codex skills folder:

```bash
cp -R codex-herdr-sol-luna ~/.agents/skills/
```

Then ask Codex to use it:

```text
Use $codex-herdr-sol-luna for this task.
```

Herdr must already be installed for pane-based workflows. The skills themselves add no Python
packages or background services.

## Development

```bash
python3 -m compileall codex-herdr-sol-luna/scripts codex-herdr-sol-luna-fable/scripts codex-herdr-sol-luna-fable-planr/scripts
python3 -m unittest discover -s tests -v
```

See [CHANGELOG.md](CHANGELOG.md) for releases. MIT licensed; see [LICENSE](LICENSE).
