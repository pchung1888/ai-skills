// Gate 9 steps: click-to-pin, drag placement, and the placement measurement (design.md "Placement").
// Selectors follow plan.md contract: #rev-toolbar [data-rev-act], #rev-layer button.rev-pin, .rev-chip, event rev:placed.
import fs from "node:fs";
import { register, buildPage, newPage, urlOf, fixtures } from "./harness.mjs";
import path from "node:path";

const PIN = "#rev-layer button.rev-pin";
const ACT = (a) => `#rev-toolbar [data-rev-act="${a}"]`;
const SEED = 51;
const METHODS = ["contextmenu", "click", "drag"];

async function open(ctx, shape) {
  const built = buildPage(shape);
  const page = await newPage(ctx.browser);
  await page.goto(urlOf(built.file));
  await page.waitForSelector("#rev-toolbar", { timeout: 5000 });
  return page;
}

// mulberry32: small seeded random generator, so the 3 edge points are the same on every run.
function mulberry32(a) {
  return () => {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const center = async (loc) => {
  await loc.scrollIntoViewIfNeeded();
  const b = await loc.boundingBox();
  if (!b) throw new Error("element has no box");
  return { x: b.x + b.width / 2, y: b.y + b.height / 2, b };
};

register("place-click", 9, async (ctx) => {
  const page = await open(ctx, "placement");
  // Give one paragraph a link and add a TOC link, both made-up, so the step can test navigation.
  await page.evaluate(() => {
    const p = document.querySelector('[data-fx="t03"]');
    p.insertAdjacentHTML("beforeend", ' <a id="fxlink" href="#t18x">see more</a>');
    const nav = document.createElement("nav");
    nav.innerHTML = '<a id="fxtoc" href="#t01x">Contents link</a>';
    document.body.prepend(nav);
  });
  const url0 = page.url();
  await page.locator(ACT("click")).click();
  await page.waitForSelector(".rev-chip", { timeout: 2000 });
  const p = page.locator('[data-fx="t03"]');
  const pid = await p.getAttribute("data-rev-id");
  await page.locator("#fxlink").click();
  await page.waitForSelector(PIN, { timeout: 3000 });
  const targets = await page.locator(PIN).evaluateAll((els) => els.map((e) => e.getAttribute("data-rev-target")));
  if (!targets.includes(pid)) throw new Error("paragraph with link not pinned: " + JSON.stringify(targets));
  if (page.url() !== url0) throw new Error("link navigated while armed: " + page.url());
  await page.locator("#fxtoc").click();
  if (page.url() !== url0) throw new Error("TOC link navigated while armed: " + page.url());
  await page.keyboard.press("Escape");
  await page.keyboard.press("Escape");
  if (await page.locator(".rev-chip").count() && await page.locator(".rev-chip").first().isVisible()) throw new Error("chip still shown after Esc");
  await page.locator("#fxtoc").click();
  if (page.url() === url0) throw new Error("link did not work after Esc disarmed");
  if (page.errors.length) throw new Error(page.errors[0]);
  await page.context().close();
});

register("place-drag", 9, async (ctx) => {
  const page = await open(ctx, "placement");
  const src = await center(page.locator(ACT("pinsource")));
  const p = page.locator('[data-fx="t04"]');
  const pid = await p.getAttribute("data-rev-id");
  const t = await center(p);
  await page.mouse.move(src.x, src.y);
  await page.mouse.down();
  await page.mouse.move((src.x + t.x) / 2, (src.y + t.y) / 2, { steps: 5 });
  await page.mouse.move(t.x, t.y, { steps: 5 });
  await page.mouse.up();
  await page.waitForSelector(PIN, { timeout: 3000 }).catch(() => { throw new Error("drag onto paragraph made no pin"); });
  const got = await page.locator(PIN).evaluateAll((els) => els.map((e) => e.getAttribute("data-rev-target")));
  if (got.length !== 1 || got[0] !== pid) throw new Error("drag pin target " + JSON.stringify(got) + " expected " + pid);
  await page.keyboard.press("Escape");
  // Release on blank space: right of the 800 px body, no pin, ghost back within 400 ms.
  const before = await page.locator(PIN).count();
  const s2 = await center(page.locator(ACT("pinsource")));
  await page.mouse.move(s2.x, s2.y);
  await page.mouse.down();
  await page.mouse.move(1150, 500, { steps: 8 });
  await page.mouse.up();
  await page.waitForTimeout(400);
  if ((await page.locator(PIN).count()) !== before) throw new Error("release on blank space made a pin");
  const ghost = await page.locator(".rev-ghost").count();
  if (ghost && await page.locator(".rev-ghost").first().isVisible()) throw new Error("ghost still visible 400 ms after release");
  if (page.errors.length) throw new Error(page.errors[0]);
  await page.context().close();
});

// Removes every pin. A fresh pin opens an empty note, and Esc in that note's textarea removes the pin
// (revision.js cancelEdit). Reloads as a last resort. Always leaves the page ready for the next method.
async function clearPins(page, method) {
  for (let i = 0; i < 3 && (await page.locator(PIN).count()); i++) await page.keyboard.press("Escape");
  if (await page.locator(PIN).count()) {
    await page.evaluate(() => Object.keys(localStorage).filter((k) => k.startsWith("rev:")).forEach((k) => localStorage.removeItem(k)));
    await page.reload();
    await page.waitForSelector("#rev-toolbar", { timeout: 5000 });
    await armWatch(page);
  }
  // Esc may have disarmed click-to-pin; re-arm so the next measurement starts armed.
  const btn = page.locator(ACT("click"));
  const armed = (await btn.getAttribute("aria-pressed")) === "true";
  if (method === "click" && !armed) await btn.click();
  if (method !== "click" && armed) await page.keyboard.press("Escape");
}

const armWatch = (page) => page.evaluate(() => {
  window.__placed = [];
  document.addEventListener("rev:placed", (e) => window.__placed.push(e.detail));
});

const median = (a) => { const s = a.filter((x) => x != null).sort((x, y) => x - y); return s.length ? s[Math.floor(s.length / 2)] : null; };

register("measure", 9, async (ctx) => {
  const targets = JSON.parse(fs.readFileSync(path.join(fixtures, "targets.json"), "utf8"));
  const page = await open(ctx, "placement");
  await armWatch(page);
  const rnd = mulberry32(SEED);
  const stats = Object.fromEntries(METHODS.map((m) => [m, { n: 0, wrong: 0, times: [], inputs: [], travel: [] }]));
  let total = 0;
  for (const method of METHODS) {
    if (method === "click") {
      await page.locator(ACT("click")).click();
    }
    await page.keyboard.press("Escape").catch(() => {});
    if (method === "click" && (await page.locator(ACT("click")).getAttribute("aria-pressed")) !== "true") await page.locator(ACT("click")).click();
    for (const t of targets) {
      const el = t.kind === "tbl" ? page.locator(`[data-fx="${t.fx}"] > caption`) : page.locator(`[data-fx="${t.fx}"]`);
      const owner = page.locator(`[data-fx="${t.fx}"]`);
      const want = await owner.getAttribute("data-rev-id");
      await el.scrollIntoViewIfNeeded();
      const b = await el.boundingBox();
      if (!b) throw new Error("no box for " + t.fx);
      const pts = [{ x: b.x + b.width / 2, y: b.y + b.height / 2 }];
      const inset = (v, len) => Math.min(Math.max(v, 6), Math.max(len - 6, 6));
      for (let k = 0; k < 3; k++) {
        const edge = Math.floor(rnd() * 4);
        const u = rnd();
        const px = edge < 2 ? b.x + inset(u * b.width, b.width) : b.x + (edge === 2 ? 6 : Math.max(b.width - 6, 6));
        const py = edge >= 2 ? b.y + inset(u * b.height, b.height) : b.y + (edge === 0 ? 6 : Math.max(b.height - 6, 6));
        pts.push({ x: px, y: py });
      }
      for (const pt of pts) {
        await armWatch(page);
        // Fail loud if the point is covered by the toolbar or anything outside the target.
        const hit = await page.evaluate(({ x, y, fx, cap }) => {
          const h = document.elementFromPoint(x, y);
          const t = document.querySelector(`[data-fx="${fx}"]` + (cap ? " > caption" : ""));
          return h ? { ok: t.contains(h), tag: h.tagName + "." + h.className } : { ok: false, tag: "none" };
        }, { x: pt.x, y: pt.y, fx: t.fx, cap: t.kind === "tbl" });
        if (!hit.ok) throw new Error("point (" + Math.round(pt.x) + "," + Math.round(pt.y) + ") for " + t.fx + " lands on " + hit.tag + ", not the target");
        let travel = 0;
        if (method === "drag") {
          const s = await center(page.locator(ACT("pinsource")));
          await el.scrollIntoViewIfNeeded();
          await page.mouse.move(s.x, s.y);
          await page.mouse.down();
          await page.mouse.move(pt.x, pt.y, { steps: 6 });
          await page.mouse.up();
          travel = Math.hypot(pt.x - s.x, pt.y - s.y);
        } else {
          const s = await center(page.locator(ACT("pinsource")));
          await el.scrollIntoViewIfNeeded();
          await page.mouse.move(s.x, s.y);
          await page.mouse.move(pt.x, pt.y, { steps: 6 });
          travel = Math.hypot(pt.x - s.x, pt.y - s.y);
          await page.mouse.click(pt.x, pt.y, { button: method === "contextmenu" ? "right" : "left" });
        }
        await page.waitForFunction(() => window.__placed.length > 0, null, { timeout: 800 }).catch(() => {});
        const ev = await page.evaluate(() => window.__placed[0] || null);
        const st = stats[method];
        st.n++; total++;
        if (!ev || ev.targetId !== want) st.wrong++;
        if (ev) { st.times.push(ev.t1 - ev.t0); st.inputs.push(ev.inputs); }
        st.travel.push(travel);
        await clearPins(page, method);
      }
    }
    if (method === "click") await page.keyboard.press("Escape");
  }
  const table = METHODS.map((m) => {
    const s = stats[m];
    return { method: m, placements: s.n, wrongRate: s.n ? s.wrong / s.n : 1, medianMs: median(s.times), inputsPerPin: median(s.inputs), medianTravelPx: Math.round(median(s.travel) || 0) };
  });
  const big = (x) => (x == null ? Infinity : x);
  const ranked = [...table].sort((a, b) => a.wrongRate - b.wrongRate || big(a.inputsPerPin) - big(b.inputsPerPin) || big(a.medianMs) - big(b.medianMs));
  const winner = ranked[0].method;
  const out = { seed: SEED, total, table, winner, note: "scripted timing measures the mechanism, not a person" };
  const argv = process.argv;
  const i = argv.indexOf("--out");
  const dest = i >= 0 ? argv[i + 1].replace(/\.json$/, "") + ".placement.json" : null;
  if (dest) fs.writeFileSync(dest, JSON.stringify(out, null, 2));
  console.log("method        placements  wrong-rate  median-ms  inputs  travel-px");
  for (const r of table) console.log(r.method.padEnd(13) + String(r.placements).padEnd(12) + r.wrongRate.toFixed(3).padEnd(12) + String(r.medianMs).padEnd(11) + String(r.inputsPerPin).padEnd(8) + r.medianTravelPx);
  console.log("winner: " + winner);
  console.log("scripted timing measures the mechanism, not a person");
  if (total !== 240) throw new Error("expected 240 placements, ran " + total);
  if (!winner) throw new Error("no winner");
  // A placement time must be a real duration: t1 (note focus, set by revision.js) after t0.
  for (const r of table) if (!(r.medianMs > 0)) throw new Error(r.method + ": median time " + r.medianMs + " ms is not a positive duration");
  await page.context().close();
}, 300000);
