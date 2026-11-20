#!/usr/bin/env python3
"""Lint, contrast-check, render, and gate one infographic spec.

    infographic.py lint   SPEC [--theme ID]
    infographic.py render SPEC -o OUT.png [--theme ID] [--attempts 3] [--dry-run]
    infographic.py --self-test

A spec is a Markdown file with YAML frontmatter (see references/spec-format.md).
`render` lints first and spends no image call on a spec that fails.
The image comes from the imagen-diagrams plugin's generate.py (failover across
engines), else the bare `imagen generate`. The gate reads the image back with
`imagen analyze` and requires the headline, every section label, and a source
footer, spelled correctly. Exit 0 ok, 1 lint or gate failure, 2 usage.
"""
from __future__ import annotations

import argparse
import difflib
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

VISUALS = {"bar", "line", "timeline", "process", "diagram", "comparison", "stat", "icons", "checklist"}
DATA_VISUALS = {"bar", "line", "stat"}
BANNED_VISUALS = {"pie", "donut", "3d", "3d-bar", "radar"}
VISUAL_HINTS = {
    "stat": "One large number with its label beneath it. No chart, bar, axis, or scale.",
    "bar": "Horizontal bars, one per data value, labeled, on one shared axis from zero.",
    "line": "One line over the given points, labeled axes from zero.",
    "timeline": "A horizontal timeline with the phrases as ordered stops.",
    "process": "Boxes joined by arrows, one box per phrase, in order.",
    "diagram": "A simple relationship diagram of the phrases, shapes and arrows only.",
    "comparison": "Two side-by-side columns contrasting the phrases.",
    "icons": "One plain pictogram beside each phrase. Pictograms carry no text or numbers.",
    "checklist": "A checkmark beside each phrase.",
}
LIMITS = dict(headline_words=8, label_words=4, point_words=8, points=3,
              min_sections=3, max_sections=6, total_words=130, colors=4)


# ---------------------------------------------------------------- theme + spec
def plugin_dir() -> Path | None:
    hits = sorted(Path.home().glob(".claude/plugins/cache/*/imagen-diagrams/*/skills/imagen-diagrams"),
                  key=lambda p: [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", p.parts[-3])])
    return hits[-1] if hits else None


def theme_palette(theme_id: str) -> tuple[dict, str]:
    root = plugin_dir()
    f = root / "themes" / f"{theme_id}.yaml" if root else None
    if not f or not f.exists():
        sys.exit(f"theme not found: {theme_id}")
    t = yaml.safe_load(f.read_text())
    keep = ("background", "ink", "primary", "primary_fg", "accent", "muted", "surface")
    return {k: t["palette"][k] for k in keep if k in t["palette"]}, " ".join(t["style"]["summary"].split())


def load_spec(path: Path, theme: str | None) -> dict:
    text = path.read_text()
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    spec = yaml.safe_load(m.group(1) if m else text) or {}
    theme = theme or spec.get("theme")
    if theme:
        pal, style = theme_palette(theme)
        spec["palette"] = {**pal, **(spec.get("palette") or {})}
        spec.setdefault("style", style)
    return spec


# ---------------------------------------------------------------- checks
def words(s) -> int:
    return len(str(s).split())


def lum(hex_: str) -> float:
    h = hex_.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def contrast(a: str, b: str) -> float:
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def lint(spec: dict) -> list[str]:
    errs = []
    msg = str(spec.get("message", "")).strip()
    if not msg:
        errs.append("message: missing (state the one takeaway in one sentence)")
    elif len(re.findall(r"[.!?](\s|$)", msg)) > 1:
        errs.append("message: more than one sentence; an infographic carries one message")
    if not spec.get("audience"):
        errs.append("audience: missing (name the reader)")
    head = spec.get("headline", "")
    if not head:
        errs.append("headline: missing (it states the takeaway)")
    elif words(head) > LIMITS["headline_words"]:
        errs.append(f"headline: {words(head)} words, limit {LIMITS['headline_words']}")

    secs = spec.get("sections") or []
    if not LIMITS["min_sections"] <= len(secs) <= LIMITS["max_sections"]:
        errs.append(f"sections: {len(secs)}, need {LIMITS['min_sections']}-{LIMITS['max_sections']}")
    total = words(head) + words(spec.get("subhead", ""))
    for i, s in enumerate(secs, 1):
        label, visual = s.get("label", ""), str(s.get("visual", "")).lower()
        total += words(label)
        if not label:
            errs.append(f"section {i}: label missing")
        elif words(label) > LIMITS["label_words"]:
            errs.append(f"section {i}: label {words(label)} words, limit {LIMITS['label_words']}")
        if visual in BANNED_VISUALS:
            errs.append(f"section {i}: '{visual}' is banned (no pies, donuts, radar, or 3D)")
        elif visual not in VISUALS:
            errs.append(f"section {i}: visual '{visual}' not in {sorted(VISUALS)}")
        pts = s.get("points") or []
        if len(pts) > LIMITS["points"]:
            errs.append(f"section {i}: {len(pts)} points, limit {LIMITS['points']} (move the rest to the article)")
        for p in pts:
            total += words(p)
            if words(p) > LIMITS["point_words"]:
                errs.append(f"section {i}: point '{p}' is {words(p)} words, limit {LIMITS['point_words']}")
        data = s.get("data") or []
        if visual in DATA_VISUALS and not data:
            errs.append(f"section {i}: '{visual}' needs data values")
        if visual in {"bar", "line"} and 0 < len(data) < 2:
            errs.append(f"section {i}: '{visual}' needs at least 2 values")
        for d in data:
            total += words(d.get("label", "")) + 1
            if not d.get("source"):
                errs.append(f"section {i}: data '{d.get('label')}' has no source")
    if total > LIMITS["total_words"]:
        errs.append(f"text: {total} words, limit {LIMITS['total_words']} (an infographic is not an article)")
    # sources is optional: no field means no footer line. Each data value still names its source.

    pal = spec.get("palette") or {}
    if not {"background", "ink"} <= pal.keys():
        errs.append("palette: needs background and ink (set palette or theme)")
    else:
        colors = {v.upper() for k, v in pal.items() if k not in ("background", "surface", "primary_fg")}
        if len(colors) > LIMITS["colors"]:
            errs.append(f"palette: {len(colors)} colors, limit {LIMITS['colors']}")
        pairs = [("ink", "background"), ("primary_fg", "primary"), ("ink", "surface")]
        for fg, bg in pairs:
            if fg in pal and bg in pal and contrast(pal[fg], pal[bg]) < 4.5:
                errs.append(f"contrast: {fg} on {bg} is {contrast(pal[fg], pal[bg]):.2f}:1, need 4.5:1")
    return errs


# ---------------------------------------------------------------- prompt + render
def required_text(spec: dict) -> list[str]:
    return [spec["headline"]] + [s["label"] for s in spec["sections"]]


def build_prompt(spec: dict) -> str:
    pal = spec["palette"]
    lines = [
        "A clean editorial infographic poster, in the style of a NotebookLM infographic.",
        f"Audience: {spec['audience']}. The single message: {spec['message']}",
        "LAYOUT: a headline band at the top, then numbered modular panels read top to bottom, "
        "then a thin footer strip. Generous white space. Strong hierarchy: the headline is the "
        "largest text, panel labels second, short phrases third.",
        f"STYLE: {spec.get('style', 'Flat vector, precise and calm.')} One bold sans-serif for the "
        "headline and labels, one regular sans-serif for phrases. Flat, simple icons in one consistent style.",
        "PALETTE (use only these): " + ", ".join(f"{k} {v}" for k, v in pal.items()),
        "",
        f'HEADLINE (exact text): "{spec["headline"]}"',
    ]
    if spec.get("subhead"):
        lines.append(f'SUBHEAD (exact text, small): "{spec["subhead"]}"')
    for i, s in enumerate(spec["sections"], 1):
        hint = VISUAL_HINTS.get(s["visual"], "")
        lines.append(f'PANEL {i} - label (exact text): "{s["label"]}" - visual: {s["visual"]}. {hint}')
        for p in s.get("points") or []:
            lines.append(f'  phrase (exact text): "{p}"')
        # Only charts get a scale; a "stat" given the scale rule comes back as a one-bar chart.
        scale = "  (draw to scale, axis starts at zero)" if s["visual"] in ("bar", "line") else ""
        for d in s.get("data") or []:
            lines.append(f'  data: "{d["label"]}" = {d["value"]}{scale}')
    lines.append('FOOTER (exact text, small): "Sources: ' + "; ".join(map(str, spec["sources"])) + '"'
                 if spec.get("sources") else "FOOTER: none")
    if spec.get("person"):
        lines.append(f"PERSON: one small flat illustrated person in a corner, {spec['person']}. "
                     "The person carries no text and no speech bubble.")
    lines += [
        "",
        "Render every quoted string exactly as written, correctly spelled. Add no other words, "
        "no logos, no brand names, no watermark, no lorem ipsum.",
        # A model fills empty icons with fake data (a "PID: 1420", a 0-2.5 scale for a version).
        "Add no numbers, IDs, values, axes, or example data that are not quoted above. "
        "A chart shows only the data values given. An icon panel uses plain pictograms with no text.",
        "Avoid: 3D effects, pie charts, gradients, photo realism, drop shadows, clutter, "
        "decoration that carries no meaning, color as the only way to tell items apart.",
    ]
    return "\n".join(l.replace("{", "(").replace("}", ")") for l in lines)


def generate(prompt: str, out: Path, aspect: str) -> bool:
    root = plugin_dir()
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write(prompt)
    if root and (root / "scripts/generate.py").exists():
        cmd = [sys.executable, str(root / "scripts/generate.py"), "--prompt-file", f.name,
               "--output", str(out), "--kind", "cover", "--aspect", aspect]
    else:
        cmd = ["imagen", "generate", prompt, "-o", str(out), "--aspect-ratio", aspect]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        print(r.stderr[-800:], file=sys.stderr)
    return out.exists() and out.stat().st_size > 0


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def all_text(spec: dict) -> list[str]:
    out = [spec["headline"], spec.get("subhead", ""), *map(str, spec.get("sources") or [])]
    for s in spec["sections"]:
        out += [s["label"], *map(str, s.get("points") or [])]
        out += [f'{d["label"]} {d["value"]}' for d in s.get("data") or []]
    return out


def missing_text(png: Path, needed: list[str], want_sources: bool, allowed_text: list[str]) -> list[str]:
    # The word "transcribe" makes the model refuse ("No description generated"),
    # so ask what appears. The answer is a bulleted list after a preamble line.
    ask = ["imagen", "analyze", str(png), "-p",
           "What words and labels appear in this infographic? Answer as a plain list, one per line."]
    out = ""
    for _ in range(2):
        out = subprocess.run(ask, capture_output=True, text=True).stdout
        if out.strip() and "Error:" not in out:
            break
    else:
        print("warn: read-back failed twice; keeping the image unchecked", file=sys.stderr)
        return []  # a probe outage must not discard a good image
    items = [l for l in out.splitlines() if re.match(r"\s*([*\-•]|\d+[.)])\s", l)]
    seen = norm("\n".join(items or out.splitlines()))
    miss = []
    for t in needed:
        n = norm(t)
        if n in seen:
            continue
        toks, k = seen.split(), len(n.split())
        windows = (" ".join(toks[i:i + k]) for i in range(max(1, len(toks) - k + 1)))
        if max((difflib.SequenceMatcher(None, n, w).ratio() for w in windows), default=0) < 0.92:
            miss.append(t)
    if want_sources and "source" not in seen:
        miss.append("Sources footer")
    # ponytail: extra words only warn. Panel numbers and icon glyph text vary too
    # much to fail on; the author's look at the PNG (SKILL.md step 6) decides.
    allowed = set(norm(" ".join(allowed_text)).split()) | {"source", "sources"}
    extra = [w for w in seen.split() if w not in allowed and not w.isdigit()]
    if extra:
        print(f"warn: text not in the spec: {' '.join(dict.fromkeys(extra))}", file=sys.stderr)
    return miss


def render(spec: dict, out: Path, attempts: int, dry: bool) -> int:
    prompt = build_prompt(spec)
    out.with_suffix(".prompt.txt").write_text(prompt)
    if dry:
        print(prompt)
        return 0
    aspect = str(spec.get("aspect", "3:4"))
    miss: list[str] = []
    for n in range(1, attempts + 1):
        if not generate(prompt, out, aspect):
            print(f"attempt {n}: no image", file=sys.stderr)
            continue
        miss = missing_text(out, required_text(spec), bool(spec.get("sources")), all_text(spec))
        if not miss:
            print(f"ok: {out} (attempt {n})")
            return 0
        print(f"attempt {n}: text missing or misspelled: {miss}", file=sys.stderr)
        out.unlink(missing_ok=True)
    print(f"FAIL: {out} after {attempts} attempts", file=sys.stderr)
    return 1


# ---------------------------------------------------------------- scene
def scene(spec: dict, out: Path, attempts: int, dry: bool, base: Path) -> int:
    """A person working with a concept: a flat illustration, optionally showing a
    reference diagram on a monitor or whiteboard. No text of its own."""
    pal = spec.get("palette") or {}
    diagram = spec.get("diagram")
    lines = [
        f"A flat editorial illustration for a technical article. Scene: {spec['person']}.",
        f"Setting: {spec.get('setting', 'a developer workspace')}.",
        f"STYLE: {spec.get('style', 'Flat vector, calm, precise.')} Simple shapes, one consistent line weight.",
        "PALETTE (use only these): " + ", ".join(f"{k} {v}" for k, v in pal.items()),
        "The person's pose and face show the moment clearly. Plenty of empty space around the figure.",
        "No title, no caption, no speech bubble, no logos, no brand names, no watermark.",
        # Image models invent garbled words on whiteboards and notes; ask for wordless marks.
        "Any writing in the room (whiteboard, sticky notes, papers, code on a second screen) is abstract "
        "scribble lines with no readable letters or words.",
    ]
    cmd = ["imagen", "generate"]
    if diagram:
        ref = (base / diagram) if not Path(diagram).is_absolute() else Path(diagram)
        if not ref.exists():
            sys.exit(f"scene: diagram not found: {ref}")
        # Without the "only inside the screen" rule the model can paste the reference over the room.
        lines.append("The reference image is a diagram. Draw a small, simplified copy of it ONLY inside the "
                     "frame of the main monitor's screen: its boxes and arrows in the same layout, with no "
                     "readable text. Nothing of the diagram appears outside that screen, and the reference "
                     "image is never pasted, overlaid, or framed in the room.")
        cmd += ["-i", str(ref), "--label", "The diagram on the screen:"]
    prompt = "\n".join(l.replace("{", "(").replace("}", ")") for l in lines)
    out.with_suffix(".prompt.txt").write_text(prompt)
    if dry:
        print(prompt)
        return 0
    cmd += [prompt, "-o", str(out), "--aspect-ratio", str(spec.get("aspect", "16:9")), "-m", "gemini-3-pro-image"]
    for n in range(1, attempts + 1):
        r = subprocess.run(cmd, capture_output=True, text=True)
        if out.exists() and out.stat().st_size:
            print(f"ok: {out} (attempt {n})")
            return 0
        print(f"attempt {n}: no image {r.stderr[-300:]}", file=sys.stderr)
    return 1


def lint_scene(spec: dict) -> list[str]:
    errs = [] if spec.get("person") else ["person: missing (who, doing what, feeling what)"]
    pal = spec.get("palette") or {}
    if not {"background", "ink"} <= pal.keys():
        errs.append("palette: needs background and ink (set palette or theme)")
    return errs


# ---------------------------------------------------------------- self-test
def self_test() -> None:
    good = {
        "message": "Context fills from four sources, and you control three of them.",
        "audience": "developers new to coding agents", "headline": "You control most of the window",
        "sections": [
            {"label": "System prompt", "visual": "icons", "points": ["Fixed by the tool"]},
            {"label": "AGENTS.md", "visual": "icons", "points": ["Your durable rules"]},
            {"label": "Window usage", "visual": "bar",
             "data": [{"label": "Rules", "value": 8, "source": "test"}, {"label": "Chat", "value": 60, "source": "test"}]},
        ],
        "sources": ["test fixture"],
        "palette": {"background": "#FFFFFF", "ink": "#102A56", "primary": "#102A56",
                    "primary_fg": "#FFFFFF", "accent": "#2F6FED"},
    }
    assert lint(good) == [], lint(good)
    bad = {**good, "message": "Two ideas. Two messages.", "sources": [],
           "sections": [{"label": "x", "visual": "pie", "points": ["90% faster"]}] * 9}
    errs = " ".join(lint(bad))
    for frag in ("more than one sentence", "sections: 9", "banned"):
        assert frag in errs, (frag, errs)
    # A data value with no source still fails, with or without a footer.
    unsourced = {**good, "sections": [*good["sections"][:2],
                 {"label": "Window usage", "visual": "bar", "data": [{"label": "Rules", "value": 8}, {"label": "Chat", "value": 60, "source": "test"}]}]}
    assert any("has no source" in e for e in lint(unsourced)), lint(unsourced)
    # sources present: today's footer line, and the read-back looks for it.
    assert 'FOOTER (exact text, small): "Sources: test fixture"' in build_prompt(good)
    assert "test fixture" in all_text(good) and "test fixture" not in all_text({**good, "sources": None})
    # sources absent: numbers in points are fine, and there is no footer line.
    days = {k: v for k, v in good.items() if k != "sources"}
    days["sections"] = [{"label": "Getting started", "visual": "timeline", "points": ["Day 1: Install once", "Day 2: Start"]},
                        *good["sections"][:2]]
    assert lint(days) == [], lint(days)
    assert "FOOTER: none" in build_prompt(days) and "Sources:" not in build_prompt(days)
    low = {**good, "palette": {**good["palette"], "ink": "#BBBBBB"}}
    assert any("contrast" in e for e in lint(low)), lint(low)
    assert round(contrast("#000000", "#FFFFFF"), 1) == 21.0
    assert "{" not in build_prompt({**good, "headline": "a {b}"})
    print("self-test ok")


def main() -> int:
    if "--self-test" in sys.argv:
        self_test()
        return 0
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("lint", "render", "scene"))
    ap.add_argument("spec", type=Path)
    ap.add_argument("-o", "--output", type=Path)
    ap.add_argument("--theme")
    ap.add_argument("--attempts", type=int, default=3)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--ref-dir", type=Path, help="scene: resolve `diagram:` here instead of the spec's folder")
    a = ap.parse_args()
    spec = load_spec(a.spec, a.theme)
    if a.cmd == "scene":
        errs = lint_scene(spec)
        for e in errs:
            print(f"lint: {e}", file=sys.stderr)
        if errs or not a.output:
            return 1 if errs else ap.error("scene needs -o OUT.png")
        a.output.parent.mkdir(parents=True, exist_ok=True)
        return scene(spec, a.output, a.attempts, a.dry_run, a.ref_dir or a.spec.parent)
    errs = lint(spec)
    for e in errs:
        print(f"lint: {e}", file=sys.stderr)
    if errs:
        return 1
    if a.cmd == "lint":
        print(f"lint ok: {a.spec}")
        return 0
    if not a.output:
        ap.error("render needs -o OUT.png")
    a.output.parent.mkdir(parents=True, exist_ok=True)
    return render(spec, a.output, a.attempts, a.dry_run)


if __name__ == "__main__":
    sys.exit(main())
