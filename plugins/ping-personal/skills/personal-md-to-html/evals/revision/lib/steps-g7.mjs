// Gate 7: the revise round trip, driven through the real revision.py (inject, extract, report).
// The step never prints a REVISE REPORT line itself; it only compares what revision.py printed.
// Ledger shape assumed (see CONTRACT.md): the pins.json from `extract` is an array, or an object holding the array
// under rows, pins or items. Each row names its target id; the step writes `verdict` and `note` on every row.
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { register, workDir, skillsDir, fixtures, stripIds } from "./harness.mjs";

const roundtripDir = path.join(fixtures, "roundtrip");
const revisionPy = () => path.join(skillsDir, "personal-md-to-html/revision/revision.py");
const readText = (file) => fs.readFileSync(file, "utf8").replace(/\r\n/g, "\n");
const TARGET_ID_PATTERN = /^[a-z0-9-]+-[a-z]+-\d+$/;
const EXPECTED_OK = "REVISE REPORT OK: 6 pins = 3 done, 2 kept, 1 orphaned";

// Runs revision.py and returns its output lines. A non-zero exit is not an error here: FAIL lines are the point.
function runRevision(args) {
  const run = spawnSync("python", [revisionPy(), ...args], { encoding: "utf8" });
  if (run.error) throw new Error("cannot run revision.py: " + run.error.message);
  const lines = ((run.stdout || "") + (run.stderr || "")).split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
  return { status: run.status, lines, last: lines[lines.length - 1] || "" };
}

// Applies canned edits to a copy of the v1 page with its ids stripped, so inject must carry the ids back.
function buildV2Source(caseDir) {
  const editSpec = JSON.parse(readText(path.join(roundtripDir, "v2-edits.json")));
  let source = stripIds(readText(path.join(roundtripDir, "v1.html"))).replace(/ data-rev-doc="[^"]*"/, "");
  for (const edit of editSpec.edits) {
    const hits = source.split(edit.find).length - 1;
    if (hits !== 1) throw new Error("edit find string occurs " + hits + " times: " + edit.find.slice(0, 40));
    source = source.replace(edit.find, edit.op === "delete" ? "" : edit.with);
  }
  const sourceFile = path.join(caseDir, "v2-source.html");
  fs.writeFileSync(sourceFile, source);
  return sourceFile;
}

function ledgerRows(ledger) {
  if (Array.isArray(ledger)) return ledger;
  for (const key of ["rows", "pins", "items"]) if (Array.isArray(ledger[key])) return ledger[key];
  throw new Error("pins.json has no row array");
}

function rowTargetId(row) {
  for (const key of ["target", "targetId", "target_id", "rev_id"]) if (typeof row[key] === "string") return row[key];
  const guess = Object.values(row).find((v) => typeof v === "string" && TARGET_ID_PATTERN.test(v));
  if (!guess) throw new Error("ledger row has no target id: " + JSON.stringify(row).slice(0, 80));
  return guess;
}

// Verdicts follow the canned edits: targets 1-3 changed, 4-5 left alone, 6 deleted.
const VERDICT_BY_TARGET = {
  "intro-h-1": "done", "intro-p-1": "done", "intro-p-2": "done",
  "intro-li-1": "kept", "steps-h-1": "kept",
  "steps-p-1": "orphaned",
};

function extractLedger(caseDir) {
  const ledgerFile = path.join(caseDir, "v1.pins.json");
  const extracted = runRevision(["extract", path.join(roundtripDir, "v1.saved.html"), "--out", ledgerFile]);
  if (!fs.existsSync(ledgerFile)) throw new Error("extract wrote no ledger; last line: " + extracted.last);
  return { ledgerFile, ledger: JSON.parse(readText(ledgerFile)) };
}

function markVerdicts(ledger) {
  const rows = ledgerRows(ledger);
  for (const row of rows) {
    const targetId = rowTargetId(row);
    const verdict = VERDICT_BY_TARGET[targetId];
    if (!verdict) throw new Error("no canned verdict for target " + targetId);
    row.verdict = verdict;
    row.note = "canned verdict for the round trip fixture";
  }
  return rows;
}

function buildV2(caseDir) {
  const v2File = path.join(caseDir, "v2.html");
  const injected = runRevision(["inject", buildV2Source(caseDir), "--out", v2File, "--carry-ids-from", path.join(roundtripDir, "v1.html")]);
  if (!fs.existsSync(v2File)) throw new Error("inject wrote no v2 page; last line: " + injected.last);
  return v2File;
}

register("roundtrip", 7, () => {
  const caseDir = fs.mkdtempSync(path.join(workDir(), "roundtrip-"));
  const { ledgerFile, ledger } = extractLedger(caseDir);
  const rows = markVerdicts(ledger);
  if (rows.length !== 6) throw new Error("ledger has " + rows.length + " rows, expected 6");
  fs.writeFileSync(ledgerFile, JSON.stringify(ledger, null, 2));
  const reported = runRevision(["report", ledgerFile, buildV2(caseDir)]);
  if (reported.last !== EXPECTED_OK) throw new Error("report said: " + reported.last.slice(0, 120));
});

register("roundtrip-fail", 7, () => {
  const caseDir = fs.mkdtempSync(path.join(workDir(), "roundtrip-fail-"));
  const { ledgerFile, ledger } = extractLedger(caseDir);
  const rows = markVerdicts(ledger);
  rows.pop();
  fs.writeFileSync(ledgerFile, JSON.stringify(ledger, null, 2));
  const reported = runRevision(["report", ledgerFile, buildV2(caseDir)]);
  if (!reported.last.startsWith("REVISE REPORT FAIL")) throw new Error("dropped row not caught; report said: " + reported.last.slice(0, 120));
  const badExtract = runRevision(["extract", path.join(roundtripDir, "v1.saved.bad.html"), "--out", path.join(caseDir, "bad.pins.json")]);
  if (!badExtract.lines.some((l) => l.startsWith("ANNOTATIONS INVALID"))) throw new Error("bad selector not caught; extract said: " + badExtract.last.slice(0, 120));
});
