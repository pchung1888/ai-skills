// Gate 5 steps: the toolbar mounts on every page shape, ids match, old and new pages take a right-click pin.
import fs from "node:fs";
import path from "node:path";
import { register, buildPage, newPage, urlOf, rightClickCenter, stripIds, idsIn, workDir, loadPlaywright } from "./harness.mjs";

const SHAPES = ["old-plain", "old-script", "interactive", "walk", "placement"];

// The page's own theme control state, or null when the shape has none.
const ownTheme = (page, shape) => page.evaluate((s) => {
  if (s === "old-script") return document.body.classList.contains("night") ? "night" : "day";
  if (s === "interactive" || s === "walk") return document.documentElement.getAttribute("data-theme");
  return null;
}, shape);

async function open(ctx, shape) {
  const built = buildPage(shape);
  const page = await newPage(ctx.browser);
  await page.goto(urlOf(built.file));
  await page.waitForSelector("#rev-toolbar", { timeout: 5000 });
  return { page, built };
}
const failOnErrors = (page, what) => { if (page.errors.length) throw new Error(what + ": " + page.errors[0]); };

register("mount", 5, async (ctx) => {
  for (const shape of SHAPES) {
    const { page } = await open(ctx, shape);
    for (const act of ["daynight", "toggle"]) {
      if (!(await page.locator(`#rev-toolbar [data-rev-act="${act}"]`).count())) throw new Error(shape + ": no " + act + " button");
    }
    const mode0 = await page.getAttribute("html", "data-rev-mode");
    await page.click('#rev-toolbar [data-rev-act="toggle"]');
    const mode1 = await page.getAttribute("html", "data-rev-mode");
    if (!mode0 || mode0 === mode1) throw new Error(shape + ": toggle did not flip data-rev-mode (" + mode0 + " -> " + mode1 + ")");
    const th0 = await page.getAttribute("html", "data-rev-theme");
    const own0 = await ownTheme(page, shape);
    await page.click('#rev-toolbar [data-rev-act="daynight"]');
    const th1 = await page.getAttribute("html", "data-rev-theme");
    if (!th0 || th0 === th1) throw new Error(shape + ": daynight did not flip data-rev-theme (" + th0 + " -> " + th1 + ")");
    const own1 = await ownTheme(page, shape);
    if (own0 !== null && own0 === own1) throw new Error(shape + ": the page's own theme control did not change (" + own0 + ")");
    failOnErrors(page, shape);
    await page.context().close();
  }
});

register("idparity", 5, async (ctx) => {
  const built = buildPage("old-plain");
  const html = fs.readFileSync(built.file, "utf8");
  const written = idsIn(html);
  if (!written.length) throw new Error("revision.py inject wrote no data-rev-id");
  const bare = path.join(workDir(), "old-plain-bare.html");
  fs.writeFileSync(bare, stripIds(html));
  const browser = ctx.browser;
  let page;
  try {
    page = await newPage(browser);
    await page.goto(urlOf(bare));
    await page.waitForSelector("#rev-toolbar", { timeout: 5000 });
    const stamped = await page.evaluate(() => [...document.querySelectorAll("[data-rev-id]")].map((e) => e.getAttribute("data-rev-id")));
    const a = [...new Set(written)].sort(), b = [...new Set(stamped)].sort();
    const missing = a.filter((x) => !b.includes(x)), extra = b.filter((x) => !a.includes(x));
    if (missing.length || extra.length) {
      throw new Error("id sets differ: missing from runtime " + missing.slice(0, 3) + " extra in runtime " + extra.slice(0, 3));
    }
    failOnErrors(page, "idparity");
  } finally { if (page) await page.context().close().catch(() => {}); }
});

// Right-click the first paragraph; the pin must carry that paragraph's own data-rev-id.
async function pinOnParagraph(ctx, shape, what) {
  const { page } = await open(ctx, shape);
  const sel = "p";
  const targetId = await page.locator(sel).first().getAttribute("data-rev-id");
  if (!targetId) throw new Error(what + ": first paragraph has no data-rev-id");
  await rightClickCenter(page, sel);
  await page.waitForSelector("#rev-layer button.rev-pin", { timeout: 3000 }).catch(() => { throw new Error(what + ": right-click made no pin"); });
  const pins = await page.locator("#rev-layer button.rev-pin").evaluateAll((els) => els.map((e) => e.getAttribute("data-rev-target")));
  if (pins.length !== 1 || pins[0] !== targetId) throw new Error(what + ": pin target " + JSON.stringify(pins) + " expected " + targetId);
  failOnErrors(page, what);
  await page.context().close();
}

register("oldpage", 5, async (ctx) => {
  for (const shape of ["old-plain", "old-script"]) await pinOnParagraph(ctx, shape, shape);
});

register("newpage", 5, async (ctx) => {
  for (const shape of ["interactive", "walk"]) await pinOnParagraph(ctx, shape, shape);
});
