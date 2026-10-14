#!/usr/bin/env python3
"""md-to-html - render a .md file to a self-contained .html page (arc theme).

v1 entry point. See docs/personal-md-to-html/2026-05-19-md-to-html-spec.md for the full
contract.
"""
from __future__ import annotations

import argparse
import html
import re
import subprocess
import sys
from pathlib import Path

# Path shim so themes.arc.components imports work when running as a script.
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

HERE = _HERE
SHELL_PATH = HERE / "themes" / "arc" / "shell.html"
TOKENS_PATH = HERE / "themes" / "arc" / "tokens.css"
COMPONENTS_PATH = HERE / "themes" / "arc" / "components.css"
VALIDATOR_PATH = HERE / "md-to-html-check.py"

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")

# Graceful ImportError exit so missing dependency reports per spec §7.3.
try:
    from markdown_it import MarkdownIt
    from markdown_it.token import Token
except ImportError:
    sys.stderr.write("missing dependency: pip install markdown-it-py\n")
    sys.exit(3)

from themes.arc.components import timeline as _timeline
from themes.arc.components import keyrows as _keyrows
from themes.arc.components import sketch as _sketch
from themes.arc.components import chart_line as _chart_line
from themes.arc.components import chart_bar as _chart_bar
from themes.arc.components import callout as _callout
from themes.arc.components import kpi as _kpi
from themes.arc.components import rules as _rules
from themes.arc.components import demo_brief as _demo_brief
from themes.arc.components import code_block as _code_block
from themes.arc.components import eyebrow as _eyebrow
from themes.arc.components.pills import transform_pills
from themes.arc.components.accent import apply_h1_accent_word
from themes.arc.components.pilcrow import apply_pilcrow
from themes.arc.components import plan_blocks as _plan_blocks

CUSTOM_BLOCKS = {
    "timeline": _timeline.render,
    "keyrows": _keyrows.render,
    "sketch": _sketch.render,
    "chart-line": _chart_line.render,
    "chart-bar": _chart_bar.render,
    "callout": _callout.render,
    "kpi": _kpi.render,
    "rules": _rules.render,
    "demo-brief": _demo_brief.render,
    "eyebrow": _eyebrow.render,
    **_plan_blocks.RENDERERS,
}

# A page that uses an html-plan block, or sets `interactive: true`, gets the interactive layer:
# the inlined html-plan runtime, sections that open and close, comment boxes, Respond, Copy
# buttons and a Day/Night switch. Other pages render exactly as before.
PLAN_FENCE_RE = re.compile(r"(?m)^\s*```(" + "|".join(re.escape(n) for n in _plan_blocks.NAMES) + r")(\s.*)?$")
VENDOR_DIR = HERE / "vendor" / "html-plan"
ARC_DIR = HERE / "themes" / "arc"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def make_interactive(page: str, title: str = "") -> str:
    """Wrap the body in <main>, each H2 section in <details>, and inline the runtime and layer."""
    head, sep, rest = page.partition("<body>")
    body, sep2, tail = rest.rpartition("</body>")
    # A page with no "# Title" line gets one from the frontmatter title, so it has a page header
    # above the sections and Respond has a title to quote.
    if "<h1" not in body and title:
        h1 = f"<h1>{html.escape(title)}</h1>\n"
        eb = re.match(r'\s*<p class="eyebrow">.*?</p>\s*', body, flags=re.S)
        body = body[:eb.end()] + h1 + body[eb.end():] if eb else h1 + body
    # The "**You asked:** ..." line under the title becomes the card that says what the page answers.
    body = re.sub(r"<p><strong>You asked:?</strong>:?\s*(.*?)</p>",
                  r'<div class="you-asked"><div class="lbl">You asked</div><div class="q">\1</div></div>', body, count=1, flags=re.S)
    # Each H2 and what follows it, up to the next H2, becomes one <details> that starts open.
    parts = re.split(r"(?=<h2[ >])", body)
    body = parts[0] + "".join(
        re.sub(r"^(<h2.*?</h2>)(.*)$", r'<details class="lvl" open><summary>\1</summary>\2</details>', p, flags=re.S)
        for p in parts[1:])
    # html-plan's CSS goes before the theme so arc headings win; interactive.css goes last so night wins.
    # data-vendor marks the copied runtime, which md-to-html-check skips for its palette check.
    pre = (f"<script>{_read(ARC_DIR / 'interactive-head.js')}</script>\n"
           f'<style data-vendor="html-plan">{_read(VENDOR_DIR / "htmlplan.css")}</style>\n'
           f"<style>{_read(ARC_DIR / 'interactive-skin.css')}</style>\n")
    head = head.replace("<style>", pre + "<style>", 1)
    head = head.replace("</head>", f"<style>{_read(ARC_DIR / 'interactive.css')}</style>\n</head>", 1)
    # data-numbers="off" drops html-plan's section signs; data-feedback="off" hides its own Respond,
    # because interactive.js gives one Respond that also carries html-plan's "+" comments.
    return (head + '<body data-numbers="off" data-feedback="off">\n<main>\n' + body + "</main>\n"
            f"<script>{_read(ARC_DIR / 'interactive.js')}</script>\n"
            f'<script data-vendor="html-plan">{_read(VENDOR_DIR / "htmlplan.js")}</script>\n' + sep2 + tail)


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Strip YAML-compatible frontmatter; return (mapping, body)."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    mapping: dict[str, str] = {}
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        mapping[key.strip()] = value.strip().strip('"').strip("'")
    return mapping, text[m.end():]


def read_md(path: Path) -> str:
    if path.suffix.lower() != ".md":
        sys.stderr.write(f"unsupported extension: {path.suffix}\n")
        sys.exit(2)
    if not path.exists():
        sys.stderr.write(f"input file not found: {path}\n")
        sys.exit(2)
    raw = path.read_bytes()
    if len(raw) > 1_000_000:
        sys.stderr.write(f"input too large: {len(raw)} bytes (cap 1000000)\n")
        sys.exit(2)
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        sys.stderr.write("input not valid UTF-8\n")
        sys.exit(2)


def _swap_fence(tokens: list, i: int, html: str) -> None:
    new = Token("html_block", "", 0)
    new.block = True
    new.content = html
    new.map = tokens[i].map
    tokens[i] = new


def _arc_transform(state, accent_word: str = ""):
    """Core rule: dispatch custom fences, H2 auto-number, H1 accent, pills."""
    # First pass: swap custom fences to html_block so subsequent passes (and
    # the fence renderer in Phase 11) don't try to highlight them as code.
    for i, token in enumerate(state.tokens):
        if token.type == "fence":
            info = (token.info or "").strip().split(maxsplit=1)
            key = info[0] if info else ""
            if key in CUSTOM_BLOCKS:
                if key in _plan_blocks.RENDERERS:
                    # html-plan blocks also read the rest of the info string (```note warn).
                    rest = info[1] if len(info) > 1 else ""
                    _swap_fence(state.tokens, i, _plan_blocks.RENDERERS[key](token.content, rest))
                else:
                    _swap_fence(state.tokens, i, CUSTOM_BLOCKS[key](token.content))

    # Second pass: numbering + accent + pills.
    h2_index = 0
    in_h1 = False
    for i, token in enumerate(state.tokens):
        if token.type == "heading_open" and token.tag == "h1":
            in_h1 = True
            continue
        if token.type == "heading_close" and token.tag == "h1":
            in_h1 = False
            continue
        if token.type == "heading_open" and token.tag == "h2":
            h2_index += 1
            token.attrSet("data-num", f"{h2_index:02d}")
            continue
        if token.type == "inline" and token.children:
            parent_block_type = state.tokens[i - 1].type if i > 0 else ""
            token.children = transform_pills(token.children, parent_block_type)
            if in_h1:
                if accent_word:
                    apply_h1_accent_word(token, accent_word)
                else:
                    for child in token.children:
                        if child.type == "em_open":
                            child.attrSet("class", "accent")
                            break

    # Third pass: pilcrow paragraph detection — must run after the second pass
    # so that pills and accent transforms don't interfere with class assignment.
    apply_pilcrow(state.tokens)


def render_body(md_body: str, accent_word: str = "") -> str:
    md = MarkdownIt("commonmark", {"html": False}).enable("table")

    def _rule(state):
        _arc_transform(state, accent_word=accent_word)

    md.core.ruler.push("arc_transform", _rule)
    md.add_render_rule("fence", _code_block.render_fence)
    return md.render(md_body)


def assemble(title: str, eyebrow: str, body_html: str, code_accent: str | None, theme: str = "arc", accent: str = "") -> str:
    theme_dir = HERE / "themes" / theme
    # tokens.css: use per-theme file, fall back to arc default.
    theme_tokens_path = theme_dir / "tokens.css"
    tokens_path = theme_tokens_path if theme_tokens_path.exists() else TOKENS_PATH
    tokens = tokens_path.read_text(encoding="utf-8")
    # shell.html: use per-theme file, fall back to arc default.
    theme_shell_path = theme_dir / "shell.html"
    shell_path = theme_shell_path if theme_shell_path.exists() else SHELL_PATH
    shell = shell_path.read_text(encoding="utf-8")
    # Per-theme components.css with fallback to arc/components.css. Lets themes
    # that only override tokens.css (e.g. midnight, Phase 9) inherit the full
    # component rule set without re-declaring it or relying on browser @import.
    theme_components = theme_dir / "components.css"
    components_path = theme_components if theme_components.exists() else COMPONENTS_PATH
    components = components_path.read_text(encoding="utf-8")
    if code_accent:
        tokens = re.sub(
            r"--arc-code-path:\s*#[0-9A-Fa-f]{6}\s*;",
            f"--arc-code-path: {code_accent};",
            tokens,
            count=1,
        )
    style = tokens + "\n" + components
    # Task 14: frontmatter accent override — injects after full theme palette so
    # cascade wins without touching any theme file.
    if accent:
        style = style + f"\n:root {{ --arc-accent: {accent}; }}"
    # Frontmatter text is escaped like the body; one pass so a title holding {{BODY}} stays text.
    eyebrow_html = f'<p class="eyebrow">{html.escape(eyebrow)}</p>' if eyebrow else ""
    slots = {"TITLE": html.escape(title or ""), "STYLE": style, "EYEBROW": eyebrow_html, "BODY": body_html}
    return re.sub(r"\{\{(TITLE|STYLE|EYEBROW|BODY)\}\}", lambda m: slots[m.group(1)], shell)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="md-to-html")
    parser.add_argument("input", type=Path)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--theme", default=None)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--code-accent", default=None)
    args = parser.parse_args(argv)

    text = read_md(args.input)
    fm, body_md = parse_frontmatter(text)

    theme = args.theme or fm.get("theme", "arc")
    # Task 13: theme-folder loader. Replace the hard "arc-only" check with a
    # folder-existence check so any themes/<name>/ directory is valid.
    # Reject path-separator chars in theme name so `theme: ..` or `theme: ../x`
    # can't bypass the gate via Path normalization (critic Phase 9 H1).
    if "/" in theme or "\\" in theme or ".." in theme.split("/") or ".." in theme.split("\\") or theme.startswith(".") or theme == "":
        sys.stderr.write(f"invalid theme name: {theme!r}\n")
        return 2
    theme_dir = HERE / "themes" / theme
    if not theme_dir.is_dir():
        sys.stderr.write(f"theme folder not found: themes/{theme}\n")
        return 2

    if args.code_accent and not HEX_RE.match(args.code_accent):
        sys.stderr.write(f"--code-accent must be #RRGGBB: {args.code_accent}\n")
        return 2

    # Task 14: frontmatter accent: "#XXXXXX" override.
    accent = fm.get("accent", "").strip().strip('"').strip("'")
    if accent and not HEX_RE.match(accent):
        sys.stderr.write(f"frontmatter accent must be #RRGGBB: {accent}\n")
        accent = ""  # ignore invalid; don't crash

    title = fm.get("title") or args.input.stem
    eyebrow = fm.get("eyebrow", "")
    accent_word = fm.get("accent_word", "")
    body_html = render_body(body_md, accent_word=accent_word)
    html = assemble(title, eyebrow, body_html, args.code_accent, theme=theme, accent=accent)
    if fm.get("interactive", "").lower() == "true" or PLAN_FENCE_RE.search(body_md):
        html = make_interactive(html, title)

    out_path = args.out or args.input.with_suffix(".html")
    out_path.write_bytes(html.encode("utf-8"))
    print(str(out_path.resolve()))

    if args.check:
        rc = subprocess.run(
            [sys.executable, str(VALIDATOR_PATH), "--input-file", str(out_path)],
        ).returncode
        return 1 if rc != 0 else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
