// Gates 4, 6 and 8, plus the client-page placement sweep (gate 1 on the client copy).
// Selectors follow design.md: TOC badge span.rev-toc-badge[data-n], #rev-panel rows grouped by section, #rev-toolbar [data-rev-act].
// Panel markup is not fixed by design.md; the three PANEL_* constants are the only place to adapt it.
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { register, buildPage, newPage, urlOf, workDir, skillsDir, fixtures } from "./harness.mjs";

const PIN = "#rev-layer button.rev-pin";
const NOTE = "#rev-layer .rev-note";
const ACT = (a) => `#rev-toolbar [data-rev-act="${a}"]`;
const PANEL = "#rev-panel";
const PANEL_ROW = "#rev-panel .rev-row";
const PANEL_GROUP = "#rev-panel .rev-group";
const PANEL_FILTER = "#rev-panel input";
const revisionPy = () => path.join(skillsDir, "personal-md-to-html/revision/revision.py");
const noteBtn = (page, name) => page.locator(NOTE).getByRole("button", { name, exact: true });
const failOnErrors = (page, what) => { if (page.errors.length) throw new Error(what + ": " + page.errors[0]); };
const ENTRY_SEL = 'nav a[href^="#"], .toc a[href^="#"], .stepmap [data-go], .steps-list [data-go], details.lvl > summary';

async function open(ctx, shape) {
  const built = buildPage(shape);
  const page = await newPage(ctx.browser);
  await page.goto(urlOf(built.file));
  await page.waitForSelector("#rev-toolbar", { timeout: 5000 });
  return { page, built };
}

async function clickCenter(page, loc) {
  await loc.scrollIntoViewIfNeeded();
  // Click the center of the visible part: element box clipped by the viewport and every overflow-hidden ancestor.
  const pt = await loc.evaluate((el) => {
    let r = el.getBoundingClientRect();
    let [l, t, rt, bt] = [Math.max(r.left, 0), Math.max(r.top, 0), Math.min(r.right, innerWidth), Math.min(r.bottom, innerHeight)];
    for (let a = el.parentElement; a; a = a.parentElement) {
      if (getComputedStyle(a).overflow === "visible") continue;
      const c = a.getBoundingClientRect();
      [l, t, rt, bt] = [Math.max(l, c.left), Math.max(t, c.top), Math.min(rt, c.right), Math.min(bt, c.bottom)];
    }
    return rt > l && bt > t ? { x: (l + rt) / 2, y: (t + bt) / 2 } : null;
  });
  if (!pt) throw new Error("clickCenter: visible part of the element is empty (clipped or off-screen)");
  await page.mouse.click(pt.x, pt.y, { button: "right" });
}

const PARA = "p:not([data-rev-ui] *)";

async function placePin(page, nth, text) {
  await clickCenter(page, page.locator(PARA).nth(nth));
  await page.locator(NOTE + " textarea").fill(text);
  await noteBtn(page, "Save").click();
  await page.waitForSelector(NOTE + ":not(:has(textarea))", { timeout: 3000 });
}

// Index of the first paragraph in each distinct section, as {nth, key}. Section = closest details.lvl, else closest id-ed ancestor.
async function paragraphSections(page) {
  return page.evaluate((sel) => {
    const out = [];
    document.querySelectorAll(sel).forEach((p, nth) => {
      if (!p.getAttribute("data-rev-id")) return;
      let sec = p.closest("details.lvl");
      if (!sec) { let a = p.parentElement; while (a && !a.id) a = a.parentElement; sec = a; }
      out.push({ nth, key: sec ? (sec.id || "lvl:" + [...document.querySelectorAll("details.lvl")].indexOf(sec)) : "none" });
    });
    return out;
  }, PARA);
}

async function pickTwoSections(page) {
  const all = await paragraphSections(page);
  const first = all[0];
  const second = first && all.find((x) => x.key !== first.key);
  if (!second) throw new Error("fixture has no second section with a paragraph");
  return [first, second];
}

// For each pinned target id, the TOC entry index that must carry the badge; and what the page shows now.
function tocState(page, ids) {
  return page.evaluate(([entrySel, ids]) => {
    const entries = [...document.querySelectorAll(entrySel)].filter((e) => !e.closest("[data-rev-ui]"));
    const entryOf = (el) => {
      const d = el.closest("details.lvl");
      if (d && d.querySelector(":scope > summary")) return entries.indexOf(d.querySelector(":scope > summary"));
      for (let a = el; a; a = a.parentElement) {
        if (!a.id) continue;
        const i = entries.findIndex((e) => (e.getAttribute("href") || e.getAttribute("data-go")) === "#" + a.id);
        if (i >= 0) return i;
      }
      return -1;
    };
    const want = {};
    for (const id of ids) {
      const el = document.querySelector(`[data-rev-id="${id}"]`);
      const i = el ? entryOf(el) : -1;
      if (i >= 0) want[i] = (want[i] || 0) + 1;
    }
    const got = {}; let textNodes = 0; let emptyOk = true;
    entries.forEach((e, i) => {
      const b = e.querySelector(".rev-toc-badge") || (e.nextElementSibling && e.nextElementSibling.matches(".rev-toc-badge") ? e.nextElementSibling : null);
      if (!b) return;
      got[i] = Number(b.getAttribute("data-n"));
      if (b.textContent !== "") emptyOk = false;
      for (const n of b.childNodes) if (n.nodeType === 3) textNodes++;
    });
    return { want, got, textNodes, emptyOk, entries: entries.length };
  }, [ENTRY_SEL, ids]);
}

const pinIds = (page) => page.locator(PIN).evaluateAll((els) => els.map((e) => e.getAttribute("data-rev-target")));

async function twoSectionPins(page) {
  const [a, b] = await pickTwoSections(page);
  await placePin(page, a.nth, "Toc pin one");
  await placePin(page, b.nth, "Toc pin two");
  return [a, b];
}

register("toc", 4, async (ctx) => {
  for (const shape of ["interactive", "walk"]) {
    const { page } = await open(ctx, shape);
    if (shape === "interactive" && (await page.getAttribute("html", "data-rev-mode")) !== "on") await page.keyboard.press("r").catch(() => {});
    await twoSectionPins(page);
    await page.waitForTimeout(250); // badges repaint after a 100 ms debounce
    let ids = await pinIds(page);
    let s = await tocState(page, ids);
    if (!Object.keys(s.want).length) throw new Error(shape + ": no TOC entry found for the pinned sections");
    if (JSON.stringify(s.want) !== JSON.stringify(s.got)) throw new Error(shape + ": badges " + JSON.stringify(s.got) + " expected " + JSON.stringify(s.want));
    if (!s.emptyOk || s.textNodes) throw new Error(shape + ": a badge holds text; it must be empty with data-n set");
    // delete one pin: the count drops
    await page.locator(PIN).first().click();
    await noteBtn(page, "Delete").first().click();
    await page.locator(NOTE).getByRole("button", { name: /^Yes$/ }).click();
    await page.waitForTimeout(350);
    ids = await pinIds(page);
    if (ids.length !== 1) throw new Error(shape + ": delete left " + ids.length + " pins");
    s = await tocState(page, ids);
    if (JSON.stringify(s.want) !== JSON.stringify(s.got)) throw new Error(shape + ": after delete badges " + JSON.stringify(s.got) + " expected " + JSON.stringify(s.want));
    failOnErrors(page, shape);
    await page.context().close();
  }
});

register("panel", 4, async (ctx) => {
  const { page } = await open(ctx, "walk");
  await twoSectionPins(page);
  await page.click(ACT("list"));
  await page.waitForSelector(PANEL_ROW, { timeout: 3000 });
  if ((await page.locator(PANEL_ROW).count()) !== 2) throw new Error("panel shows " + (await page.locator(PANEL_ROW).count()) + " rows, expected 2");
  if ((await page.locator(PANEL_GROUP).count()) < 2) throw new Error("rows are not grouped by section (groups: " + (await page.locator(PANEL_GROUP).count()) + ")");
  // filter: a text that matches one row hides the other
  await page.locator(PANEL_FILTER).first().fill("Toc pin two");
  await page.waitForTimeout(300);
  const shown = await page.locator(PANEL_ROW).evaluateAll((els) => els.filter((e) => e.getClientRects().length).length);
  if (shown !== 1) throw new Error("filter left " + shown + " rows visible, expected 1");
  await page.locator(PANEL_FILTER).first().fill("");
  await page.waitForTimeout(300);
  // locate: click the row of the pin that is off screen
  await page.evaluate(() => window.scrollTo(0, 0));
  const rows = page.locator(PANEL_ROW);
  const idsBefore = await pinIds(page);
  await rows.nth(1).click();
  await page.waitForSelector(NOTE, { state: "visible", timeout: 3000 });
  await page.waitForTimeout(600);
  const inView = await page.evaluate((id) => {
    const r = document.querySelector(`[data-rev-id="${id}"]`).getBoundingClientRect();
    return r.bottom > 0 && r.top < window.innerHeight;
  }, idsBefore[1]);
  if (!inView) throw new Error("row click did not scroll its target into view");
  // edit: the row's Edit opens the post-it with a textarea
  await page.locator(NOTE + " textarea").first().waitFor({ state: "detached", timeout: 500 }).catch(() => {});
  await rows.nth(0).getByRole("button", { name: "Edit", exact: true }).click();
  await page.waitForSelector(NOTE + " textarea", { timeout: 3000 });
  // delete: asks in place, then the pin and the row go
  await rows.nth(0).getByRole("button", { name: "Delete", exact: true }).click();
  await page.locator(PANEL).getByRole("button", { name: /^Yes$/ }).click();
  await page.waitForTimeout(350);
  if ((await page.locator(PIN).count()) !== 1) throw new Error("panel Delete left " + (await page.locator(PIN).count()) + " pins");
  if ((await page.locator(PANEL_ROW).count()) !== 1) throw new Error("panel Delete left " + (await page.locator(PANEL_ROW).count()) + " rows");
  failOnErrors(page, "panel");
  await page.context().close();
});

// ---- gate 6: Respond text unchanged ----
const COMMENT = "Baseline comment one";
function normalize(t) {
  const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  let s = t.replace(/^Date: .*$/m, "Date: <DATE>");
  const tmp = workDir();
  for (const p of [tmp, tmp.replace(/\\/g, "/")]) s = s.replace(new RegExp(esc(p), "g"), "<TMP>");
  s = s.replace(/interactive\.html|walk\.html/g, "<PAGE>");
  return s.replace(/\r\n/g, "\n");
}
const baseline = (n) => fs.readFileSync(path.join(fixtures, "..", "baseline", n), "utf8");

async function respondText(page, shape) {
  await page.evaluate(() => document.querySelectorAll("details").forEach((d) => (d.open = true)));
  if (shape === "interactive") {
    await page.fill("details.lvl .sc-box textarea", COMMENT);
    await page.click("details.lvl .sc-box .sc-save");
    await page.click(".sc-respond");
    return page.inputValue(".sc-sheet textarea");
  }
  await page.evaluate(() => document.querySelector(".cm .cbtn").click());
  await page.fill(".cm .cedit textarea", COMMENT);
  await page.click(".cm .csave");
  await page.click("#respond");
  return page.inputValue("#out");
}

register("comments", 6, async (ctx) => {
  const want = { interactive: "respond-arc.txt", walk: "respond-walk.txt" };
  for (const shape of ["interactive", "walk"]) {
    // pass 1: the page as it loads; pass 2: after R flips revision mode
    for (const pass of ["as-loaded", "mode-flipped"]) {
      const { page } = await open(ctx, shape);
      if (pass === "mode-flipped") { await page.locator("body").click({ position: { x: 600, y: 5 } }).catch(() => {}); await page.keyboard.press("r"); await page.waitForTimeout(200); }
      const got = normalize(await respondText(page, shape));
      const exp = baseline(want[shape]);
      if (got !== exp) {
        let i = 0; while (i < got.length && got[i] === exp[i]) i++;
        throw new Error(shape + " " + pass + ": Respond text differs from baseline at offset " + i);
      }
      failOnErrors(page, shape + " " + pass);
      await page.context().close();
    }
  }
});

// ---- gate 8 and client pins: need --client and --original ----
const needClient = (ctx, what) => {
  if (!ctx.client || (what === "both" && !ctx.original)) throw new Error("NOT-RUN needs " + (what === "both" ? "--client and --original" : "--client"));
};

// Content text: body without script, style, template and runtime UI, whitespace collapsed.
const contentText = (page) => page.evaluate(() => {
  const c = document.body.cloneNode(true);
  c.querySelectorAll("script, style, template, [data-rev-ui]").forEach((n) => n.remove());
  return c.textContent.replace(/\s+/g, " ").trim();
});

register("client-text", 8, async (ctx) => {
  needClient(ctx, "both");
  const tc = spawnSync("python", [revisionPy(), "textcheck", ctx.original, ctx.client], { encoding: "utf8", timeout: 60000 });
  if (tc.error || tc.signal) throw new Error("textcheck did not finish");
  if (!/TEXT SAME/.test(tc.stdout || "")) throw new Error("textcheck: " + ((tc.stdout || tc.stderr || "").trim().split("\n")[0] || "no output").slice(0, 80));
  const orig = await newPage(ctx.browser);
  await orig.goto(urlOf(path.resolve(ctx.original)));
  const want = await contentText(orig);
  await orig.context().close();
  const page = await newPage(ctx.browser);
  await page.goto(urlOf(path.resolve(ctx.client)));
  await page.waitForSelector("#rev-toolbar", { timeout: 8000 });
  const targets = await page.locator(PARA).count();
  if (targets < 3) throw new Error("client copy has fewer than 3 paragraphs");
  for (const i of [0, Math.floor(targets / 2), targets - 1]) await placePin(page, i, "text check pin");
  if ((await page.locator(PIN).count()) !== 3) throw new Error("expected 3 pins, got " + (await page.locator(PIN).count()));
  const got = await contentText(page);
  if (got !== want) {
    let i = 0; while (i < got.length && got[i] === want[i]) i++;
    throw new Error("live content text differs from the original at offset " + i + " (lengths " + got.length + " vs " + want.length + ")");
  }
  failOnErrors(page, "client-text");
  await page.context().close();
});

const NOT_UI = ":not([data-rev-ui] *):not(nav *):not(.bar *):not(.nw-bar *)";
const KIND_SEL = {
  h: `h1${NOT_UI}, h2${NOT_UI}, h3${NOT_UI}, h4${NOT_UI}`,
  p: `p${NOT_UI}`,
  li: `li${NOT_UI}`,
  btn: `button${NOT_UI}`,
  img: `img${NOT_UI}`,
  tbl: `table${NOT_UI} > caption`,
  code: `pre${NOT_UI}`,
  dia: `svg${NOT_UI}`,
};

register("client-pins", 1, async (ctx) => {
  needClient(ctx, "client");
  const page = await newPage(ctx.browser);
  await page.goto(urlOf(path.resolve(ctx.client)));
  await page.waitForSelector("#rev-toolbar", { timeout: 8000 });
  const counts = {};
  for (const [kind, sel] of Object.entries(KIND_SEL)) {
    const n = await page.locator(sel).count();
    counts[kind] = 0;
    const step = Math.max(1, Math.floor(n / 10));
    for (let i = 0; i < n && counts[kind] < 10; i += step) {
      const loc = page.locator(sel).nth(i);
      const info = await loc.evaluate((el, k) => {
        const r = el.getBoundingClientRect();
        if (!r.width || !r.height || getComputedStyle(el).visibility === "hidden") return null;
        if (k === "dia" && (r.width < 48 || r.height < 48)) return null;
        if (el.closest("[data-rev-ui]")) return null;
        let own = k === "tbl" ? el.parentElement : el;
        // A list item that wraps paragraphs: the click lands on the inner paragraph, and that is the pin target.
        if (k === "li") { el.scrollIntoView({ block: "center", behavior: "instant" }); const r2 = el.getBoundingClientRect(); const h = document.elementFromPoint(r2.x + r2.width / 2, r2.y + r2.height / 2); if (h && el.contains(h)) own = h; }
        while (own && !own.getAttribute("data-rev-id")) own = own.parentElement;
        return own ? own.getAttribute("data-rev-id") : "";
      }, kind);
      if (info === null) continue;
      if (!info) throw new Error(kind + " #" + i + ": no data-rev-id on it or an ancestor");
      await clickCenter(page, loc);
      await page.waitForSelector(PIN, { timeout: 3000 }).catch(() => { throw new Error(kind + " #" + i + ": right-click made no pin"); });
      const got = await pinIds(page);
      if (got.length !== 1 || got[0] !== info) throw new Error(kind + " #" + i + ": pin target " + JSON.stringify(got) + " expected " + info);
      await noteBtn(page, "Save").click(); // empty Save removes the pin, so the next click starts clean
      await page.waitForTimeout(80);
      counts[kind]++;
    }
  }
  console.log("client-pins counts " + JSON.stringify(counts));
  if (!counts.h || !counts.p) throw new Error("no heading or paragraph instance was clicked");
  failOnErrors(page, "client-pins");
  await page.context().close();
});
