---
name: imagen-infographic
description: Design and render NotebookLM-style infographics (a headline band, numbered modular panels, simple icons or mini charts, a sources footer) and flat scene illustrations of a person working with an idea (a developer at a desk, frustrated or relieved, optionally with a diagram on screen), as PNGs with the imagen CLI. Infographic specs are linted for one message, sourced numbers, restraint, and WCAG contrast before any image is spent, then read back to check that every label is spelled correctly. Use this skill whenever someone wants an infographic, a one-page visual summary, an explainer poster, a visual takeaway for an article, blog post, slide, or newsletter, a personable illustration of a developer, or asks for something like NotebookLM makes, even if they do not say the word infographic. Not for flowcharts or architecture diagrams that come from mermaid source (use imagen-diagrams) or for photos and cover art (use image-gen).
---

# imagen-infographic

A good infographic turns complex information into something clear, memorable, and scannable in seconds. It puts comprehension ahead of decoration. This skill turns that into a repeatable process: write a spec, lint it, render it, and check the text that came back.

## The design rules (read before you write a spec)

1. **One clear message.** You must be able to say the whole piece in one sentence. Write that sentence first, as `message`. The `headline` states the takeaway, so the reader gets the point in about five seconds. Two competing ideas make two infographics, or one article section.
2. **Accurate, credible data.** Use facts from the source material only. Every data value carries a source. The footer lists the sources when the spec has a `sources` field; with no field, the image has no footer line. A misleading scale or a cherry-picked number destroys trust faster than no chart at all.
3. **One named audience.** Match complexity and vocabulary to what that reader already knows. A generic overview helps nobody.
4. **Hierarchy and flow.** Size, contrast, and placement tell the eye where to go: headline, then panel labels, then short phrases. Use a top-to-bottom sequence or a clear modular grid.
5. **The right visual for the data.**
   - `bar` for comparisons.
   - `line` for trends over time.
   - `timeline` or `process` for sequences.
   - `diagram` for relationships.
   - `comparison` for side by side.
   - `stat` for one big number.
   - `icons` or `checklist` for a short list.

   No 3D, no pies with many slices, no decoration that carries no meaning. The lint rejects `pie`, `donut`, `radar`, and `3d`.
6. **Simplicity and restraint.** Keep labels short and phrases shorter. Use 2 or 3 fonts and 2 to 4 colors, with generous white space. If a section needs a paragraph, it belongs in the article, not the infographic.
7. **Accessibility.** Text contrast must be at least 4.5:1, and the script checks it. Never use color as the only way to tell items apart: label them. The image must stay readable on a phone.
8. **Consistency.** Use one icon style, one type system, and even spacing. The prompt asks for this, so do not fight it with mixed instructions.

**Failure modes. Check the spec for these before you render:**
- information overload, or too many topics
- pretty but meaningless decoration
- weak hierarchy that makes the reader hunt for the point
- wrong or distorted charts
- missing sources
- unreadable text

## Workflow

1. **Find the message.** Read the source (an article section, a report, notes). Write the one-sentence `message` and pick the `audience`. If you cannot write one sentence, the material is not ready for an infographic.
2. **Write the spec**, a Markdown file with YAML frontmatter. The format and a full example are in `references/spec-format.md`. Use 3 to 6 panels, each with a short label, a visual type, and at most 3 phrases or a few data points.
3. **Lint it:**
   ```bash
   python3 ~/.claude/skills/imagen-infographic/scripts/infographic.py lint SPEC.md --theme arctic-fox
   ```
   The lint enforces the limits in rules 1, 2, 5, 6, and 7, and it prints one line per problem. Fix the spec, not the limits: each limit is there because past infographics failed without it.
4. **Render:**
   ```bash
   python3 ~/.claude/skills/imagen-infographic/scripts/infographic.py render SPEC.md -o out.png --theme arctic-fox
   ```
   - `--theme` takes any imagen-diagrams theme id, and it fills the palette and style. You can also set `palette:` in the spec.
   - The default aspect ratio is 3:4, a portrait poster. Set `aspect: "16:9"` for a slide.
   - The script writes `out.prompt.txt` next to the image so you can see what was asked. Use `--dry-run` to print the prompt and spend nothing.
5. **The gate.** The script reads the image back with `imagen analyze`. The headline, every panel label, and the sources footer must appear, spelled correctly. The script tries up to 3 times (`--attempts`) and deletes an image that fails, so a failure is a visible gap, not a broken image.
6. **Look at the result yourself.** Open the PNG and check it against the eight rules. The gate checks spelling only. It cannot tell you that the hierarchy is weak or that a chart is out of scale. If the picture fails a rule, change the spec (fewer words, a different visual) and render again.

When you embed the image in an article, give it a caption and a short paragraph that says what it shows. A reader who cannot see the image must still get the message.

## Scenes: a person working with the idea

A scene is a flat illustration of a person at the moment the article describes: a developer scratching their head at a long chat log, relieved when a test passes, sketching a plan on a whiteboard. Scenes make a technical piece personable. A scene can show one of the article's diagrams on a monitor or whiteboard, which ties the person to the concept. Use about one scene per article, at a moment of frustration or relief.

```bash
python3 ~/.claude/skills/imagen-infographic/scripts/infographic.py scene SCENE.md -o scene.png --theme arctic-fox
```

A scene spec is a short frontmatter block (see `references/spec-format.md`): `person` (who, doing what, feeling what), `setting`, an optional `diagram` (a PNG path relative to the spec, sent as a reference image), `theme` or `palette`, and `aspect` (default 16:9). Scenes carry no text of their own, so they have no text gate. Look at each one: the emotion must read at a glance, and the image must have no title, caption, or speech bubble.

## Requirements

- The `imagen` CLI (gemini-imagen) on the PATH, with a working key.
- The imagen-diagrams plugin, for `--theme` and the engine failover in its `generate.py`. Without the plugin the script calls `imagen generate` directly, and you must set `palette:` in the spec.
- Python 3 with PyYAML.

Run `infographic.py --self-test` after you change the script. It checks the lint and contrast rules without making any image call.
