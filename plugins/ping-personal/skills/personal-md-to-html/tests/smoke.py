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
