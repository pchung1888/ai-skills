"""Tests for revision.py (inject, extract, carry-ids, report) plus the css and vendor checks.

Usage: python test_revision.py [ClassName ...]
With no class names every class runs. The last line is REVISION PY TESTS PASS or REVISION PY TESTS FAIL.
All page text below is made up.
"""
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parents[2]
REVISION_DIR = SKILLS_DIR / "personal-md-to-html" / "revision"
VENDOR_DIR = SKILLS_DIR / "personal-htsw" / "walk" / "revision"
REVISION_PY = REVISION_DIR / "revision.py"
REVISION_CSS = REVISION_DIR / "revision.css"
REVISION_JS = REVISION_DIR / "revision.js"
SIZE_LIMIT_BYTES = 131072
DESIGN_TOKENS = [
    "note-top", "note-bot", "note-ink", "note-edge", "note-muted", "pin", "pin-ink",
    "hi", "ok", "warn", "ui-bg", "ui-ink", "ui-edge", "shadow",
]

PLAIN_PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>Garden Notes</title>
<style>body{margin:0}</style>
</head><body>
<nav class="toc"><a href="#soil">Soil</a></nav>
<section id="soil">
<h2>Soil</h2>
<p>Good soil is <em>dark</em> and <span>crumbly</span>.</p>
<p>Test the soil before planting.</p>
<div class="spacer"><div class="inner"></div></div>
<ul><li>Kitchen scraps</li><li>Dry leaves</li></ul>
<table><caption>Weekly water</caption><thead><tr><th>Plant</th><th>Litres</th></tr></thead>
<tbody><tr><td>Tomato</td><td>8</td></tr></tbody></table>
<pre>row 1: beans</pre>
</section>
<script>var gardenCount = 3;</script>
</body></html>
"""

V1_PAGE = """<!DOCTYPE html>
<html lang="en" data-rev-doc="carry-1a2b3c4d"><head><meta charset="utf-8"><title>Carry</title></head><body>
<section id="intro">
<h1 data-rev-id="intro-h-1">Setup guide</h1>
<p data-rev-id="intro-p-1">Install the widget before you start the demo.</p>
<p data-rev-id="intro-p-2">Check that the lamp turns green after power on.</p>
<p data-rev-id="intro-p-3">Wipe the glass panel with a dry cloth.</p>
</section>
</body></html>
"""

V2_SOURCE_EQUAL = re.sub(r' data-rev-(id|doc)="[^"]*"', "", V1_PAGE)
V2_SOURCE_REPLACED = V2_SOURCE_EQUAL.replace(
    "Install the widget before you start the demo.", "Install the widget first."
)
V2_SOURCE_NEW_AND_RETIRED = V2_SOURCE_EQUAL.replace(
    "<p>Wipe the glass panel with a dry cloth.</p>\n", "<p>Plug in the brand new lamp now.</p>\n"
).replace("<p>Check that the lamp turns green after power on.</p>\n", "")


def annotation_item(item_number, target_id, quote, body="Make this clearer", with_css=True, with_quote=True):
    selector_list = []
    if with_css:
        selector_list.append({"type": "CssSelector", "value": '[data-rev-id="%s"]' % target_id})
    if with_quote:
        selector_list.append({"type": "TextQuoteSelector", "exact": quote, "prefix": "", "suffix": ""})
    item = {
        "id": "urn:uuid:00000000-0000-4000-8000-00000000000%d" % item_number,
        "type": "Annotation",
        "motivation": "editing",
        "created": "2026-01-01T00:00:00Z",
        "modified": "2026-01-01T00:00:00Z",
        "target": {"source": "urn:rev:carry-1a2b3c4d", "selector": selector_list},
        "rev:kind": "p", "rev:section": "intro", "rev:intent": "wording", "rev:state": "open", "rev:status": "new",
    }
    if body is not None:
        item["body"] = {"type": "TextualBody", "format": "text/plain", "purpose": "editing", "value": body}
    return item


def saved_page(item_list, page_text=V1_PAGE):
    annotation_page = {
        "@context": "http://www.w3.org/ns/anno.jsonld",
        "type": "AnnotationPage",
        "rev:doc": "carry-1a2b3c4d",
        "items": item_list,
    }
    block = '<script type="application/ld+json" id="rev-annotations">\n%s\n</script>\n' % json.dumps(annotation_page, indent=2)
    return page_text.replace("</body>", block + "</body>")


def ledger_rows(ledger):
    if isinstance(ledger, list):
        return ledger
    for key in ("rows", "pins", "items"):
        if isinstance(ledger.get(key), list):
            return ledger[key]
    raise AssertionError("ledger has no row list")


class RevisionCase(unittest.TestCase):
    def setUp(self):
        self.workDir = tempfile.TemporaryDirectory()
        self.addCleanup(self.workDir.cleanup)
        self.work = Path(self.workDir.name)

    def write(self, name, text):
        target = self.work / name
        target.write_text(text, encoding="utf-8", newline="\n")
        return target

    def run_revision(self, *args):
        completed = subprocess.run(
            [sys.executable, str(REVISION_PY), *[str(a) for a in args]],
            capture_output=True, text=True, encoding="utf-8",
        )
        return completed.returncode, (completed.stdout + completed.stderr)

    def inject(self, page_text, name="page.html", *extra):
        source = self.write(name, page_text)
        out = self.work / ("out-" + name)
        exit_code, output = self.run_revision("inject", source, "--out", out, *extra)
        self.assertEqual(exit_code, 0, "inject must exit 0, got %s: %s" % (exit_code, output[-200:]))
        self.assertTrue(out.exists(), "inject must write the --out file")
        return source, out, out.read_text(encoding="utf-8"), output


class InjectTests(RevisionCase):
    def test_ids_follow_section_kind_number(self):
        _, _, injected, _ = self.inject(PLAIN_PAGE)
        for expected_id in ("soil-h-1", "soil-p-1", "soil-p-2", "soil-li-1", "soil-li-2", "soil-tbl-1", "soil-row-1", "soil-code-1"):
            self.assertIn('data-rev-id="%s"' % expected_id, injected, "missing id " + expected_id)

    def test_no_text_node_changed(self):
        source, out, _, _ = self.inject(PLAIN_PAGE)
        exit_code, output = self.run_revision("textcheck", source, out)
        self.assertEqual(exit_code, 0, "textcheck exit code")
        self.assertIn("TEXT SAME", output)
        other = self.write("other.html", PLAIN_PAGE.replace("Dry leaves", "Wet leaves"))
        exit_code, output = self.run_revision("textcheck", source, other)
        self.assertNotEqual(exit_code, 0, "textcheck must fail on different text")
        self.assertIn("TEXT DIFF", output)

    def test_second_run_changes_nothing(self):
        _, first_out, first_text, _ = self.inject(PLAIN_PAGE)
        second_out = self.work / "second.html"
        exit_code, output = self.run_revision("inject", first_out, "--out", second_out)
        self.assertEqual(exit_code, 0, "second inject must exit 0: " + output[-200:])
        self.assertEqual(second_out.read_text(encoding="utf-8"), first_text, "inject must be idempotent")

    def test_input_file_is_never_overwritten(self):
        source, _, _, _ = self.inject(PLAIN_PAGE)
        self.assertEqual(source.read_text(encoding="utf-8"), PLAIN_PAGE)

    def test_skipped_tags_get_no_id(self):
        _, _, injected, _ = self.inject(PLAIN_PAGE)
        self.assertGreater(injected.count("data-rev-id="), 0, "inject must stamp some ids first")
        for skipped_start in ("<span", "<em", "<nav", "<script>", '<div class="spacer"', '<div class="inner"', "<style>"):
            index = injected.find(skipped_start)
            self.assertNotEqual(index, -1, "fixture lost " + skipped_start)
            start_tag = injected[index:injected.find(">", index) + 1]
            self.assertNotIn("data-rev-id", start_tag, "skipped tag got an id: " + start_tag)

    def test_html_tag_attributes(self):
        _, _, injected, _ = self.inject(PLAIN_PAGE, "garden.html")
        html_tag = injected[injected.find("<html"):injected.find(">", injected.find("<html")) + 1]
        self.assertRegex(html_tag, r'data-rev-doc="garden-[0-9a-f]{8}"')
        self.assertIn('data-rev-default="on"', html_tag)
        self.assertIn('data-rev-source="garden.html"', html_tag)

    def test_three_data_rev_blocks_in_order(self):
        _, _, injected, _ = self.inject(PLAIN_PAGE)
        for block_name in ("css", "snap", "js"):
            self.assertEqual(len(re.findall(r'data-rev="%s"' % block_name, injected)), 1, "block " + block_name)
        snap_at = injected.find('data-rev="snap"')
        js_at = injected.find('data-rev="js"')
        self.assertLess(injected.find('data-rev="css"'), injected.find("</head>"), "css goes before </head>")
        self.assertLess(snap_at, js_at, "snap goes before js")
        self.assertLess(js_at, injected.find("</body>"), "js goes before </body>")
        self.assertLess(snap_at, injected.find("var gardenCount"), "snap goes before the trailing page script")


class ExtractTests(RevisionCase):
    def extract(self, page_text):
        saved = self.write("saved.html", page_text)
        ledger_file = self.work / "saved.pins.json"
        exit_code, output = self.run_revision("extract", saved, "--out", ledger_file)
        return exit_code, output, ledger_file

    def test_valid_block_writes_ledger(self):
        pins = [
            annotation_item(1, "intro-h-1", "Setup guide"),
            annotation_item(2, "intro-p-1", "Install the widget before you start the demo."),
        ]
        exit_code, output, ledger_file = self.extract(saved_page(pins))
        self.assertEqual(exit_code, 0, output[-200:])
        self.assertIn("ANNOTATIONS VALID: 2", output)
        rows = ledger_rows(json.loads(ledger_file.read_text(encoding="utf-8")))
        self.assertEqual(len(rows), 2, "one ledger row per pin")
        self.assertEqual([row["resolved"] for row in rows], ["id", "id"])

    def test_invalid_block_is_rejected(self):
        pins = [annotation_item(1, "intro-h-1", "Setup guide", body=None)]
        exit_code, output, _ = self.extract(saved_page(pins))
        self.assertNotEqual(exit_code, 0, "a pin with no body value must fail")
        self.assertIn("ANNOTATIONS INVALID", output)

    def test_duplicate_ids_are_rejected(self):
        pins = [annotation_item(1, "intro-h-1", "Setup guide"), annotation_item(1, "intro-p-1", "Install the widget before you start the demo.")]
        exit_code, output, _ = self.extract(saved_page(pins))
        self.assertNotEqual(exit_code, 0, "duplicate annotation ids must fail")
        self.assertIn("ANNOTATIONS INVALID", output)

    def test_missing_id_resolves_by_quote_and_unknown_is_none(self):
        pins = [
            annotation_item(1, "gone-p-9", "Check that the lamp turns green after power on."),
            annotation_item(2, "gone-p-8", "A sentence that is nowhere on the page."),
        ]
        exit_code, output, ledger_file = self.extract(saved_page(pins))
        self.assertEqual(exit_code, 0, output[-200:])
        rows = ledger_rows(json.loads(ledger_file.read_text(encoding="utf-8")))
        self.assertEqual(rows[0]["resolved"], "quote")
        self.assertEqual(rows[1]["resolved"], "none")


class CarryTests(RevisionCase):
    def carry(self, source_text):
        v1_file = self.write("v1.html", V1_PAGE)
        return self.inject(source_text, "v2.html", "--carry-ids-from", v1_file)

    def test_equal_blocks_keep_v1_ids(self):
        _, _, injected, _ = self.carry(V2_SOURCE_EQUAL)
        for kept_id in ("intro-h-1", "intro-p-1", "intro-p-2", "intro-p-3"):
            self.assertIn('data-rev-id="%s"' % kept_id, injected)

    def test_replaced_element_keeps_its_id(self):
        _, _, injected, _ = self.carry(V2_SOURCE_REPLACED)
        self.assertRegex(injected, r'<p data-rev-id="intro-p-1">Install the widget first\.</p>')

    def test_new_element_gets_a_number_never_used(self):
        _, _, injected, _ = self.carry(V2_SOURCE_NEW_AND_RETIRED)
        self.assertRegex(injected, r'<p data-rev-id="intro-p-4">Plug in the brand new lamp now\.</p>')
        self.assertNotIn('data-rev-id="intro-p-2"', injected, "a retired number is never reused")

    def test_retired_ids_are_listed(self):
        _, _, _, output = self.carry(V2_SOURCE_NEW_AND_RETIRED)
        retired_lines = [line for line in output.splitlines() if line.startswith("rev-retired:")]
        self.assertEqual(len(retired_lines), 1, "inject must print one rev-retired line")
        self.assertIn("intro-p-2", retired_lines[0])


class ReportTests(RevisionCase):
    V2_PAGE = V1_PAGE.replace('<p data-rev-id="intro-p-3">Wipe the glass panel with a dry cloth.</p>\n', "")

    def ledger_row(self, pin_id, target_id, verdict):
        return {
            "id": pin_id, "target": target_id, "kind": "p", "section": "intro", "quote": "made up quote",
            "comment": "Make this clearer", "intent": "wording", "resolved": "id", "verdict": verdict, "note": "made up note",
        }

    def report(self, row_list):
        ledger_file = self.write("pins.json", json.dumps(row_list))
        v2_file = self.write("v2.html", self.V2_PAGE)
        exit_code, output = self.run_revision("report", ledger_file, v2_file)
        return exit_code, output

    def test_counts_add_up(self):
        rows = [
            self.ledger_row("urn:a", "intro-h-1", "done"),
            self.ledger_row("urn:b", "intro-p-1", "kept"),
            self.ledger_row("urn:c", "intro-p-3", "orphaned"),
        ]
        exit_code, output = self.report(rows)
        self.assertEqual(exit_code, 0, output[-200:])
        self.assertEqual(output.strip().splitlines()[-1], "REVISE REPORT OK: 3 pins = 1 done, 1 kept, 1 orphaned")

    def test_missing_target_becomes_orphaned_and_is_named(self):
        rows = [
            self.ledger_row("urn:a", "intro-h-1", "done"),
            self.ledger_row("urn:b", "intro-p-3", "done"),
        ]
        exit_code, output = self.report(rows)
        self.assertIn("intro-p-3", output, "the changed target id must be named")
        self.assertEqual(output.strip().splitlines()[-1], "REVISE REPORT OK: 2 pins = 1 done, 0 kept, 1 orphaned")

    def test_dropped_ledger_row_fails(self):
        rows = [self.ledger_row("urn:a", "intro-h-1", "done"), self.ledger_row("urn:a", "intro-p-1", "kept")]
        exit_code, output = self.report(rows)
        self.assertNotEqual(exit_code, 0, "a repeated pin id must fail")
        self.assertTrue(output.strip().splitlines()[-1].startswith("REVISE REPORT FAIL:"))

    def test_missing_verdict_fails(self):
        row_without_verdict = self.ledger_row("urn:a", "intro-h-1", "done")
        del row_without_verdict["verdict"]
        exit_code, output = self.report([row_without_verdict])
        self.assertNotEqual(exit_code, 0, "a pin with no verdict must fail")
        self.assertTrue(output.strip().splitlines()[-1].startswith("REVISE REPORT FAIL:"))


class CssTests(unittest.TestCase):
    def css_text(self):
        self.assertTrue(REVISION_CSS.exists(), "revision.css must exist at " + str(REVISION_CSS))
        return REVISION_CSS.read_text(encoding="utf-8")

    def test_tokens_exist_in_day_and_night(self):
        css_text = self.css_text()
        for theme in ("day", "night"):
            theme_blocks = re.findall(r'html\[data-rev-theme="%s"\][^{]*\{([^}]*)\}' % theme, css_text)
            self.assertTrue(theme_blocks, "no %s theme block" % theme)
            theme_body = "".join(theme_blocks)
            for token in DESIGN_TOKENS:
                self.assertIn("--rev-%s:" % token, theme_body, "token --rev-%s missing in %s" % (token, theme))

    def test_every_selector_is_namespaced(self):
        css_text = re.sub(r"/\*.*?\*/", "", self.css_text(), flags=re.S)
        selector_list = [m.strip() for m in re.findall(r"(?:^|[};])\s*([^{};@]+)\{", css_text)]
        selector_list = [s for s in selector_list if not re.fullmatch(r"(from|to|\d+%)(\s*,\s*(from|to|\d+%))*", s)]
        self.assertTrue(selector_list, "no selectors found")
        for selector_group in selector_list:
            for selector in (part.strip() for part in selector_group.split(",")):
                self.assertTrue(
                    selector.startswith((".rev-", "[data-rev-ui]", "html[data-rev-")),
                    "selector is not namespaced: " + selector,
                )

    def test_runtime_files_stay_under_size_limit(self):
        for runtime_file in (REVISION_JS, REVISION_CSS):
            self.assertTrue(runtime_file.exists(), "missing " + runtime_file.name)
        total_bytes = REVISION_JS.stat().st_size + REVISION_CSS.stat().st_size
        self.assertLess(total_bytes, SIZE_LIMIT_BYTES, "revision.js plus revision.css is %d bytes" % total_bytes)


class VendorTests(unittest.TestCase):
    def test_vendored_copy_is_byte_identical(self):
        for file_name in ("revision.js", "revision.css", "revision.py"):
            source_file = REVISION_DIR / file_name
            vendored_file = VENDOR_DIR / file_name
            self.assertTrue(source_file.exists(), "missing source " + str(source_file))
            self.assertTrue(vendored_file.exists(), "missing vendored copy " + str(vendored_file))
            self.assertEqual(
                hashlib.sha256(source_file.read_bytes()).hexdigest(),
                hashlib.sha256(vendored_file.read_bytes()).hexdigest(),
                file_name + " differs between RM and RV",
            )


ALL_CLASS_NAMES = ["InjectTests", "ExtractTests", "CarryTests", "ReportTests", "CssTests", "VendorTests"]

if __name__ == "__main__":
    selected_names = sys.argv[1:] or ALL_CLASS_NAMES
    unknown_names = [n for n in selected_names if n not in ALL_CLASS_NAMES]
    if unknown_names:
        print("unknown test class: " + ", ".join(unknown_names))
        print("REVISION PY TESTS FAIL")
        sys.exit(2)
    loader = unittest.TestLoader()
    suite = unittest.TestSuite(loader.loadTestsFromTestCase(globals()[n]) for n in selected_names)
    outcome = unittest.TextTestRunner(verbosity=1).run(suite)
    print("REVISION PY TESTS PASS" if outcome.wasSuccessful() else "REVISION PY TESTS FAIL")
    sys.exit(0 if outcome.wasSuccessful() else 1)
