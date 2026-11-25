// Gates 1, 2 and 3: right-click placement by kind, the post-it life cycle, saving and reopening a copy.
// Selectors follow design.md: #rev-layer, button.rev-pin[data-rev-target], .rev-note, #rev-toolbar [data-rev-act], #rev-toast.
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { register, buildPage, newPage, urlOf, workDir, skillsDir, fixtures } from "./harness.mjs";

const PIN = "#rev-layer button.rev-pin";
const NOTE = "#rev-layer .rev-note";
const ACT = (a) => `#rev-toolbar [data-rev-act="${a}"]`;
const failOnErrors = (page, what) => { if (page.errors.length) throw new Error(what + ": " + page.errors[0]); };
const revisionPy = () => path.join(skillsDir, "personal-md-to-html/revision/revision.py");

async function open(ctx, shape) {
  const built = buildPage(shape);
  const page = await newPage(ctx.browser);
  await page.goto(urlOf(built.file));
  await page.waitForSelector("#rev-toolbar", { timeout: 5000 });
  return { page, built };
}

const pinTargets = (page) => page.locator(PIN).evaluateAll((els) => els.map((e) => e.getAttribute("data-rev-target")));

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

// Installs a capture listener that records whether any contextmenu event was default-prevented.
const watchPrevented = (page) => page.evaluate(() => {
  window.__rcPrevented = [];
  document.addEventListener("contextmenu", (e) => setTimeout(() => window.__rcPrevented.push(e.defaultPrevented), 0), true);
});
const prevented = (page) => page.evaluate(() => window.__rcPrevented.slice());

// Instance selectors per kind. The element clicked is the one whose own data-rev-id the pin must carry.
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
const OWNER = { tbl: (el) => el.parentElement };

// Clicks every visible instance of every kind and checks the pin target. Returns the count of instances clicked.
async function checkKinds(ctx, shape, required) {
  const { page } = await open(ctx, shape);
  const counts = {};
  for (const [kind, sel] of Object.entries(KIND_SEL)) {
    const n = await page.locator(sel).count();
    counts[kind] = 0;
    for (let i = 0; i < n; i++) {
      const loc = page.locator(sel).nth(i);
      const info = await loc.evaluate((el, k) => {
        const r = el.getBoundingClientRect();
        let own = k === "tbl" ? el.parentElement : el;
        // An image or svg inside a figure pins the outermost figure (design: fig wins over what it holds).
        if (k === "img" || k === "dia") for (let a = el.parentElement; a; a = a.parentElement) if (a.tagName === "FIGURE" || a.classList.contains("fig")) own = a;
        if (k === "dia" && (r.width < 48 || r.height < 48)) return null;
        if (k === "btn" && el.closest("[data-rev-ui]")) return null;
        const cs = getComputedStyle(el);
        if (!r.width || !r.height || cs.visibility === "hidden") return null;
        // A closed details box does not draw its content (outside the summary), even when the box reports a size.
        for (let prev = el, a = el.parentElement; a; prev = a, a = a.parentElement) if (a.tagName === "DETAILS" && !a.open && prev.tagName !== "SUMMARY") return null;
        return { id: own.getAttribute("data-rev-id") };
      }, kind);
      if (!info) continue;
      if (!info.id) throw new Error(shape + " " + kind + " #" + i + ": element has no data-rev-id");
      await page.addInitScript(() => { window.__btnClicks = 0; document.addEventListener("click", () => window.__btnClicks++, true); });
      await page.locator(PIN).evaluateAll((els) => els.forEach((e) => e.remove())).catch(() => {});
      await page.reload();
      await page.waitForSelector("#rev-toolbar", { timeout: 5000 });
      await clickCenter(page, page.locator(sel).nth(i));
      await page.waitForSelector(PIN, { timeout: 3000 }).catch(() => { throw new Error(shape + " " + kind + " #" + i + ": right-click made no pin"); });
      const got = await pinTargets(page);
      if (got.length !== 1 || got[0] !== info.id) throw new Error(shape + " " + kind + " #" + i + ": pin target " + JSON.stringify(got) + " expected " + info.id);
      if (kind === "btn") {
        const clicks = await page.evaluate(() => window.__btnClicks);
        if (clicks !== 0) throw new Error(shape + " btn #" + i + ": page action fired (" + clicks + " clicks)");
      }
      counts[kind]++;
    }
  }
  for (const k of required) if (!counts[k]) throw new Error(shape + ": no instance of kind " + k + " was clicked");
  failOnErrors(page, shape);
  await page.context().close();
}

register("rc-kinds", 1, async (ctx) => {
  await checkKinds(ctx, "placement", Object.keys(KIND_SEL));
  await checkKinds(ctx, "walk", ["h", "p"]);
});

register("rc-inner", 1, async (ctx) => {
  for (const shape of ["walk", "placement"]) {
    const { page } = await open(ctx, shape);
    await watchPrevented(page);
    // inline children of a paragraph: the pin target is the paragraph itself
    const hosted = await page.evaluate(() => {
      const p = [...document.querySelectorAll("p:not([data-rev-ui] *)")].find((x) => x.getAttribute("data-rev-id"));
      return p ? p.getAttribute("data-rev-id") : null;
    });
    if (!hosted) throw new Error(shape + ": no paragraph with data-rev-id");
    for (const tag of ["span", "em", "code"]) {
      // wrap a word of the first paragraph in the inline tag, so the click lands inside it
      await page.reload();
      await page.waitForSelector("#rev-toolbar", { timeout: 5000 });
      await page.evaluate(([id, t]) => {
        const p = document.querySelector(`[data-rev-id="${id}"]`);
        const w = document.createTreeWalker(p, NodeFilter.SHOW_TEXT);
        let n; while ((n = w.nextNode()) && !n.textContent.trim()) { /* skip blanks */ }
        const el = document.createElement(t); el.setAttribute("data-inner", t);
        el.textContent = n.textContent; n.replaceWith(el);
      }, [hosted, tag]);
      await clickCenter(page, page.locator(`[data-inner="${tag}"]`));
      await page.waitForSelector(PIN, { timeout: 3000 }).catch(() => { throw new Error(shape + ": right-click inside " + tag + " made no pin"); });
      const got = await pinTargets(page);
      if (got.length !== 1 || got[0] !== hosted) throw new Error(shape + " " + tag + ": pin target " + JSON.stringify(got) + " expected " + hosted);
    }
    // a layout div with no text of its own: no pin
    await page.reload();
    await page.waitForSelector("#rev-toolbar", { timeout: 5000 });
    await watchPrevented(page);
    await page.evaluate(() => {
      const d = document.createElement("div"); d.id = "rc-empty"; d.style.cssText = "width:300px;height:40px;border:1px solid #999";
      document.body.insertBefore(d, document.body.firstChild);
    });
    await clickCenter(page, page.locator("#rc-empty"));
    await page.waitForTimeout(300);
    if ((await page.locator(PIN).count()) !== 0) throw new Error(shape + ": a layout div got a pin");
    // blank page space: far right of the viewport, no pin, and the native menu is not prevented
    await page.mouse.click(1195, 5, { button: "right" });
    await page.waitForTimeout(300);
    if ((await page.locator(PIN).count()) !== 0) throw new Error(shape + ": blank space got a pin");
    const prev = await prevented(page);
    if (prev.length < 2 || prev.some(Boolean)) throw new Error(shape + ": contextmenu was default-prevented on empty or blank space " + JSON.stringify(prev));
    failOnErrors(page, shape);
    await page.context().close();
  }
});

register("rc-shift", 1, async (ctx) => {
  for (const shape of ["walk", "placement"]) {
    const { page } = await open(ctx, shape);
    await watchPrevented(page);
    const loc = page.locator("p:not([data-rev-ui] *)").first();
    await loc.scrollIntoViewIfNeeded();
    const b = await loc.boundingBox();
    await page.keyboard.down("Shift");
    await page.mouse.click(b.x + b.width / 2, b.y + b.height / 2, { button: "right" });
    await page.keyboard.up("Shift");
    await page.waitForTimeout(300);
    if ((await page.locator(PIN).count()) !== 0) throw new Error(shape + ": Shift+right-click made a pin");
    const prev = await prevented(page);
    if (prev.length < 1 || prev.some(Boolean)) throw new Error(shape + ": Shift+right-click was default-prevented " + JSON.stringify(prev));
    failOnErrors(page, shape);
    await page.context().close();
  }
});

const noteBtn = (page, name) => page.locator(NOTE).getByRole("button", { name, exact: true });

register("postit", 2, async (ctx) => {
  const { page } = await open(ctx, "walk");
  const TEXT = "Make this shorter", TEXT2 = "Make this much shorter";
  await clickCenter(page, page.locator("p:not([data-rev-ui] *)").first());
  await page.waitForSelector(PIN, { timeout: 3000 });
  await page.locator(NOTE + " textarea").fill(TEXT);
  await noteBtn(page, "Save").click();
  await page.waitForSelector(NOTE + ":not(:has(textarea))", { timeout: 3000 }).catch(() => { throw new Error("after Save the post-it is still editing"); });
  const shown = await page.locator(NOTE).first().innerText();
  if (!shown.includes(TEXT)) throw new Error("open post-it does not show the saved text");
  // Edit and change the text
  await noteBtn(page, "Edit").click();
  await page.locator(NOTE + " textarea").fill(TEXT2);
  await noteBtn(page, "Save").click();
  await page.waitForSelector(NOTE + ":not(:has(textarea))", { timeout: 3000 });
  if (!(await page.locator(NOTE).first().innerText()).includes(TEXT2)) throw new Error("edited text not shown");
  // Hide: only the pin shows
  await noteBtn(page, "Hide").click();
  await page.waitForTimeout(400);
  const visibleNotes = await page.locator(NOTE).evaluateAll((els) => els.filter((e) => e.getBoundingClientRect().width > 0 && getComputedStyle(e).visibility !== "hidden" && getComputedStyle(e).display !== "none").length);
  if (visibleNotes !== 0) throw new Error("after Hide " + visibleNotes + " .rev-note still visible");
  if ((await page.locator(PIN).count()) !== 1) throw new Error("after Hide the pin is missing");
  await page.locator(PIN).first().click();
  await page.waitForSelector(NOTE, { state: "visible", timeout: 3000 });
  if (!(await page.locator(NOTE).first().innerText()).includes(TEXT2)) throw new Error("pin click did not show the saved text");
  // Delete: first click asks, second confirms; Undo within 6 s brings it back
  await noteBtn(page, "Delete").click();
  await page.locator(NOTE).getByRole("button", { name: /^Yes$/ }).click();
  await page.waitForTimeout(300);
  if ((await page.locator(PIN).count()) !== 0) throw new Error("Delete did not remove the pin");
  await page.locator("#rev-toast").getByRole("button", { name: /Undo/ }).click();
  await page.waitForSelector(PIN, { timeout: 3000 }).catch(() => { throw new Error("Undo did not bring the pin back"); });
  await page.locator(PIN).first().click();
  await page.waitForSelector(NOTE, { state: "visible", timeout: 3000 });
  if (!(await page.locator(NOTE).first().innerText()).includes(TEXT2)) throw new Error("undone pin lost its text");
  await noteBtn(page, "Delete").click();
  await page.locator(NOTE).getByRole("button", { name: /^Yes$/ }).click();
  await page.waitForTimeout(300);
  if ((await page.locator(PIN).count()) !== 0) throw new Error("second Delete left a pin");
  // Empty Save on a new pin leaves no pin
  await clickCenter(page, page.locator("p:not([data-rev-ui] *)").nth(1));
  await page.waitForSelector(PIN, { timeout: 3000 });
  await noteBtn(page, "Save").click();
  await page.waitForTimeout(300);
  if ((await page.locator(PIN).count()) !== 0) throw new Error("empty Save left a pin");
  failOnErrors(page, "postit");
  await page.context().close();
});

async function placePin(page, nth, text) {
  await clickCenter(page, page.locator("p:not([data-rev-ui] *)").nth(nth));
  await page.locator(NOTE + " textarea").fill(text);
  await noteBtn(page, "Save").click();
  await page.waitForSelector(NOTE + ":not(:has(textarea))", { timeout: 3000 });
}

register("persist", 2, async (ctx) => {
  const { page, built } = await open(ctx, "walk");
  await placePin(page, 0, "First pin text");
  await placePin(page, 1, "Second pin text");
  await page.waitForTimeout(600); // the runtime writes storage 300 ms after a change
  const want = await pinTargets(page);
  if (want.length !== 2) throw new Error("expected 2 pins, got " + want.length);
  const key = await page.evaluate(() => "rev:1:" + document.documentElement.getAttribute("data-rev-doc"));
  const stored = await page.evaluate((k) => localStorage.getItem(k), key);
  if (!stored) throw new Error("no localStorage value under " + key);
  const pins = (JSON.parse(stored).pins || []);
  if (pins.length !== 2) throw new Error("stored pins " + pins.length + " expected 2");
  await page.reload();
  await page.waitForSelector("#rev-toolbar", { timeout: 5000 });
  await page.waitForSelector(PIN, { timeout: 3000 });
  const got = await pinTargets(page);
  if (JSON.stringify(got) !== JSON.stringify(want)) throw new Error("pins after reload " + JSON.stringify(got) + " expected " + JSON.stringify(want));
  const blob = JSON.stringify(JSON.parse(await page.evaluate((k) => localStorage.getItem(k), key)).pins);
  for (const t of ["First pin text", "Second pin text"]) if (!blob.includes(t)) throw new Error("text '" + t + "' lost after reload");
  failOnErrors(page, "persist");
  await page.context().close();
  void built;
});

register("save-file", 3, async (ctx) => {
  const { page, built } = await open(ctx, "interactive");
  await placePin(page, 0, "Save file pin one");
  await placePin(page, 1, "Save file pin two");
  const count = (await page.locator(PIN).count());
  const [dl] = await Promise.all([page.waitForEvent("download", { timeout: 5000 }), page.click(ACT("save"))]);
  const name = dl.suggestedFilename();
  if (!/^interactive\.rev-\d{8}-\d{4}\.html$/.test(name)) throw new Error("download name " + name);
  const saved = path.join(workDir(), name);
  await dl.saveAs(saved);
  const ex = spawnSync("python", [revisionPy(), "extract", saved], { encoding: "utf8" });
  const out = (ex.stdout || "") + (ex.stderr || "");
  const m = out.match(/ANNOTATIONS VALID: (\d+)/);
  if (!m || Number(m[1]) !== count) throw new Error("extract said '" + out.trim().split("\n").pop() + "' expected ANNOTATIONS VALID: " + count);
  const tc = spawnSync("python", [revisionPy(), "textcheck", built.file, saved], { encoding: "utf8" });
  if (!/TEXT SAME/.test(tc.stdout || "")) throw new Error("textcheck: " + (tc.stdout || tc.stderr).trim().split("\n")[0]);
  // reopen the downloaded copy
  const copy = await newPage(ctx.browser);
  await copy.goto(urlOf(saved));
  await copy.waitForSelector("#rev-toolbar", { timeout: 5000 });
  await copy.waitForSelector(PIN, { timeout: 3000 });
  if ((await copy.locator(PIN).count()) !== count) throw new Error("copy shows " + (await copy.locator(PIN).count()) + " pins, expected " + count);
  failOnErrors(copy, "downloaded copy");
  // the arc page's own section comment and Respond still work on the copy
  await copy.evaluate(() => document.querySelectorAll("details").forEach((d) => (d.open = true)));
  await copy.fill("details.lvl .sc-box textarea", "Copy comment");
  await copy.click("details.lvl .sc-box .sc-save");
  await copy.click(".sc-respond");
  const sheet = await copy.inputValue(".sc-sheet textarea");
  if (!sheet.includes("Copy comment")) throw new Error("Respond on the copy lost the comment");
  failOnErrors(copy, "downloaded copy after Respond");
  await copy.context().close();
  await page.context().close();
  void fs; void fixtures;
});
