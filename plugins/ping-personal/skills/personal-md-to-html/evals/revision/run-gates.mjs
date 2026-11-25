// Revision-mode gate script. Usage:
//   node run-gates.mjs [--steps a,b] [--list] [--require a,b] [--selftest]
//                      [--client <html>] [--original <html>] [--out <json>]
// Last line: ALL REVISION GATES PASS|FAIL, SELECTED REVISION STEPS PASS|FAIL, STEP LIST PASS|FAIL or SELFTEST PASS|FAIL.
import fs from "node:fs";
import { launch, stepIds, runSteps, report, selftest, cleanup } from "./lib/harness.mjs";
import "./lib/steps-g5.mjs";
import "./lib/steps-g123.mjs";
import "./lib/steps-g468.mjs";
import "./lib/steps-g7.mjs";
import "./lib/steps-g9.mjs";
// Later tasks add their steps files below this line.

const argv = process.argv.slice(2);
const flag = (n) => argv.includes(n);
const val = (n) => { const i = argv.indexOf(n); return i >= 0 ? argv[i + 1] : null; };
const csv = (s) => (s ? s.split(",").map((x) => x.trim()).filter(Boolean) : []);

if (flag("--selftest")) {
  const ok = await selftest();
  console.log(ok ? "SELFTEST PASS" : "SELFTEST FAIL");
  process.exit(ok ? 0 : 1);
}

if (flag("--list")) {
  const ids = stepIds();
  ids.forEach((i) => console.log(i));
  console.log(ids.length + " steps");
  const missing = csv(val("--require")).filter((i) => !ids.includes(i));
  if (missing.length) console.log("missing: " + missing.join(","));
  const ok = ids.length > 0 && !missing.length;
  console.log(ok ? "STEP LIST PASS" : "STEP LIST FAIL");
  process.exit(ok ? 0 : 1);
}

const selected = flag("--steps");
const ids = selected ? csv(val("--steps")) : stepIds();
const ctx = { client: val("--client"), original: val("--original") };
let ok = false;
try {
  ctx.browser = await launch();
  const results = await runSteps(ids, ctx);
  ok = report(results);
  if (val("--out")) fs.writeFileSync(val("--out"), JSON.stringify(results, null, 2));
} catch (e) {
  console.log("HARNESS ERROR " + String(e.message).split("\n")[0]);
} finally {
  if (ctx.browser) await ctx.browser.close();
  cleanup();
}
console.log(ok ? (selected ? "SELECTED REVISION STEPS PASS" : "ALL REVISION GATES PASS") : (selected ? "SELECTED REVISION STEPS FAIL" : "ALL REVISION GATES FAIL"));
process.exit(ok ? 0 : 1);
