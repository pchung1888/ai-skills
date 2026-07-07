# arc theme — custom block DSL reference

The `arc` theme adds six Markdown extensions on top of standard CommonMark:

- `timeline` fence — vertical beat list with hollow-circle rail
- `keyrows` fence — small-caps definition list
- `sketch` fence — wireframe sketches via inline SVG
- `chart-line` fence — CSV → polyline sparkline SVG
- `chart-bar` fence — CSV → horizontal bars SVG
- `[[TAG]]` inline — pill / pill-meta tag

Plus two H1/H2 transforms:

- Frontmatter `accent_word: ARC` wraps the first match of `ARC` in `<em class="accent">` inside H1 (no `*…*` needed).
- All `<h2>` headings get `data-num="01"`, `"02"`, … in document order.

## timeline (spec §6.1)

```timeline
T+0:00 — Setup — "send me anything"
"You can drop a paragraph or a paste; we'll do the rest."

T+0:30 — Frame the brief
"Three minutes — here's what I heard."
```

- Beats are separated by blank lines.
- First line of each beat: `<timestamp> — <title>` (em-dash U+2014). The first em-dash splits timestamp from title; subsequent em-dashes are part of the title.
- Optional second line: a quote, emitted inside `<em>` and `<p class="quote">`.
- Output: `<ol class="arc timeline"><li>…</li>…</ol>`.

## keyrows (spec §6.5)

```keyrows
WHY HER : She has range
VISUAL : Cinematic palette
RISK : Schedule pressure
```

- Delimiter is the literal ` : ` (space-colon-space).
- Output: `<dl class="keyrows"><dt>why her</dt><dd>She has range</dd>…</dl>`. CSS handles the small-caps.

## sketch (spec §6.2)

```sketch
box "Header" w=320 h=40
divider
box "Body block" w=320 h=120
button "Submit" w=120 h=36
```

- Items stack vertically. Output is one `<svg class="sketch" viewBox=…>` with `<rect>`/`<line>`/`<text>` children.
- Colors are theme tokens (`var(--arc-paper)`, `var(--arc-rule)`, `var(--arc-ink)`); no raw hex.

## chart-line (spec §6.3)

```chart-line
Jan,12
Feb,18
Mar,22
Apr,31
May,44
```

- Two-column CSV (label, value). Optional header (auto-detected: row 1 is a header iff column 2 doesn't parse as float).
- Output: `<svg class="chart-line" viewBox="0 0 320 80">` with one `<polyline>` in `--arc-accent`, dot markers, x-axis labels.

## chart-bar (spec §6.4)

```chart-bar
Pilot,20
Creator cut,35
Studio plan,55
```

- Same CSV grammar as `chart-line`. Output: `<svg class="chart-bar" viewBox="0 0 320 H">` with one `<rect>` bar per row.

## Inline pills (spec §6.6)

`[[A-TIER · MOST CINEMATIC]]` becomes `<span class="pill">A-TIER · MOST CINEMATIC</span>`.

If the pill is the **last non-whitespace token of a paragraph**, it additionally gets class `pill-meta` and floats right.
Pills inside headings, list items, etc. do NOT get `pill-meta`.

## Code blocks (spec §6.9)

Standard fenced code (` ```python `) is rendered as `<pre><code class="language-python">…</code></pre>` with two server-side regex highlights:

- `code-path` wraps path-like tokens (`./foo/bar.py`, `D:\…`).
- `code-comment` wraps trailing line comments (`# …`, `-- …`).

Known trade-off (v1): `#` inside a quoted string may be mis-classified as a comment.
