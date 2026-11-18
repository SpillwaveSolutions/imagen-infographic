# imagen-infographic

A Claude Code skill that designs and renders NotebookLM-style infographics and flat scene illustrations as PNG files.

- **Infographics:** a headline band, numbered panels, simple icons or mini charts, and a sources footer. The spec is linted before any image is spent, and the text in the result is read back.
- **Scenes:** a flat illustration of a person working with an idea, for example a developer at a desk.

Read `SKILL.md` for the design rules and the workflow, and `references/spec-format.md` for the spec format.

## Install

Copy or clone this folder to `~/.claude/skills/imagen-infographic`.

## Requirements

- The `imagen` CLI for rendering.
- `codex` is optional. It is used for the text read-back when `imagen analyze` gives no answer.
