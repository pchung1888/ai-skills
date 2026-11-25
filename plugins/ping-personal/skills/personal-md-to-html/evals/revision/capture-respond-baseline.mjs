// Captures the text the Respond buttons produce, so later code can be proven to keep it.
// Usage: node capture-respond-baseline.mjs          writes baseline/respond-{arc,nw,walk}.txt
//        node capture-respond-baseline.mjs --check  rebuilds and compares; last line says PASS or FAIL
import { createRequire } from "node:module";
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const skills = path.resolve(here, "../../..");
const fx = path.join(here, "fixtures");
const outDir = path.join(here, "baseline");
const check = process.argv.includes("--check");

// Playwright lookup: NODE_PATH entries, env REV_PW_DIR, then the gstack install.
function loadPlaywright() {
  const dirs = (process.env.NODE_PATH || "").split(path.delimiter).filter(Boolean);
  if (process.env.REV_PW_DIR) dirs.push(process.env.REV_PW_DIR);
  dirs.push("D:/playground/gstack/gstack/node_modules");
  for (const d of dirs) {
    try { return createRequire(path.join(d, "x.js"))("playwright"); } catch (e) { /* next */ }
  }
  return null;
}

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "rev-baseline-"));
function run(args) {
  const r = spawnSync("python", args, { encoding: "utf8" });
  if (r.status !== 0) throw new Error("build failed: " + args.join(" ") + "\n" + r.stderr);
}
const pages = {
  arc: path.join(tmp, "arc.html"),
  walk: path.join(tmp, "walk.html"),
  nw: path.join(tmp, "nw.html"),
};
run([path.join(skills, "personal-md-to-html/md-to-html.py"), path.join(fx, "interactive.md"), "--out", pages.arc]);
run([path.join(skills, "personal-htsw/walk/walk-build.py"), "--out", pages.walk, path.join(fx, "walk.json")]);
// The generator sets data-feedback="off", which hides html-plan's own Respond. A temp copy with it
// removed shows .nw-respond, which runs the same html-plan code a plain html-plan page uses.
fs.writeFileSync(pages.nw, fs.readFileSync(pages.arc, "utf8").replace(' data-feedback="off"', ""));

// Fixed tokens so a re-run is byte-equal: the date line and any temp path.
function norm(t) {
  const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  let s = t.replace(/^Date: .*$/m, "Date: <DATE>");
  for (const p of [tmp, tmp.replace(/\\/g, "/")]) s = s.replace(new RegExp(esc(p), "g"), "<TMP>");
  s = s.replace(/arc\.html|walk\.html|nw\.html/g, "<PAGE>");
  return s.replace(/\r\n/g, "\n");
}
const url = (f) => "file:///" + f.replace(/\\/g, "/");
const COMMENT = "Baseline comment one";

const pw = loadPlaywright();
if (!pw) { console.log("RESPOND BASELINE FAIL no playwright"); process.exit(1); }
const browser = await pw.chromium.launch({ headless: true });
const got = {};
try {
  async function open(file) {
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    await page.goto(url(file));
    await page.evaluate(() => document.querySelectorAll("details").forEach((d) => (d.open = true)));
    return page;
  }
  // arc: the page's own section comment box and the .sc-respond sheet
  let page = await open(pages.arc);
  await page.fill("details.lvl .sc-box textarea", COMMENT);
  await page.click("details.lvl .sc-box .sc-save");
  await page.click(".sc-respond");
  got["respond-arc.txt"] = await page.inputValue(".sc-sheet textarea");
  await page.context().close();
  // nw: html-plan's "+" popover comment and the .nw-respond sheet
  page = await open(pages.nw);
  await page.evaluate(() => document.querySelector(".nw-cbtn").click());
  await page.fill(".nw-pop textarea", COMMENT);
  await page.click(".nw-pop .primary");
  await page.evaluate(() => document.querySelector(".nw-respond").click());
  got["respond-nw.txt"] = await page.textContent(".nw-sheet pre");
  await page.context().close();
  // walk: the "+ Comment" editor and the #respond button
  page = await open(pages.walk);
  await page.evaluate(() => document.querySelector(".cm .cbtn").click());
  await page.fill(".cm .cedit textarea", COMMENT);
  await page.click(".cm .csave");
  await page.click("#respond");
  got["respond-walk.txt"] = await page.inputValue("#out");
  await page.context().close();
} finally {
  await browser.close();
}

let bad = 0;
for (const [name, raw] of Object.entries(got)) {
  const text = norm(raw);
  if (!text.includes(COMMENT)) { console.log("MISSING comment text in " + name); bad++; continue; }
  const f = path.join(outDir, name);
  if (check) {
    const want = fs.existsSync(f) ? fs.readFileSync(f, "utf8") : null;
    if (want !== text) { console.log("DIFFERS " + name); bad++; } else console.log("same " + name);
  } else {
    fs.mkdirSync(outDir, { recursive: true });
    fs.writeFileSync(f, text);
    console.log("wrote " + name + " (" + text.length + " chars)");
  }
}
fs.rmSync(tmp, { recursive: true, force: true });
if (check) console.log(bad ? "RESPOND BASELINE FAIL" : "RESPOND BASELINE PASS");
else if (bad) process.exit(1);
