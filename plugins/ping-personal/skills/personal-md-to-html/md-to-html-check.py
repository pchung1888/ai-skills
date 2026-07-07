#!/usr/bin/env python3
"""md-to-html-check - stdlib-only validator. See spec §8.

Implements the seven content checks. Exit codes: 0 pass, 1 fail with detail
lines on stderr, 2 bad invocation.
"""
from __future__ import annotations

import argparse
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

# Check #3 regexes - see plan Appendix B for derivation.
ALLOWED_DECL_RE = re.compile(
    r"--[A-Za-z][A-Za-z0-9_-]*\s*:\s*(#[0-9A-Fa-f]{6}|#[0-9A-Fa-f]{3})\s*[;}]?"
)
ANY_HEX_RE = re.compile(r"#[0-9A-Fa-f]{6}\b|#[0-9A-Fa-f]{3}\b")
VAR_REF_RE = re.compile(r"var\(\s*--[A-Za-z][A-Za-z0-9_\-]*\s*(?:,[^)]*)?\)")

# Check #1 / #2 - external resources.
EXT_STYLESHEET_RE = re.compile(
    r"""<link[^>]+rel\s*=\s*["']stylesheet["'][^>]+href\s*=\s*["']https?://""",
    re.IGNORECASE,
)
EXT_SCRIPT_RE = re.compile(r"""<script[^>]+src\s*=\s*["']https?://""", re.IGNORECASE)

# Check #5 - every <svg> has viewBox.
SVG_OPEN_RE = re.compile(r"<svg\b[^>]*>", re.IGNORECASE)

# Check #6 - at least one custom artifact (class-aware).
# NOTE: `\b` is a regex word boundary (hyphen counts as boundary), not a CSS
# class-name boundary. v1 emitted HTML uses space-delimited class names so
# this is theoretical; documented for future maintainers.
#
# Component → artifact class mapping (one regex per component, Phases 1-8):
#   timeline      → <ol class="arc">           (themes/arc/components/timeline.py)
#   keyrows       → <dl class="keyrows">        (themes/arc/components/keyrows.py)
#   chart-line    → <svg class="chart-line">    (themes/arc/components/chart_line.py)
#   chart-bar     → <svg class="chart-bar">     (themes/arc/components/chart_bar.py)
#   sketch        → <svg class="sketch">        (themes/arc/components/sketch.py)
#   pills         → <span class="pill">         (themes/arc/components/pills.py)
#   callout       → <div class="callout-grid">  (themes/arc/components/callout.py)
#   kpi           → <div class="kpi-row">       (themes/arc/components/kpi.py)
#   rules         → <ol class="rules">          (themes/arc/components/rules.py)
#   demo-brief    → <section class="demo-brief">(themes/arc/components/demo_brief.py)
#   code-eyebrow  → <p class="code-eyebrow">    (themes/arc/components/code_block.py)
#   eyebrow       → <p class="eyebrow">         (themes/arc/components/eyebrow.py)
#   pilcrow       → <p class="pilcrow">         (themes/arc/components/pilcrow.py)
ARTIFACT_RES = [
    re.compile(r'<ol[^>]*class="[^"]*\barc\b[^"]*"', re.IGNORECASE),
    re.compile(r'<dl[^>]*class="[^"]*\bkeyrows\b[^"]*"', re.IGNORECASE),
    re.compile(r'<svg[^>]*class="[^"]*\bchart-line\b[^"]*"', re.IGNORECASE),
    re.compile(r'<svg[^>]*class="[^"]*\bchart-bar\b[^"]*"', re.IGNORECASE),
    re.compile(r'<svg[^>]*class="[^"]*\bsketch\b[^"]*"', re.IGNORECASE),
    re.compile(r'<span[^>]*class="[^"]*\bpill\b[^"]*"', re.IGNORECASE),
    re.compile(r'<div[^>]*class="[^"]*\bcallout-grid\b[^"]*"', re.IGNORECASE),
    re.compile(r'<div[^>]*class="[^"]*\bkpi-row\b[^"]*"', re.IGNORECASE),
    re.compile(r'<ol[^>]*class="[^"]*\brules\b[^"]*"', re.IGNORECASE),
    re.compile(r'<section[^>]*class="[^"]*\bdemo-brief\b[^"]*"', re.IGNORECASE),
    re.compile(r'<p[^>]*class="[^"]*\bcode-eyebrow\b[^"]*"', re.IGNORECASE),
    re.compile(r'<p[^>]*class="[^"]*\beyebrow\b[^"]*"', re.IGNORECASE),
    re.compile(r'<p[^>]*class="[^"]*\bpilcrow\b[^"]*"', re.IGNORECASE),
]

SIZE_CAP = 512_000  # 500 KB per spec §4 / §8.1 #4


def check_hex_palette_only(html: str) -> list[str]:
    """Spec §8.1 #3. Returns list of failing line snippets."""
    failures = []
    for ln, line in enumerate(html.splitlines(), 1):
        # 1. Identify allowed-declaration hex spans.
        consumed_spans = [m.span(1) for m in ALLOWED_DECL_RE.finditer(line)]
        # 2. Mask var(...) substrings (same length, so offsets don't shift).
        masked = VAR_REF_RE.sub(lambda m: " " * (m.end() - m.start()), line)
        # 3. Mask the consumed declaration hexes.
        for s, e in consumed_spans:
            masked = masked[:s] + (" " * (e - s)) + masked[e:]
        # 4. Anything left is a violation.
        leftovers = list(ANY_HEX_RE.finditer(masked))
        if leftovers:
            failures.append(
                f"line {ln}: raw hex outside palette declaration: "
                f"{leftovers[0].group(0)} in {line.strip()[:80]}"
            )
    return failures


def check_svg_viewbox(html: str) -> list[str]:
    fails = []
    for m in SVG_OPEN_RE.finditer(html):
        tag = m.group(0)
        if "viewBox=" not in tag:
            fails.append(f"svg without viewBox at offset {m.start()}")
    return fails


def check_artifacts_present(html: str) -> bool:
    return any(rx.search(html) for rx in ARTIFACT_RES)


def check_html_parseable(html: str) -> str | None:
    try:
        HTMLParser().feed(html)
        return None
    except Exception as e:  # noqa: BLE001
        return f"HTMLParser raised: {e}"


def run_checks(html: str, size_bytes: int) -> list[str]:
    fails: list[str] = []
    if EXT_STYLESHEET_RE.search(html):
        fails.append("  [1] external stylesheet detected")
    if EXT_SCRIPT_RE.search(html):
        fails.append("  [2] external script detected")
    for f in check_hex_palette_only(html):
        fails.append(f"  [3] {f}")
    if size_bytes > SIZE_CAP:
        fails.append(f"  [4] file size: {size_bytes} bytes (cap {SIZE_CAP})")
    for f in check_svg_viewbox(html):
        fails.append(f"  [5] {f}")
    if not check_artifacts_present(html):
        fails.append("  [6] no custom artifact (timeline/keyrows/chart-*/sketch/pill/callout-grid/kpi-row/rules/demo-brief/code-eyebrow/eyebrow/pilcrow)")
    err = check_html_parseable(html)
    if err:
        fails.append(f"  [7] {err}")
    return fails


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="md-to-html-check")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--input-file", type=Path)
    g.add_argument("--input-string")
    p.add_argument("--palette", type=Path, default=None)  # accepted; not yet used by v1
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args(argv)

    if args.input_file:
        if not args.input_file.exists():
            sys.stderr.write(f"input file not found: {args.input_file}\n")
            return 2
        raw = args.input_file.read_bytes()
        html = raw.decode("utf-8")
        size = len(raw)
    else:
        html = args.input_string
        size = len(html.encode("utf-8"))

    fails = run_checks(html, size)
    if fails:
        if not args.quiet:
            sys.stderr.write("md-to-html-check: FAIL\n")
            for line in fails:
                sys.stderr.write(line + "\n")
        return 1
    if not args.quiet:
        sys.stdout.write("md-to-html-check: PASS\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
