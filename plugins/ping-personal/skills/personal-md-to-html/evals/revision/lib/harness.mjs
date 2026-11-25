// Gate harness: Playwright loader, page builders, step registry and runner.
// Plain ESM; the only dependency is Playwright. Steps live in steps-*.mjs and call register().
import { createRequire } from "node:module";
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

export const evalDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
export const skillsDir = path.resolve(evalDir, "../../..");
export const fixtures = path.join(evalDir, "fixtures");
const STEP_TIMEOUT = 30000;

// Playwright lookup: each NODE_PATH entry, then env REV_PW_DIR.
export function loadPlaywright() {
  const dirs = (process.env.NODE_PATH || "").split(path.delimiter).filter(Boolean);
  if (process.env.REV_PW_DIR) dirs.push(process.env.REV_PW_DIR);
  for (const d of dirs) {
    try { return createRequire(path.join(d, "x.js"))("playwright"); } catch (e) { /* next */ }
  }
  throw new Error("Playwright not found: set env NODE_PATH or REV_PW_DIR to a node_modules folder that contains playwright");
}

export async function launch() {
  return loadPlaywright().chromium.launch({ headless: true });
}

// A page whose console.error and pageerror events land in page.errors.
// Browser contexts still open; runSteps closes them after a step times out so hung work cannot touch later steps.
const openContexts = new Set();
export async function newPage(browser, opts = {}) {
  const ctx = await browser.newContext({ viewport: { width: 1200, height: 900 }, acceptDownloads: true, ...opts });
  openContexts.add(ctx);
  const page = await ctx.newPage();
  page.errors = [];
  page.on("console", (m) => { if (m.type() === "error") page.errors.push("console: " + m.text()); });
  page.on("pageerror", (e) => page.errors.push("pageerror: " + e.message));
  return page;
}

export const urlOf = (f) => "file:///" + f.replace(/\\/g, "/");

let buildDir = null;
export function workDir() {
  if (!buildDir) {
    buildDir = path.join(os.tmpdir(), "rev-gates-" + process.pid);
    fs.mkdirSync(buildDir, { recursive: true });
  }
  return buildDir;
}
export function cleanup() { if (buildDir) fs.rmSync(buildDir, { recursive: true, force: true }); }

function py(args) {
  const r = spawnSync("python", args, { encoding: "utf8", timeout: 60000 });
  if (r.error || r.signal) throw new Error("command did not finish: python " + args.join(" ") + " (" + (r.error ? r.error.message : r.signal) + ")");
  if (r.status !== 0) throw new Error("command failed: python " + args.join(" ") + "\n" + (r.stderr || r.stdout));
  return r.stdout;
}
const revisionPy = () => path.join(skillsDir, "personal-md-to-html/revision/revision.py");

// Shapes: old-plain, old-script, placement (foreign pages, injected), interactive, walk (generated).
// Returns { file, shape, injectedIds } where file is a built page under the work dir.
export function buildPage(shape) {
  const out = path.join(workDir(), shape + ".html");
  if (shape === "old-plain" || shape === "old-script" || shape === "placement") {
    py([revisionPy(), "inject", path.join(fixtures, shape + ".html"), "--out", out]);
  } else if (shape === "interactive") {
    py([path.join(skillsDir, "personal-md-to-html/md-to-html.py"), path.join(fixtures, "interactive.md"), "--revision", "on", "--out", out]);
  } else if (shape === "walk") {
    py([path.join(skillsDir, "personal-htsw/walk/walk-build.py"), path.join(fixtures, "walk.json"), "--out", out]);
  } else throw new Error("unknown shape " + shape);
  return { file: out, shape };
}

export const ID_ATTR = /\sdata-rev-id="[^"]*"/g;
export const stripIds = (html) => html.replace(ID_ATTR, "");
export const idsIn = (html) => [...html.matchAll(/\sdata-rev-id="([^"]*)"/g)].map((m) => m[1]);

export const textOf = (page) => page.evaluate(() => document.body.innerText);

// Right-click the visual center of the first element matching selector.
export async function rightClickCenter(page, selector, nth = 0) {
  const loc = page.locator(selector).nth(nth);
  await loc.scrollIntoViewIfNeeded();
  const b = await loc.boundingBox();
  if (!b) throw new Error("no box for " + selector);
  await page.mouse.click(b.x + b.width / 2, b.y + b.height / 2, { button: "right" });
}

// ---- step registry ----
const steps = new Map();
// timeout (ms) overrides the default step timeout for a long step.
export function register(id, gate, fn, timeout) { steps.set(id, { id, gate, fn, timeout }); }
export const stepIds = () => [...steps.keys()];

function withTimeout(p, ms) {
  let t;
  const timer = new Promise((_, rej) => { t = setTimeout(() => rej(new Error("timeout after " + ms + " ms")), ms); });
  return Promise.race([p, timer]).finally(() => clearTimeout(t));
}

// Runs the selected ids. Returns [{id, gate, status, reason}]. An id with no step is NOT-RUN.
export async function runSteps(ids, ctx, registry = steps, timeout = STEP_TIMEOUT) {
  const results = [];
  for (const id of ids) {
    const s = registry.get(id);
    if (!s) { results.push({ id, gate: null, status: "NOT-RUN", reason: "no such step" }); continue; }
    try {
      await withTimeout(Promise.resolve(s.fn(ctx)), s.timeout || timeout);
      results.push({ id, gate: s.gate, status: "PASS", reason: "" });
    } catch (e) {
      if (/^timeout after/.test(String(e && e.message))) {
        for (const c of openContexts) await c.close().catch(() => {});
        openContexts.clear();
      }
      results.push({ id, gate: s.gate, status: "FAIL", reason: String(e && e.message || e).split("\n")[0] });
    }
  }
  return results;
}

// Prints STEP and GATE lines, returns true only when every selected step passed.
export function report(results, log = console.log) {
  for (const r of results) log("STEP " + r.id + " " + r.status + (r.reason ? " " + r.reason : ""));
  const gates = new Map();
  for (const r of results) {
    if (r.gate == null) continue;
    const g = gates.get(r.gate) || "PASS";
    gates.set(r.gate, r.status === "PASS" ? g : r.status === "NOT-RUN" && g !== "FAIL" ? "NOT-RUN" : "FAIL");
  }
  for (const [g, st] of [...gates].sort((a, b) => a[0] - b[0])) log("GATE " + g + " " + st);
  return results.length > 0 && results.every((r) => r.status === "PASS");
}

// Proves the harness: throw = FAIL, unregistered = NOT-RUN, NOT-RUN fails the run, zero steps fails.
export async function selftest() {
  const reg = new Map([
    ["boom", { id: "boom", gate: 0, fn: () => { throw new Error("planted"); } }],
    ["fine", { id: "fine", gate: 0, fn: () => {} }],
    ["slow", { id: "slow", gate: 0, fn: () => new Promise(() => {}) }],
  ]);
  const quiet = () => {};
  const r = await runSteps(["boom", "fine", "ghost", "slow"], {}, reg, 200);
  const st = Object.fromEntries(r.map((x) => [x.id, x.status]));
  const checks = {
    "throwing step is FAIL": st.boom === "FAIL",
    "hung step is FAIL": st.slow === "FAIL",
    "unregistered id is NOT-RUN": st.ghost === "NOT-RUN",
    "NOT-RUN fails the run": report(await runSteps(["fine", "ghost"], {}, reg), quiet) === false,
    "zero steps fails the run": report([], quiet) === false,
    "all-pass run passes": report(await runSteps(["fine"], {}, reg), quiet) === true,
  };
  let ok = true;
  for (const [k, v] of Object.entries(checks)) { console.log((v ? "ok   " : "BAD  ") + k); ok = ok && v; }
  return ok;
}
