"""Regression tests for the review fix-now rows and the placement time in revision.js.

Usage: python test_revision_fixes.py
Needs Node with Playwright: set NODE_PATH to a node_modules folder that holds playwright.
Example: NODE_PATH=D:/playground/gstack/gstack/node_modules
Each test drives headless Chromium on a made-up page built with revision.py inject.
The last line is REVISION FIX TESTS PASS or REVISION FIX TESTS FAIL.
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

PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>Tea Notes</title></head><body>
<section id="brew"><h2>Brewing</h2><p>Use water just off the boil.</p><p>Steep for three minutes.</p></section>
</body></html>
"""

PAGE_T96 = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>Tea Notes</title></head><body>
<nav><a href="#brew">Brewing</a> <a href="#serve">Serving</a></nav>
<section id="brew"><h2>Brewing</h2><p>Use water just off the boil.</p><p>Steep for three minutes.</p>
<details class="lvl" open><summary>More</summary><p>Use a warm pot.</p></details>
<aside><p>Tip one.</p><p>Tip two.</p></aside></section>
<section id="serve"><h2>Serving</h2><p>Pour slowly.</p><p>Serve warm.</p></section>
</body></html>
"""

PAGE_T97 = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>Tea Notes</title>
<style>body{margin:0}p{margin:0 0 0 40px;width:300px}#heading{position:absolute;left:420px;top:100px;width:180px;margin:0}
#ta,#tb{width:60px;height:10px;font-size:8px;line-height:10px;margin-left:150px}#gap{height:2000px}</style></head><body>
<section id="near"><aside><p id="near1">Near the top of the page.</p><p id="near2">A second line.</p></aside></section>
<h2 id="heading">Lower heading</h2>
<section id="edge"><p id="edge1">Pins stack beside this line.</p></section>
<section id="tiny"><p id="ta">A</p><p id="tb">B</p></section>
<div id="gap"></div>
<section id="far"><p id="far1">Far below the fold.</p></section>
<section id="keepsec"><p id="keep1">Keep this one open.</p></section>
</body></html>
"""

PAGE_T105 = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>Tea Notes</title>
<style>body{margin:0;height:700px}#card{position:absolute;left:20px;top:20px;width:1150px;height:100px;margin:0}
#box{position:absolute;left:20px;top:130px;width:600px;height:60px}#save{position:absolute;left:20px;top:200px;width:120px;height:30px}</style></head><body>
<p id="card">A wide card with a comment box and a save button right under it.</p>
<textarea id="box"></textarea><button id="save">Save comment</button>
</body></html>
"""

# The browser script prints one JSON object on its last line. SAVED is the exported page path.
SCRIPT = r"""
const { chromium } = require("playwright");
const [mode, pagePath, savedPath] = process.argv.slice(2);
const url = (p) => "file:///" + p.replace(/\\/g, "/");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
(async () => {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1200, height: 900 }, acceptDownloads: true });
  const page = await ctx.newPage();
  const out = {};
  const open = async (p) => { await page.goto(url(p)); await page.waitForSelector("html[data-rev-mounted]"); };
  const addPin = () => page.evaluate(() => {
    const p = document.querySelectorAll("section p")[0];
    const pin = window.__rev.place(p, "click");
    pin.text = "Say boiling point"; pin.state = "open"; window.__rev.save();
    return pin.id;
  });
  if (mode === "dirty") {
    await open(pagePath);
    const q = () => page.evaluate(() => document.querySelector('[data-rev-act="save"]').hasAttribute("data-dirty"));
    out.dirtyAtStart = await q();
    await addPin();
    out.dirtyAfterPin = await q();
  } else if (mode === "time") {
    await open(pagePath);
    await page.evaluate(() => { window.__ev = []; document.addEventListener("rev:placed", (e) => window.__ev.push({ t0: e.detail.t0, t1: e.detail.t1 })); });
    const target = page.locator("section p").first();
    await target.click({ button: "right" });
    await page.waitForSelector("#rev-layer .rev-note textarea");
    out.focusIsTextarea = await page.evaluate(() => document.activeElement && document.activeElement.tagName === "TEXTAREA");
    out.ev = await page.evaluate(() => window.__ev[0]);
  } else if (mode === "stack") {
    await open(pagePath);
    await page.evaluate(() => {
      const p = document.querySelectorAll("section p")[0];
      for (let i = 0; i < 3; i++) { const pin = window.__rev.place(p, "click"); pin.text = "Stacked note number " + i + " with some words"; pin.state = "open"; }
      window.__rev.save(); window.__rev.sync();
    });
    await sleep(900);
    out.stack = await page.evaluate(() => {
      const notes = [...document.querySelectorAll("#rev-layer .rev-note")];
      // layout boxes: the post-its are tilted, so bounding rects of neighbours can touch
      const rects = notes.map((n) => { const l = parseFloat(n.style.left), t = parseFloat(n.style.top); return { left: l, top: t, right: l + n.offsetWidth, bottom: t + n.offsetHeight }; });
      let overlap = 0;
      for (let i = 0; i < rects.length; i++) for (let j = i + 1; j < rects.length; j++) {
        const a = rects[i], b = rects[j];
        if (!(a.right <= b.left || b.right <= a.left || a.bottom <= b.top || b.bottom <= a.top)) overlap++;
      }
      const origins = notes.map((n) => {
        const pin = document.querySelector('#rev-layer .rev-pin[data-rev-pin="' + window.__rev.state.pins[notes.indexOf(n)].id + '"]');
        const m = n.style.getPropertyValue("--rev-ox").split(" ").map((v) => parseFloat(v));
        return { oy: m[1], want: parseFloat(pin.style.top) - parseFloat(n.style.top) + 11 };
      });
      return { count: notes.length, overlap, origins };
    });
  } else if (mode === "foldload") {
    await open(pagePath);
    await page.evaluate(() => {
      const p = document.querySelectorAll("section p")[0];
      const a = window.__rev.place(p, "click"); a.text = "Plain note"; a.state = "open";
      const b = window.__rev.place(p, "click"); b.text = "Kept note"; b.state = "open";
      window.__rev.save(); window.__rev.sync();
    });
    await page.evaluate(() => {
      const note = [...document.querySelectorAll("#rev-layer .rev-note")][0];
      const kp = [...note.querySelectorAll("button")].find((x) => x.textContent === "Keep open");
      kp.click();
      window.__rev.flush();
    });
    await page.evaluate(() => { for (const p of window.__rev.state.pins) p.state = "open"; window.__rev.save(); window.__rev.flush(); });
    await page.reload();
    await page.waitForSelector("html[data-rev-mounted]");
    await sleep(500);
    out.fold = await page.evaluate(() => ({ states: window.__rev.state.pins.map((p) => p.state), notes: document.querySelectorAll("#rev-layer .rev-note").length }));
  } else if (mode === "sticky") {
    await open(pagePath);
    await page.evaluate(() => {
      const tb = document.querySelector("#rev-toolbar"), r = tb.getBoundingClientRect();
      document.body.style.minHeight = "3000px"; const d = document.createElement("div");
      d.style.cssText = "position:sticky;top:0;margin-bottom:-100vh;width:80px;height:100vh;z-index:1;background:#ccc";
      document.body.insertBefore(d, document.body.firstChild);
      d.style.marginLeft = (r.left - 20 - d.getBoundingClientRect().left) + "px";
      window.dispatchEvent(new Event("resize"));
    });
    await sleep(300);
    out.stickyLeft = await page.evaluate(() => document.querySelector("#rev-toolbar").style.left);
  } else if (mode === "scroll") {
    await open(pagePath);
    await page.evaluate(() => { document.body.style.minHeight = "4000px"; window.__tb = document.querySelector("#rev-toolbar"); window.__tb.style.left = "123px"; });
    await page.evaluate(() => window.scrollTo(0, 500));
    await sleep(300);
    out.leftAfterScroll = await page.evaluate(() => window.__tb.style.left);
  } else if (mode === "reload") {
    await open(pagePath);
    await addPin();
    await page.evaluate(() => window.__rev.flush());
    await page.reload();
    await page.waitForSelector("html[data-rev-mounted]");
    out.dirtyAfterReload = await page.evaluate(() => document.querySelector('[data-rev-act="save"]').hasAttribute("data-dirty"));
  } else if (mode === "reloadsaved") {
    await open(savedPath);
    await page.evaluate(() => window.__rev.flush());
    await page.reload();
    await page.waitForSelector("html[data-rev-mounted]");
    out.dirtyAfterReload = await page.evaluate(() => document.querySelector('[data-rev-act="save"]').hasAttribute("data-dirty"));
  } else if (mode === "undo2") {
    await open(pagePath);
    await page.evaluate(() => {
      const section = document.querySelector("section");
      const extra = document.createElement("p"); extra.textContent = "Serve warm."; section.appendChild(extra);
      window.__rev.stampIds && window.__rev.stampIds();
    });
    await page.evaluate(() => {
      const ps = document.querySelectorAll("section p");
      for (let i = 0; i < 3; i++) { const pin = window.__rev.place(ps[i], "click"); pin.text = "Note " + i; pin.state = "hidden"; }
      window.__rev.save();
    });
    const del = async (n) => {
      await page.locator("#rev-layer .rev-pin").nth(n).click();
      await page.locator("#rev-layer .rev-note button[data-danger]").click();
      await page.locator("#rev-layer .rev-note button", { hasText: /^Yes$/ }).click();
      await sleep(450);
    };
    await del(2);
    // keep the first delete's Undo button; a detached button still runs its own handler
    const firstUndo = await page.evaluateHandle(() => [...document.querySelectorAll("button")].find((b) => b.textContent === "Undo"));
    await del(0);
    await page.evaluate((b) => b.click(), firstUndo);
    out.after = await page.evaluate(() => window.__rev.state.pins.map((p) => p.text));
  } else if (mode === "hide") {
    await open(pagePath);
    await page.evaluate(() => window.__rev.place(document.querySelectorAll("section p")[0], "click"));
    await page.locator("#rev-layer .rev-note textarea").fill("Say boiling point");
    await page.locator("#rev-layer .rev-note button", { hasText: /^Save$/ }).click();
    await page.waitForSelector("#rev-layer .rev-note .rev-note-text");
    out.after = await page.evaluate(async () => {
      const pin = window.__rev.state.pins[0];
      const btns = [...document.querySelectorAll("#rev-layer .rev-note button")].filter((b) => b.textContent === "Hide");
      if (!btns.length) return "no-hide-button";
      btns[0].click();
      window.__rev.state.pins.splice(0, 1);   // the pin is deleted during the 180 ms animation
      await new Promise((r) => setTimeout(r, 500));
      return pin.state;
    });
  } else if (mode === "t96") {
    const fresh = async () => {
      const pg = await (await browser.newContext({ viewport: { width: 1200, height: 900 } })).newPage();
      await pg.goto(url(pagePath)); await pg.waitForSelector("html[data-rev-mounted]"); return pg;
    };
    const noteBtn = (pg, label) => pg.locator("#rev-layer .rev-note button", { hasText: new RegExp("^" + label + "$") });
    // row 1: Esc while editing returns focus to the pin; a removed pin sends it to the tool bar
    let pg = await fresh();
    await pg.evaluate(() => { const pin = window.__rev.place(document.querySelectorAll("#brew p")[0], "click"); pin.text = "Saved note"; pin.state = "open"; window.__rev.save(); window.__rev.sync(); });
    await noteBtn(pg, "Edit").click();
    await pg.locator("#rev-layer .rev-note textarea").focus();
    await pg.keyboard.press("Escape");
    out.escPin = await pg.evaluate(() => document.activeElement.className);
    pg = await fresh();
    await pg.evaluate(() => { window.__rev.place(document.querySelectorAll("#brew p")[0], "click"); });
    await pg.locator("#rev-layer .rev-note textarea").focus();
    await pg.keyboard.press("Escape");
    out.escGone = await pg.evaluate(() => ({ pins: window.__rev.state.pins.length, inBar: !!document.activeElement.closest("#rev-toolbar") }));
    // row 2: Show all opens post-its without Keep open, so a new post-it still folds them
    pg = await fresh();
    await pg.evaluate(() => {
      const ps = document.querySelectorAll("#brew p");
      for (let i = 0; i < 2; i++) { const pin = window.__rev.place(ps[i], "click"); pin.text = "Note " + i; pin.state = "hidden"; }
      window.__rev.save(); window.__rev.sync();
    });
    await pg.locator('#rev-toolbar [data-rev-act="hideall"]').click();
    out.shownAll = await pg.locator("#rev-layer .rev-note").count();
    await pg.evaluate(() => { window.__rev.place(document.querySelectorAll("#serve p")[0], "click"); });
    out.afterNewOne = await pg.evaluate(() => window.__rev.state.pins.filter((p) => p.state !== "hidden").length);
    // row 11: Enter on the focused Edit button activates it and does not place a pin
    pg = await fresh();
    await pg.evaluate(() => { const pin = window.__rev.place(document.querySelectorAll("#brew p")[0], "click"); pin.text = "Saved note"; pin.state = "open"; window.__rev.save(); window.__rev.sync(); });
    await pg.keyboard.press("j");
    await noteBtn(pg, "Edit").focus();
    await pg.keyboard.press("Enter");
    out.enterEdit = await pg.evaluate(() => ({ pins: window.__rev.state.pins.length, editing: !!document.querySelector("#rev-layer .rev-note textarea") }));
    // row 12: turning revision mode off removes the pin-list page margin
    pg = await fresh();
    await pg.locator('#rev-toolbar [data-rev-act="list"]').click();
    const margin = () => pg.evaluate(() => getComputedStyle(document.body).marginRight);
    out.marginOn = await margin();
    await pg.evaluate(() => window.__rev.setMode("off"));
    out.marginOff = await margin();
    // row 13: a Contents link shows one badge with the total count
    pg = await fresh();
    await pg.evaluate(() => {
      window.__rev.place(document.querySelectorAll("#brew p")[0], "click");
      window.__rev.place(document.querySelector("#brew details p"), "click");
      window.__rev.save(); window.__rev.sync();
    });
    await sleep(500);
    out.badges = await pg.evaluate(() => { const a = document.querySelector('nav a[href="#brew"]'); return [...a.querySelectorAll("[data-n]")].map((b) => b.getAttribute("data-n")); });
    // row 14: after Alt+Up widens to a container, J continues after that container
    pg = await fresh();
    const hiTop = () => pg.evaluate(() => { const h = document.querySelector(".rev-hi"); return { top: h.getBoundingClientRect().top, height: h.getBoundingClientRect().height }; });
    const p1 = await pg.evaluate(() => document.querySelector("#brew aside p").getBoundingClientRect().top);
    for (let i = 0; i < 8; i++) { await pg.keyboard.press("j"); if (Math.abs((await hiTop()).top - p1) < 2) break; }
    await pg.keyboard.press("Alt+ArrowUp");
    out.widened = (await hiTop()).height;
    await pg.keyboard.press("j");
    out.afterJ = (await hiTop()).top;
    out.serveTop = await pg.evaluate(() => document.querySelector("#serve h2").getBoundingClientRect().top);
  } else if (mode === "t105") {
    await open(pagePath);
    out.hits = await page.evaluate(() => {
      const pin = window.__rev.place(document.querySelector("#card"), "click"); pin.text = "A note for the card"; pin.state = "open";
      window.__rev.save(); window.__rev.sync();
      const el = document.querySelector("#rev-layer .rev-note"), L = parseFloat(el.style.left), T = parseFloat(el.style.top);   // style box, not the animated scale
      const n = { left: L, top: T, right: L + el.offsetWidth, bottom: T + el.offsetHeight };
      return ["#box", "#save"].filter((sel) => { const c = document.querySelector(sel).getBoundingClientRect();
        return n.left < c.right && n.right > c.left && n.top < c.bottom && n.bottom > c.top; });
    });
  } else if (mode === "t97") {
    const fresh = async () => {
      const pg = await (await browser.newContext({ viewport: { width: 1200, height: 900 } })).newPage();
      await pg.goto(url(pagePath)); await pg.waitForSelector("html[data-rev-mounted]"); return pg;
    };
    const pinLeft = (pg, ids) => pg.evaluate((ids) => ids.map((id) => parseFloat(document.querySelector('#rev-layer .rev-pin[data-rev-pin="' + id + '"]').style.left)), ids);
    // rows 1 and 2: the gutter check covers off-screen targets and the note's full height
    const gutterOf = async (sel) => {
      const q = await fresh();
      return q.evaluate((sel) => {
        const pin = window.__rev.place(document.querySelector(sel), "click"); pin.text = "A note with some words in it"; pin.state = "open";
        window.__rev.save(); window.__rev.sync();
        const note = document.querySelector("#rev-layer .rev-note");
        return { left: parseFloat(note.style.left), right: document.querySelector(sel).getBoundingClientRect().right + window.scrollX, height: note.offsetHeight };
      }, sel);
    };
    const near = await gutterOf("#near1"), far = await gutterOf("#far1");
    out.gutter = { nearLeft: near.left, nearRight: near.right, farLeft: far.left, farRight: far.right, noteHeight: near.height };
    let pg;
    // row 3: three pins on a target 40 px from the left edge never go below 0
    pg = await fresh();
    const ids = await pg.evaluate(() => [0, 1, 2].map(() => { const pin = window.__rev.place(document.querySelector("#edge1"), "click"); pin.state = "hidden"; return pin.id; }));
    await pg.evaluate(() => window.__rev.sync());
    out.edgeLefts = await pinLeft(pg, ids);
    // row 4: pins hidden by the per-target cap take no stacking slot
    const second = async (n) => {
      const q = await fresh();
      const bid = await q.evaluate((n) => {
        for (let i = 0; i < n; i++) { const pin = window.__rev.place(document.querySelector("#ta"), "click"); pin.state = "hidden"; }
        const b = window.__rev.place(document.querySelector("#tb"), "click"); b.state = "hidden"; window.__rev.sync(); return b.id;
      }, n);
      return (await pinLeft(q, [bid]))[0];
    };
    out.afterFive = await second(5);
    out.afterThree = await second(3);
    // row 5: after Esc focuses the pin, J and Alt+Up still work
    pg = await fresh();
    await pg.evaluate(() => { const pin = window.__rev.place(document.querySelector("#near1"), "click"); pin.text = "Saved note"; pin.state = "open"; window.__rev.save(); window.__rev.sync(); });
    await pg.locator("#rev-layer .rev-note button", { hasText: /^Edit$/ }).click();
    await pg.locator("#rev-layer .rev-note textarea").focus();
    await pg.keyboard.press("Escape");
    out.focusOnPin = await pg.evaluate(() => document.activeElement.className.indexOf("rev-pin") >= 0);
    await pg.keyboard.press("j");
    out.hiAfterJ = await pg.evaluate(() => { const h = document.querySelector(".rev-hi"); return h ? h.getBoundingClientRect().height : 0; });
    await pg.keyboard.press("Alt+ArrowUp");
    out.hiAfterAlt = await pg.evaluate(() => { const h = document.querySelector(".rev-hi"); return h ? h.getBoundingClientRect().height : 0; });
  } else if (mode === "t97keep") {
    await open(pagePath);
    await page.evaluate(() => { const pin = window.__rev.place(document.querySelector("#keep1"), "click"); pin.text = "Kept note"; pin.state = "open"; window.__rev.save(); window.__rev.sync(); });
    await page.evaluate(() => { [...document.querySelectorAll("#rev-layer .rev-note button")].find((x) => x.textContent === "Keep open").click(); });
    require("fs").writeFileSync(savedPath, await page.evaluate(() => window.__rev.exportHtml()));
    const q = await (await browser.newContext({ viewport: { width: 1200, height: 900 } })).newPage();
    await q.goto(url(savedPath)); await q.waitForSelector("html[data-rev-mounted]"); await sleep(400);
    out.reopened = await q.evaluate(() => ({ states: window.__rev.state.pins.map((p) => p.state), notes: document.querySelectorAll("#rev-layer .rev-note").length }));
  } else if (mode === "export") {
    await open(pagePath);
    await addPin();
    require("fs").writeFileSync(savedPath, await page.evaluate(() => window.__rev.exportHtml()));
  } else if (mode === "deleted") {
    await open(savedPath);
    out.before = await page.evaluate(() => window.__rev.state.pins.length);
    await page.evaluate(() => {
      const pin = window.__rev.state.pins[0]; pin.state = "open"; window.__rev.save();
    });
    await page.waitForSelector("#rev-layer .rev-note");
    await page.locator("#rev-layer .rev-note button[data-danger]").click();
    await page.locator("#rev-layer .rev-note button", { hasText: /^Yes$/ }).click();
    await sleep(600);
    await page.evaluate(() => window.__rev.flush());
    await page.reload();
    await page.waitForSelector("html[data-rev-mounted]");
    out.after = await page.evaluate(() => window.__rev.state.pins.length);
  }
  await browser.close();
  console.log(JSON.stringify(out));
})().catch((e) => { console.error(e); process.exit(1); });
"""


def run_browser(mode, page_path, saved_path=""):
    env = dict(os.environ)
    env.setdefault("NODE_PATH", DEFAULT_NODE_PATH)
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "run.js"
        script.write_text(SCRIPT, encoding="utf-8")
        result = subprocess.run(["node", str(script), mode, str(page_path), str(saved_path)],
                                capture_output=True, text=True, env=env, timeout=90)
    if result.returncode != 0:
        raise AssertionError("browser script failed: " + result.stderr)
    return json.loads(result.stdout.strip().splitlines()[-1])


class RuntimeFixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        base = Path(cls.tmp.name)
        (base / "tea.html").write_text(PAGE, encoding="utf-8")
        cls.page = base / "tea.rev.html"
        subprocess.run([sys.executable, str(REVISION_PY), "inject", str(base / "tea.html"), "--out", str(cls.page), "--default", "on"],
                       check=True, capture_output=True)
        cls.saved = base / "saved.html"
        run_browser("export", cls.page, cls.saved)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_row3_deleted_embedded_pin_stays_deleted_after_reload(self):
        out = run_browser("deleted", self.page, self.saved)
        self.assertEqual(out["before"], 1)
        self.assertEqual(out["after"], 0)

    def test_row4_hide_timer_ignores_a_deleted_pin(self):
        out = run_browser("hide", self.page)
        self.assertEqual(out["after"], "open")

    def test_row7_save_button_is_clean_at_start_and_dirty_after_an_edit(self):
        out = run_browser("dirty", self.page)
        self.assertFalse(out["dirtyAtStart"])
        self.assertTrue(out["dirtyAfterPin"])

    def test_time_right_click_focuses_textarea_and_t1_is_after_t0(self):
        out = run_browser("time", self.page)
        self.assertTrue(out["focusIsTextarea"])
        self.assertIsNotNone(out["ev"]["t1"])
        self.assertGreater(out["ev"]["t1"] - out["ev"]["t0"], 0)

    def test_row1_reload_with_local_only_pin_keeps_save_dirty(self):
        out = run_browser("reload", self.page)
        self.assertTrue(out["dirtyAfterReload"])

    def test_row1_reload_matching_the_file_stays_clean(self):
        out = run_browser("reloadsaved", self.page, self.saved)
        self.assertFalse(out["dirtyAfterReload"])

    def test_row3_first_delete_undo_keeps_its_own_index(self):
        out = run_browser("undo2", self.page)
        self.assertEqual(out["after"], ["Note 1", "Note 2"])


class PostItLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        base = Path(cls.tmp.name)
        (base / "tea.html").write_text(PAGE, encoding="utf-8")
        cls.page = base / "tea.rev.html"
        subprocess.run([sys.executable, str(REVISION_PY), "inject", str(base / "tea.html"), "--out", str(cls.page), "--default", "on"],
                       check=True, capture_output=True)
        cls.stack = run_browser("stack", cls.page)["stack"]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_t88_row1_stacked_postits_do_not_overlap_at_full_size(self):
        self.assertEqual(self.stack["overlap"], 0)

    def test_t89_fold_rule_only_the_newest_postit_stays_open_and_none_overlap(self):
        # placing a post-it folds the others (T82 fold rule), so 3 placed pins leave 1 open
        self.assertEqual(self.stack["count"], 1)
        self.assertEqual(self.stack["overlap"], 0)

    def test_t89_saved_postits_load_folded_unless_keep_open_is_set(self):
        out = run_browser("foldload", self.page)["fold"]
        self.assertEqual(sorted(out["states"]), ["hidden", "open"])
        self.assertEqual(out["notes"], 1)

    def test_t88_row2_no_second_auto_hide_rule_beside_avoid_notes(self):
        source = (SKILLS_DIR / "personal-md-to-html" / "revision" / "revision.js").read_text(encoding="utf-8")
        self.assertNotIn("fresher", source)

    def test_t88_row3_open_animation_grows_from_the_pin_after_the_move(self):
        for o in self.stack["origins"]:
            self.assertAlmostEqual(o["oy"], o["want"], delta=1.5)

    def test_t88_row4_sticky_element_does_not_move_the_toolbar(self):
        out = run_browser("sticky", self.page)
        self.assertEqual(out["stickyLeft"], "")

    def test_t88_row4_scrolling_does_not_re_measure_the_toolbar(self):
        out = run_browser("scroll", self.page)
        self.assertEqual(out["leftAfterScroll"], "123px")


class ReviewRowTests(unittest.TestCase):
    """T96: the seven fix-now rows of the round-3 critic judge."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        base = Path(cls.tmp.name)
        (base / "tea.html").write_text(PAGE_T96, encoding="utf-8")
        page = base / "tea.rev.html"
        subprocess.run([sys.executable, str(REVISION_PY), "inject", str(base / "tea.html"), "--out", str(page), "--default", "on"],
                       check=True, capture_output=True)
        cls.out = run_browser("t96", page)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_t96_row1_esc_while_editing_returns_focus_to_the_pin(self):
        self.assertIn("rev-pin", self.out["escPin"])

    def test_t96_row1_esc_on_a_removed_pin_focuses_the_tool_bar(self):
        self.assertEqual(self.out["escGone"], {"pins": 0, "inBar": True})

    def test_t96_row2_show_all_does_not_set_keep_open(self):
        self.assertEqual(self.out["shownAll"], 2)
        self.assertEqual(self.out["afterNewOne"], 1)

    def test_t96_row4_gutter_comment_says_284_px(self):
        source = (SKILLS_DIR / "personal-md-to-html" / "revision" / "revision.js").read_text(encoding="utf-8")
        self.assertIn("284 px", source)
        self.assertNotIn("280 px", source)

    def test_t96_row11_enter_on_the_edit_button_activates_it_and_places_no_pin(self):
        self.assertEqual(self.out["enterEdit"], {"pins": 1, "editing": True})

    def test_t96_row12_mode_off_removes_the_pin_list_margin(self):
        self.assertEqual(self.out["marginOn"], "320px")
        self.assertNotEqual(self.out["marginOff"], "320px")

    def test_t96_row13_contents_link_shows_one_badge_with_the_total(self):
        self.assertEqual(self.out["badges"], ["2"])

    def test_t96_row14_j_after_alt_up_continues_after_the_container(self):
        self.assertGreater(self.out["widened"], 35)
        self.assertAlmostEqual(self.out["afterJ"], self.out["serveTop"], delta=2)


class FixNowT97Tests(unittest.TestCase):
    """T97: the round-4 fix-now rows of the critic judge plus the Keep open export row."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        base = Path(cls.tmp.name)
        (base / "tea.html").write_text(PAGE_T97, encoding="utf-8")
        cls.page = base / "tea.rev.html"
        subprocess.run([sys.executable, str(REVISION_PY), "inject", str(base / "tea.html"), "--out", str(cls.page), "--default", "on"],
                       check=True, capture_output=True)
        cls.out = run_browser("t97", cls.page)
        cls.keep = run_browser("t97keep", cls.page, base / "saved.html")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_t97_row1_note_below_the_fold_does_not_take_the_right_gutter(self):
        self.assertLess(self.out["gutter"]["farLeft"], self.out["gutter"]["farRight"])

    def test_t97_row2_gutter_probe_sees_a_heading_lower_in_the_note(self):
        self.assertGreater(self.out["gutter"]["noteHeight"], 120)
        self.assertLess(self.out["gutter"]["nearLeft"], self.out["gutter"]["nearRight"])

    def test_t97_row3_stepped_pins_never_go_past_the_left_edge(self):
        self.assertTrue(all(left >= 0 for left in self.out["edgeLefts"]), self.out["edgeLefts"])

    def test_t97_row4_hidden_pins_take_no_stacking_slot(self):
        self.assertEqual(self.out["afterFive"], self.out["afterThree"])

    def test_t97_row5_j_and_alt_up_work_after_esc_focuses_a_pin(self):
        self.assertTrue(self.out["focusOnPin"])
        self.assertGreater(self.out["hiAfterJ"], 0)
        self.assertGreater(self.out["hiAfterAlt"], self.out["hiAfterJ"])

    def test_t97_row6_pin_pulse_peaks_at_1_08(self):
        css = (SKILLS_DIR / "personal-md-to-html" / "revision" / "revision.css").read_text(encoding="utf-8")
        pulse = [line for line in css.splitlines() if "@keyframes rev-pin-pulse" in line][0]
        self.assertIn("scale(1.08)", pulse)
        self.assertNotIn("scale(1.18)", pulse)

    def test_t97_row8_saved_copy_keeps_the_keep_open_setting(self):
        self.assertEqual(self.keep["reopened"], {"states": ["open"], "notes": 1})

    def test_t104_row1_layout_note_removes_compact_before_reading_height(self):
        source = (SKILLS_DIR / "personal-md-to-html" / "revision" / "revision.js").read_text(encoding="utf-8")
        body = source.split("function layoutNote(")[1]
        self.assertLess(body.index('removeAttribute("data-compact")'), body.index("note.offsetHeight"))

    def test_t104_row2_above_and_below_probe_the_clamped_left(self):
        source = (SKILLS_DIR / "personal-md-to-html" / "revision" / "revision.js").read_text(encoding="utf-8")
        body = source.split("function layoutNote(")[1].split("function ")[0]
        self.assertNotIn("Math.max(EDGE, r.left)", body)
        self.assertIn("vw - NOTE_W - EDGE", body.split("coversContent")[0])
        self.assertIn("coversContent(cl, r.top - 8 - h, h)", body)
        self.assertIn("coversContent(cl, r.bottom + 8, h)", body)

    def test_t104_row3_layout_comment_lists_the_real_order(self):
        source = (SKILLS_DIR / "personal-md-to-html" / "revision" / "revision.js").read_text(encoding="utf-8")
        line = [x for x in source.splitlines() if x.strip().startswith("// Order: right gutter")]
        self.assertEqual(len(line), 1)
        text = line[0]
        self.assertTrue(text.index("right") < text.index("left") < text.index("above") < text.index("below") < text.index("compact"))
        self.assertIn("wide target", text)

    def test_t104_row4_newer_embedded_pin_without_keep_open_drops_the_stale_keep(self):
        source = (SKILLS_DIR / "personal-md-to-html" / "revision" / "revision.js").read_text(encoding="utf-8")
        self.assertIn("else delete s.keep[e.id]", source)

    def test_t112_clear_all_records_embedded_pins_as_deleted(self):
        source = (SKILLS_DIR / "personal-md-to-html" / "revision" / "revision.js").read_text(encoding="utf-8")
        line = [x for x in source.splitlines() if 'askIn(cl, "Clear all?"' in x]
        self.assertEqual(len(line), 1)
        self.assertIn("embeddedPins().forEach", line[0])
        self.assertLess(line[0].index("state.deleted.push"), line[0].index("state.pins.length = 0"))

    def test_t104_htsw_copy_matches_md_to_html_copy(self):
        a = (SKILLS_DIR / "personal-md-to-html" / "revision" / "revision.js").read_bytes()
        c = (SKILLS_DIR / "personal-htsw" / "walk" / "revision" / "revision.js").read_bytes()
        self.assertEqual(a, c)


class PostItControlsT105Tests(unittest.TestCase):
    """T105: an open post-it never covers an input or button next to its target."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        base = Path(cls.tmp.name)
        (base / "tea.html").write_text(PAGE_T105, encoding="utf-8")
        page = base / "tea.rev.html"
        subprocess.run([sys.executable, str(REVISION_PY), "inject", str(base / "tea.html"), "--out", str(page), "--default", "on"],
                       check=True, capture_output=True)
        cls.out = run_browser("t105", page)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_t105_open_postit_does_not_cover_the_comment_box_or_save_button(self):
        self.assertEqual(self.out["hits"], [])


def _t111_files():
    root = SKILLS_DIR / "personal-md-to-html" / "revision"
    return (root / "revision.js").read_text(encoding="utf-8"), (root / "revision.css").read_text(encoding="utf-8")


class RoundSixT111Tests(unittest.TestCase):
    """T111: the six round-6 fix-now rows, checked on the shipped source."""

    def test_t111_row1_hover_tag_flips_only_when_there_is_no_room_above(self):
        js, _ = _t111_files()
        self.assertIn('toggleAttribute("data-flip", r.top < 28)', js)
        self.assertNotIn("above < 24", js)

    def test_t111_row2_compact_note_treats_its_target_box_as_blocked(self):
        js, _ = _t111_files()
        self.assertIn("function coversContent(x, y, h, ctl, tr)", js)
        self.assertIn("if (ctl && tr && px >= tr.left", js)
        self.assertEqual(js.count("coversContent(cl, yy, h, true, r)"), 2)

    def test_t111_row3_open_postit_has_one_hide_button(self):
        js, _ = _t111_files()
        self.assertEqual(js.count('"Hide")'), 1)

    def test_t111_row4_compact_collision_counts_links(self):
        js, _ = _t111_files()
        body = js.split("function coversContent(")[1].split("function layoutNote(")[0]
        self.assertLess(body.index('hit.closest("a[href]")'), body.index("if (ctl) return false;"))

    def test_t111_row5_below_viewport_probe_avoids_media(self):
        js, _ = _t111_files()
        self.assertIn("a[href],img,svg,canvas,video,h1", js)

    def test_t111_row6_one_row_foot_rule_comes_after_the_rules_that_override_it(self):
        _, css = _t111_files()
        lines = css.splitlines()
        one_row = [i for i, x in enumerate(lines) if x.startswith(".rev-panel-foot { flex-wrap: nowrap")][0]
        later = [i for i, x in enumerate(lines) if x.startswith(".rev-panel-foot, .rev-row-head") or x.startswith(".rev-panel button {")]
        self.assertTrue(later and one_row > max(later))


class PythonFixTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_row5_report_never_rewrites_its_input_ledger(self):
        ledger_row = {"id": "urn:a", "target": "gone-p-9", "kind": "p", "section": "s", "quote": "made up",
                      "comment": "Fix it", "intent": "wording", "resolved": "id", "verdict": "done", "note": "made up"}
        ledger_file = self.base / "pins.json"
        ledger_text = json.dumps([ledger_row])
        ledger_file.write_text(ledger_text, encoding="utf-8")
        v2_file = self.base / "v2.html"
        v2_file.write_text(PAGE, encoding="utf-8")
        run = subprocess.run([sys.executable, str(REVISION_PY), "report", str(ledger_file), str(v2_file)],
                             capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stdout)
        self.assertEqual(ledger_file.read_text(encoding="utf-8"), ledger_text, "the input ledger must stay byte-identical")
        reported = json.loads((self.base / "pins.json.reported.json").read_text(encoding="utf-8"))
        self.assertEqual(reported[0]["verdict"], "orphaned")

    def test_row2_report_removes_a_stale_reported_file(self):
        ledger_row = {"id": "urn:a", "target": "brew-p-1", "kind": "p", "section": "s", "quote": "made up",
                      "comment": "Fix it", "intent": "wording", "resolved": "id", "verdict": "done", "note": "made up"}
        ledger_file = self.base / "pins.json"
        ledger_file.write_text(json.dumps([ledger_row]), encoding="utf-8")
        v2_file = self.base / "v2.html"
        v2_file.write_text(PAGE.replace('<p>Use', '<p data-rev-id="brew-p-1">Use'), encoding="utf-8")
        stale = self.base / "pins.json.reported.json"
        stale.write_text("[]", encoding="utf-8")
        run = subprocess.run([sys.executable, str(REVISION_PY), "report", str(ledger_file), str(v2_file)],
                             capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stdout)
        self.assertFalse(stale.exists(), "a clean run must remove the stale reported file")

    def test_row6_walk_page_names_the_spec_as_data_rev_source(self):
        spec_file = SKILLS_DIR / "personal-md-to-html" / "evals" / "revision" / "fixtures" / "walk.json"
        out_file = self.base / "generated-page.html"
        run = subprocess.run([sys.executable, str(SKILLS_DIR / "personal-htsw" / "walk" / "walk-build.py"),
                              str(spec_file), "--out", str(out_file)], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn('data-rev-source="walk.json"', out_file.read_text(encoding="ascii"))


if __name__ == "__main__":
    outcome = unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    print("REVISION FIX TESTS PASS" if outcome.wasSuccessful() else "REVISION FIX TESTS FAIL")
    sys.exit(0 if outcome.wasSuccessful() else 1)
