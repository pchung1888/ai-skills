"""Pin list group title must print once when a heading holds its text twice.

A split-text animation leaves two copies of a heading in textContent: a screen-reader copy and the
visible word spans, with different case or spacing. Made-up content only.
Run: python -m unittest tests.test_group_label (from the personal-md-to-html folder).
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parents[2]
REVISION_PY = SKILLS_DIR / "personal-md-to-html" / "revision" / "revision.py"
DEFAULT_NODE_PATH = "D:/playground/gstack/gstack/node_modules"

# Heading text: same words twice, glued, with different case (copy two is upper case).
PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>Tea Notes</title></head><body>
<section id="brew"><h2>Tea Time  Basics<span>TEA TIME BASICS</span></h2><p>Use water just off the boil.</p></section>
<section id="cold"><h2>Cold Brew<span>cold   brew</span></h2><p>Steep overnight.</p></section>
<section id="plain"><h2>Bora Tea Guide</h2><p>Plain heading stays whole.</p></section>
</body></html>
"""

SCRIPT = r"""
const { chromium } = require("playwright");
(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await (await browser.newContext({ viewport: { width: 1200, height: 900 } })).newPage();
  await page.goto("file:///" + process.argv[2].replace(/\\/g, "/"));
  await page.waitForSelector("html[data-rev-mounted]");
  await page.evaluate(() => {
    document.querySelectorAll("section p").forEach((p) => { const pin = window.__rev.place(p, "click"); pin.text = "n"; pin.state = "hidden"; });
    window.__rev.save();
    document.querySelector('[data-rev-act="list"]').click();
  });
  await page.waitForSelector(".rev-panel-group");
  const labels = await page.evaluate(() => [...document.querySelectorAll(".rev-panel-group")].map((e) => e.textContent));
  await browser.close();
  console.log(JSON.stringify(labels));
})().catch((e) => { console.error(e); process.exit(1); });
"""


class GroupLabelTests(unittest.TestCase):
    def test_doubled_heading_prints_once_even_with_case_and_spacing_drift(self):
        env = dict(os.environ)
        env.setdefault("NODE_PATH", DEFAULT_NODE_PATH)
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "tea.html").write_text(PAGE, encoding="utf-8")
            subprocess.run([sys.executable, str(REVISION_PY), "inject", str(base / "tea.html"), "--out", str(base / "tea.rev.html"), "--default", "on"],
                           check=True, capture_output=True)
            (base / "run.js").write_text(SCRIPT, encoding="utf-8")
            r = subprocess.run(["node", str(base / "run.js"), str(base / "tea.rev.html")], capture_output=True, text=True, env=env, timeout=90)
        self.assertEqual(r.returncode, 0, r.stderr)
        labels = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertEqual(labels, ["Tea Time Basics", "Cold Brew", "Bora Tea Guide"])


if __name__ == "__main__":
    unittest.main()
