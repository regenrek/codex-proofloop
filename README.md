# Codex Herdr Orchestrator

Three standalone Codex skills for running clear, bounded multi-agent workflows in Herdr.

## Choose a version

| Directory | Includes | Best when |
| --- | --- | --- |
| `codex-herdr-sol-luna/` | Sol + Luna | You want the smallest workflow |
| `codex-herdr-sol-luna-fable/` | Sol + Luna + Fable | You also have Fable for one independent review |
| `codex-herdr-sol-luna-fable-planr/` | Sol + Luna + Fable + Planr | Your tasks and evidence live in Planr |

Each directory is complete by itself. Pick one; you do not need the other tools or variants.

## Install

Copy the directory you want into your Codex skills folder. For example:

```bash
cp -R codex-herdr-sol-luna ~/.agents/skills/
```

Then ask Codex to use it:

```text
Use $codex-herdr-sol-luna for this task.
```

Herdr must already be installed and running. Each skill includes project templates and a small
dependency-free validator.

## Check the repository

```bash
python3 -m unittest discover -s tests -v
```

MIT licensed. See [LICENSE](LICENSE).
