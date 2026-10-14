#!/usr/bin/env python3
"""tests/smoke.py - md-to-html smoke harness. Stdlib-only.

Layers per spec §10:
  10.1  validator self-test against examples/claire-arc.html
  10.2  render-diff: render claire-arc.md to tmp, canonicalize both,
        difflib.unified_diff - pass on empty diff
  10.4  six negative tests
"""
from __future__ import annotations

import difflib
import re
import subprocess
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
PY = sys.executable
RENDERER = SKILL / "md-to-html.py"
VALIDATOR = SKILL / "md-to-html-check.py"
GOLDEN_MD = SKILL / "examples" / "claire-arc.md"
GOLDEN_HTML = SKILL / "examples" / "claire-arc.html"


class Canonicalizer(HTMLParser):
    def __init__(self):
        super().__init__()
        self.lines = []
        self.literal_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("pre", "code"):
            self.literal_depth += 1
        sorted_attrs = " ".join(f'{n}="{v or ""}"' for n, v in sorted(attrs))
        suf = (" " + sorted_attrs) if sorted_attrs else ""
        self.lines.append(f"<{tag}{suf}>")

    def handle_endtag(self, tag):
        self.lines.append(f"</{tag}>")
        if tag in ("pre", "code") and self.literal_depth:
            self.literal_depth -= 1

    def handle_data(self, data):
        if self.literal_depth:
            if data:
                self.lines.append(data)
            return
        text = re.sub(r"\s+", " ", data).strip()
        if text:
            self.lines.append(text)

    def handle_comment(self, data):
        if data.lstrip().startswith("md-to-html:"):
            self.lines.append(f"<!--{data}-->")


def canonicalize(html: str) -> list[str]:
    p = Canonicalizer()
    p.feed(html)
    return p.lines


def test_validator_self_test() -> str | None:
    rc = subprocess.run(
        [PY, str(VALIDATOR), "--input-file", str(GOLDEN_HTML), "--quiet"]
    ).returncode
    return None if rc == 0 else f"validator self-test exit {rc}"


def test_render_diff() -> str | None:
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "claire-arc.actual.html"
        rc = subprocess.run(
            [PY, str(RENDERER), str(GOLDEN_MD), "--out", str(out)]
        ).returncode
        if rc != 0:
            return f"renderer exit {rc}"
        actual = canonicalize(out.read_text(encoding="utf-8"))
        expected = canonicalize(GOLDEN_HTML.read_text(encoding="utf-8"))
        diff = list(difflib.unified_diff(expected, actual, "expected", "actual", lineterm=""))
        return None if not diff else "render-diff:\n" + "\n".join(diff[:40])


def _validator_should_fail(html_bytes: bytes, want_check: int) -> str | None:
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
        f.write(html_bytes)
        path = f.name
    try:
        result = subprocess.run(
            [PY, str(VALIDATOR), "--input-file", path],
            capture_output=True, text=True,
        )
        if result.returncode != 1:
            return f"expected exit 1, got {result.returncode}"
        if f"[{want_check}]" not in result.stderr:
            return f"expected [{want_check}] in stderr, got: {result.stderr[:200]}"
        return None
    finally:
        Path(path).unlink(missing_ok=True)


def test_neg_external_stylesheet() -> str | None:
    html = (
        b'<!doctype html><html><head>'
        b'<link rel="stylesheet" href="https://cdn.example.com/x.css">'
        b'<style>:root{--arc-accent:#B83A20;}</style>'
        b'</head><body><span class="pill">x</span></body></html>'
    )
    return _validator_should_fail(html, 1)


def test_neg_oversize() -> str | None:
    pad = b"<!-- " + (b"x" * 520_000) + b" -->"
    html = (
        b'<!doctype html><html><head><style>:root{--arc-accent:#B83A20;}</style></head>'
        b'<body><span class="pill">x</span>' + pad + b'</body></html>'
    )
    return _validator_should_fail(html, 4)


def test_neg_no_artifacts() -> str | None:
    html = (
        b'<!doctype html><html><head><style>:root{--arc-accent:#B83A20;}</style>'
        b'</head><body><h1>plain</h1></body></html>'
    )
    return _validator_should_fail(html, 6)


def test_neg_svg_no_viewbox() -> str | None:
    html = (
        b'<!doctype html><html><head><style>:root{--arc-accent:#B83A20;}</style>'
        b'</head><body><span class="pill">x</span><svg width="10" height="10"></svg>'
        b'</body></html>'
    )
    return _validator_should_fail(html, 5)


def test_neg_wrong_extension() -> str | None:
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        f.write(b"hello")
        path = f.name
    try:
        rc = subprocess.run([PY, str(RENDERER), path]).returncode
        return None if rc == 2 else f"expected renderer exit 2 for .txt, got {rc}"
    finally:
        Path(path).unlink(missing_ok=True)


def test_neg_unsupported_theme() -> str | None:
    with tempfile.NamedTemporaryFile(suffix=".md", delete=False, mode="w", encoding="utf-8") as f:
        f.write("---\ntheme: gothic\n---\n# x\n")
        path = f.name
    try:
        rc = subprocess.run([PY, str(RENDERER), path]).returncode
        return None if rc == 2 else f"expected renderer exit 2 for theme: gothic, got {rc}"
    finally:
        Path(path).unlink(missing_ok=True)


DASHBOARD_DIR = SKILL / "examples" / "dashboard"
DOCS_DIR = SKILL.parent.parent.parent / "docs" / "md-to-html"

# Sentinel: a test fn may return (SKIP, reason) to be SKIPPED (not failed). Used for
# optional golden-pair tests whose golden file has not been created yet -- the test
# auto-activates the day someone adds the fixture.
SKIP = object()


def _golden_pair_test(name: str, base_dir: Path | None = None, optional: bool = False):
    """Factory: returns a test fn that renders <name>.md, diffs against <name>.html,
    and also asserts the validator passes on the output.

    base_dir: directory containing <name>.md and <name>.html; defaults to DASHBOARD_DIR.
    optional: when True and the golden pair is absent, SKIP (pending) instead of FAIL.
    """
    def _test():
        d = base_dir if base_dir is not None else DASHBOARD_DIR
        md = d / f"{name}.md"
        golden = d / f"{name}.html"
        if not md.exists() or not golden.exists():
            if optional:
                return (SKIP, f"golden not created yet: {name}.md / {name}.html under {d}")
            return f"missing fixture: {name}.md or {name}.html"
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / f"{name}.actual.html"
            rc = subprocess.run(
                [PY, str(RENDERER), str(md), "--out", str(out)]
            ).returncode
            if rc != 0:
                return f"renderer exit {rc}"
            actual = canonicalize(out.read_text(encoding="utf-8"))
            expected = canonicalize(golden.read_text(encoding="utf-8"))
            diff = list(difflib.unified_diff(expected, actual, "expected", "actual", lineterm=""))
            if diff:
                return "diff:\n" + "\n".join(diff[:40])
            # Also validate the output
            val_rc = subprocess.run(
                [PY, str(VALIDATOR), "--input-file", str(out)],
                capture_output=True,
            ).returncode
            if val_rc != 0:
                return f"validator exit {val_rc} on rendered output"
            return None
    return _test


PLAN_MD = SKILL / "examples" / "plan-blocks.md"


def _render(md_text: str, cwd: Path) -> str:
    """Render md_text from a temp .md file with cwd as the working folder; return the HTML."""
    md = cwd / "page.md"
    md.write_text(md_text, encoding="utf-8")
    out = cwd / "page.html"
    subprocess.run([PY, str(RENDERER), str(md), "--out", str(out)], cwd=cwd, capture_output=True, check=True)
    return out.read_text(encoding="utf-8")


def test_plan_blocks() -> str | None:
    """Every html-plan block renders, the page goes interactive, passes the validator, stays ASCII."""
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "plan.html"
        if subprocess.run([PY, str(RENDERER), str(PLAN_MD), "--out", str(out)], capture_output=True).returncode:
            return "renderer failed on examples/plan-blocks.md"
        html = out.read_text(encoding="utf-8")
        for tag in ("doc-flow", "doc-calls", "doc-machine", "doc-code", "doc-mock", "doc-note", "doc-ask"):
            if f"<{tag}" not in html:
                return f"missing <{tag}>"
        for needle in ('<script data-vendor="html-plan">', '<style data-vendor="html-plan">', "<main>",
                       'data-feedback="off"', "md2h-comments:", 'data-theme',
                       # Respond must not depend on an <h1> and must show its own errors.
                       "h1 ? h1.textContent : document.title", "Respond could not build the text"):
            if needle not in html:
                return f"interactive layer missing: {needle}"
        if html.count('<details class="lvl" open>') != html.count("<h2"):
            return "not every H2 section is wrapped in <details>"
        if "block skipped" in html:
            return "a demo block was skipped"
        if any(ord(c) > 127 for c in html):
            return "interactive page is not pure ASCII"
        if subprocess.run([PY, str(VALIDATOR), "--input-file", str(out)], capture_output=True).returncode:
            return "validator failed on the interactive page"
    return None


def test_plain_page_stays_plain() -> str | None:
    """A page with no html-plan block and no `interactive: true` gets no runtime."""
    with tempfile.TemporaryDirectory() as td:
        html = _render("# Plain\n\n```keyrows\na : b\n```\n", Path(td))
        return "plain page got the interactive layer" if "data-vendor" in html or "<main>" in html else None


def test_interactive_frontmatter() -> str | None:
    with tempfile.TemporaryDirectory() as td:
        html = _render("---\ninteractive: true\n---\n# Page\n\n## One\n\ntext\n", Path(td))
        return None if 'data-vendor="html-plan"' in html else "interactive: true did not add the layer"


def test_plan_blocks_cannot_break_out() -> str | None:
    """Block text cannot close its <script> early (any case) or open a script-data comment."""
    evil = "</ScRiPt><img src=x onerror=alert(1)>\n<!--<script>"
    md = (f"# P\n\n```flow\na = {evil}\n```\n\n```code-pins\ncode: |\n  {evil.splitlines()[0]}\n  <!--\n```\n")
    with tempfile.TemporaryDirectory() as td:
        html = _render(md, Path(td))
    main = html.split("<main>", 1)[1].split("</main>", 1)[0]
    opens, closes = main.count('<script type="text/plain">'), len(re.findall(r"</script", main, re.I))
    if closes != opens:
        return f"block text closed its <script> early ({opens} opened, {closes} closed)"
    if "<!--" in main:
        return "block text opened a script-data comment"
    return None


def test_model_shaped_blocks() -> str | None:
    """The shapes a model writes without the docs still draw: a plain list as a flow, a note with
    its tone on the fence line, a "- [x]" list as a decision. A page with no "# Title" gets one."""
    md = ("---\ntitle: Page title from frontmatter\ninteractive: true\n---\n## One\n\n"
          "```flow\nFirst step (done)\nSecond step\n```\n\n"
          "```note warn\nPlain text with no YAML.\n```\n\n"
          "```ask\nWhat next?\n- [x] Ship it\n- [ ] Wait\n```\n")
    with tempfile.TemporaryDirectory() as td:
        html = _render(md, Path(td))
    main = html.split("<main>", 1)[1]
    if "block skipped" in main:
        return "a model-shaped block was skipped"
    if "s1 = First step (done)" not in main or "s1 -> s2" not in main:
        return "a plain list did not become a top-to-bottom flow"
    if '<doc-note tone="warn"><strong>Watch out</strong> Plain text with no YAML.' not in main:
        return "a note with its tone on the fence line was not drawn"
    if 'value="o1" checked> Ship it' not in main:
        return "a - [x] list did not become a decision"
    if "<h1>Page title from frontmatter</h1>" not in main:
        return "a page with no # Title did not get one from the frontmatter"
    with tempfile.TemporaryDirectory() as td:
        html = _render("---\ninteractive: true\n---\n# T\n\n**You asked:** how does X work?\n\n## One\n\ntext\n", Path(td))
    if '<div class="you-asked"><div class="lbl">You asked</div><div class="q">how does X work?</div></div>' not in html:
        return "the **You asked:** line did not become the You-asked card"
    return None


def test_code_pins_refuses_unsafe_paths() -> str | None:
    """code-pins reads only files inside the working folder, never a secrets file."""
    with tempfile.TemporaryDirectory() as td:
        cwd = Path(td) / "repo"
        cwd.mkdir()
        (cwd / ".env").write_text("TOKEN=abc\n", encoding="utf-8")
        (Path(td) / "outside.txt").write_text("outside\n", encoding="utf-8")
        for path in ("../outside.txt", ".env"):
            html = _render(f"# P\n\n```code-pins\npath: {path}\nlines: 1-1\n```\n", cwd)
            if "code-pins block skipped" not in html or "TOKEN=abc" in html or "outside\n" in html:
                return f"code-pins read {path}"
        (cwd / "ok.py").write_text("x = 1\n", encoding="utf-8")
        html = _render("# P\n\n```code-pins\npath: ok.py\nlines: 1-1\n```\n", cwd)
        return None if "x = 1" in html else "code-pins did not read a normal file"


TESTS = [
    ("validator_self_test", test_validator_self_test),
    ("render_diff", test_render_diff),
    ("neg_external_stylesheet", test_neg_external_stylesheet),
    ("neg_oversize", test_neg_oversize),
    ("neg_no_artifacts", test_neg_no_artifacts),
    ("neg_svg_no_viewbox", test_neg_svg_no_viewbox),
    ("neg_wrong_extension", test_neg_wrong_extension),
    ("neg_unsupported_theme", test_neg_unsupported_theme),
    ("pos_callout", _golden_pair_test("callout")),
    ("pos_kpi", _golden_pair_test("kpi")),
    ("pos_rules", _golden_pair_test("rules")),
    ("pos_demo_brief", _golden_pair_test("demo-brief")),
    ("pos_eyebrow", _golden_pair_test("eyebrow")),
    ("pos_pill_variants", _golden_pair_test("pill-variants")),
    ("pos_code_with_path", _golden_pair_test("code-with-path")),
    ("pos_pilcrow", _golden_pair_test("pilcrow")),
    ("pos_heading_meta_pill", _golden_pair_test("heading-meta-pill")),
    # Phase 9 — theme system
    ("pos_midnight", _golden_pair_test("midnight")),
    ("pos_accent_override", _golden_pair_test("accent-override")),
    # htsw-presentation: html-plan blocks and the interactive layer
    ("pos_plan_blocks", test_plan_blocks),
    ("pos_plain_page_stays_plain", test_plain_page_stays_plain),
    ("pos_interactive_frontmatter", test_interactive_frontmatter),
    ("neg_code_pins_unsafe_paths", test_code_pins_refuses_unsafe_paths),
    ("neg_plan_blocks_script_breakout", test_plan_blocks_cannot_break_out),
    ("pos_model_shaped_blocks", test_model_shaped_blocks),
    # Phase 10 — pipeline showcase (lives in docs/personal-md-to-html/, not examples/dashboard/)
    ("pos_sample_plan_as_dashboard", _golden_pair_test("sample-plan-as-dashboard", base_dir=DOCS_DIR, optional=True)),
]


def main() -> int:
    failed = 0
    skipped = 0
    for name, fn in TESTS:
        res = fn()
        if isinstance(res, tuple) and res and res[0] is SKIP:
            sys.stdout.write(f"SKIP {name}: {res[1]}\n")
            skipped += 1
        elif res:
            sys.stderr.write(f"FAIL {name}: {res}\n")
            failed += 1
        else:
            sys.stdout.write(f"PASS {name}\n")
    passed = len(TESTS) - failed - skipped
    sys.stdout.write(f"\n{passed}/{len(TESTS)} passed, {skipped} skipped, {failed} failed\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
