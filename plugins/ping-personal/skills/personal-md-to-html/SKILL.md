---
name: personal-md-to-html
model: sonnet
description: Convert one Markdown file into a single self-contained styled HTML "magazine spread" page using the arc theme (cream paper, brick-orange accent, serif headlines, hollow-circle timeline rails, inline SVG sketches and sparklines). TRIGGER on /personal-md-to-html, "render this with md-to-html", "convert this markdown to a presentation", or natural language pointing at a .md file. Do NOT auto-trigger on reading or editing markdown.
---

# md-to-html

Renders a single `.md` source into a single `.html` page styled like a magazine
spread (theme `arc`: cream paper, brick-orange accent, serif headlines,
hollow-circle timeline rails, inline SVG sketches and sparklines).

## Triggers (spec §2)

- `/personal-md-to-html <path>` — render `<path>` to `<path>.html` next to source.
- `/personal-md-to-html <path> --out <out-path>` — render to a custom path.
- Natural language: "render this with md-to-html" pointing at a `.md` file.

## Quick contract (full spec: docs/personal-md-to-html/2026-05-19-md-to-html-spec.md)

- Input: one `.md` file, UTF-8, ≤ 1 MB. Optional YAML-compatible frontmatter.
- Output: one self-contained `.html` file, UTF-8 no BOM, ≤ 500 KB, no external requests.
- Exit codes: 0 ok · 1 ok-but-validator-failed · 2 input rejected · 3 render failed.

## Usage

```bash
python md-to-html.py examples/claire-arc.md
python md-to-html.py examples/claire-arc.md --out /tmp/out.html
python md-to-html.py examples/claire-arc.md --check
python md-to-html.py examples/claire-arc.md --code-accent "#C67661"
python md-to-html-check.py --input-file examples/claire-arc.html
```

## Custom block dialect

See `themes/arc/README.md` for the full DSL (timeline, keyrows, sketch,
chart-line, chart-bar, inline pills `[[TAG]]`).

---

## Block reference

### Original 5 (shipped with v1 arc theme)

| Block | Description | Syntax |
|---|---|---|
| `timeline` | Hollow-circle vertical rail — milestone list | ` ```timeline ` then YAML list with `date:` + `title:` + `body:` |
| `keyrows` | Two-column key / value grid | ` ```keyrows ` then YAML mapping of label → value pairs |
| `sketch` | Inline SVG diagram (hand-drawn style) | ` ```sketch ` then SVG path commands |
| `chart-line` | Inline SVG sparkline / line chart | ` ```chart-line ` then comma-separated numeric values |
| `chart-bar` | Inline SVG bar chart | ` ```chart-bar ` then comma-separated numeric values |

### Dashboard extension — 9 new blocks (v1, Phases 2-10)

| Block | Description | Syntax |
|---|---|---|
| `callout` | 2-column YAML card grid (label + optional italic quote + body) | ` ```callout ` then YAML list of `{label, quote?, body?}` |
| `kpi` | Flex tile row — label, value, delta (coloured), optional sparkline | ` ```kpi ` then YAML list of `{label, value, delta?, trend?, data?}` |
| `rules` | Numbered card list with YAML columns and per-row notes | ` ```rules ` then YAML `{columns: [...], items: [{data: [...], note?}]}` |
| `demo-brief` | Composite block — eyebrow, title, pills, body, meta key-value table | ` ```demo-brief ` then YAML `{n, title, tier?, tags?, body, meta: {KEY: val}}` |
| `eyebrow` (body-level) | Small-caps accent breadcrumb placed inline in the document body | ` ```eyebrow ` then one plain-text line |
| `[[TAG\|good]]` / `[[TAG\|warn]]` / `[[TAG\|muted]]` | Filled pill variants — green / coral / grey tint | `[[LABEL\|good]]`, `[[LABEL\|warn]]`, `[[LABEL\|muted]]` inline in prose |
| `code-with-path` | `path=` info-string emits a `.eyebrow.code-eyebrow` label above the code block | ` ```python path=some/file.py ` (quote path if it contains spaces) |
| `pilcrow` | Paragraph starting with `¶` renders as italic, indented, accent glyph | `¶ Editorial note here.` as a standalone paragraph |
| heading meta-pill | Trailing `[[TAG]]` or `[[TAG\|variant]]` in a heading floats right as `.pill-meta` | `## Heading text [[STATUS\|good]]` |

---

## Theming

The renderer supports a 3-level theming model (spec §4.2):

**Level 1 — Frontmatter accent override (no new files)**

```yaml
---
accent: "#3E7BFF"
---
```

Injects `:root { --arc-accent: #3E7BFF; }` after the palette via cascade. Every
accent-bearing element (headings, eyebrows, pill outlines, kpi tile headers) picks
up the new colour. Works with any active theme.

**Level 2 — Theme switch**

```yaml
---
theme: midnight
---
```

Loads `themes/midnight/tokens.css` and `themes/midnight/shell.html` instead of arc
defaults. The `arc/components.css` block styles still apply (fallback). `midnight` is
the only bundled non-default theme; it ships as a dark-palette proof.

**Level 3 — Custom theme folder**

Drop `themes/<name>/tokens.css` and `themes/<name>/shell.html` into the skill root.
Set `theme: <name>` in frontmatter. The renderer resolves the folder at runtime; a
missing folder exits with code 2. Component CSS (`arc/components.css`) is shared across
all themes unless a `themes/<name>/components.css` override is present.

Both Level 1 and Level 2 can be combined:

```yaml
---
theme: midnight
accent: "#FF6B35"
---
```

---

## Pipeline workflow

The intended workflow for producing a dashboard-enriched HTML doc:

1. **Run an upstream skill** (`superpowers:writing-plans`, `htsw`, `brainstorming`, etc.)
   to generate the Markdown source document.
2. **Open the Markdown output** and insert dashboard fences where tables, lists, or callouts
   would improve readability. No special tooling — the fences are just fenced code blocks
   with custom language identifiers.
3. **Render with one command:**
   ```bash
   python .claude/skills/personal-md-to-html/personal-md-to-html.py <path>.md
   ```
4. **Validate** (optional but recommended before sharing):
   ```bash
   python .claude/skills/personal-md-to-html/personal-md-to-html-check.py --input-file <path>.html
   ```

**Live example:** `docs/personal-md-to-html/sample-plan-as-dashboard.md` — the md-to-html
implementation plan rendered as a dashboard. All 9 v1 blocks appear in that document.
