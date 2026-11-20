# Infographic spec format

A spec is a Markdown file with YAML frontmatter. Name it `<name>.infographic.md`. The body after the frontmatter is free notes for the author, and the script ignores it.

## Fields

| Field | Required | Meaning |
|---|---|---|
| `message` | yes | The one takeaway, as one sentence. It goes to the image model as intent. It is not printed. |
| `audience` | yes | Who reads it, for example "developers new to coding agents". |
| `headline` | yes | The takeaway as printed, 8 words or fewer. |
| `subhead` | no | One short line under the headline. |
| `sections` | yes | 3 to 6 panels, in reading order. |
| `sections[].label` | yes | The panel label, 4 words or fewer. |
| `sections[].visual` | yes | `bar`, `line`, `timeline`, `process`, `diagram`, `comparison`, `stat`, `icons`, or `checklist`. |
| `sections[].points` | no | Up to 3 phrases of 8 words or fewer. |
| `sections[].data` | for `bar`, `line`, `stat` | A list of `{label, value, source}`. `bar` and `line` need at least 2 values. |
| `sources` | no | The footer list of sources. Leave it out for no footer line. Each data value still needs its own `source`. |
| `theme` | one of theme or palette | An imagen-diagrams theme id, for example `arctic-fox`. |
| `palette` | one of theme or palette | Hex colors: `background` and `ink` are required. `primary`, `primary_fg`, `accent`, `muted`, and `surface` are optional. At most 4 colors other than the background. |
| `style` | no | Free text style. A theme fills it. |
| `aspect` | no | `3:4` (default, poster), `4:5`, `1:1`, or `16:9`. |
| `person` | no | One small illustrated person, for example "a developer at a desk, relieved". |

The total printed text (headline, labels, phrases, data labels) must stay at 130 words or fewer.

## Example

```markdown
---
message: OpenCode builds every request from four sources, and the developer controls three of them.
audience: developers who use a terminal coding agent every day
headline: You control most of the window
subhead: What OpenCode sends on every turn
theme: arctic-fox
aspect: "3:4"
person: a developer at a desk, pointing at a checklist
sections:
  - label: System prompt
    visual: icons
    points: ["Set by OpenCode", "Same every turn"]
  - label: AGENTS.md rules
    visual: checklist
    points: ["Your durable rules", "Loaded global, then project"]
  - label: Chat and tool output
    visual: bar
    data:
      - {label: "Rules", value: 4, source: "OpenCode docs: context"}
      - {label: "Chat", value: 55, source: "OpenCode docs: context"}
      - {label: "Tool output", value: 41, source: "OpenCode docs: context"}
  - label: Compaction
    visual: process
    points: ["Old turns become a summary", "Rules in AGENTS.md survive"]
sources: ["opencode.ai/docs (OpenCode 2.3.0)"]
---

Notes: the bar values are percentages of one example session. Say so in the article caption.
```

## Scene spec

Name it `<name>.scene.md`. Only `person` and a theme or palette are required.

```markdown
---
person: a frustrated developer at a desk, hands on head, after the agent forgot an earlier decision
setting: a quiet home office at night, one desk lamp
diagram: part-01-mental-model_01_flowchart_chat_budget_imagen.png
theme: arctic-fox
aspect: "16:9"
---
```

## What the lint rejects

- A `message` with more than one sentence, or no `message`.
- No `audience`, or a `headline` longer than 8 words.
- Fewer than 3 or more than 6 sections.
- A label longer than 4 words, more than 3 points, or a point longer than 8 words.
- A `pie`, `donut`, `radar`, or `3d` visual, or a visual outside the list.
- A `bar`, `line`, or `stat` panel with no data, or a data item with no `source`.
- More than 130 printed words, or more than 4 colors.
- Text contrast below 4.5:1 for ink on background, ink on surface, or `primary_fg` on `primary`.
