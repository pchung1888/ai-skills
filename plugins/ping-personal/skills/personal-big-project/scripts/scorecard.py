"""Grade a run's metrics.json with references/scorecard.json, compare runs, and export a run's metrics
to the cross-project retro folder after a scrub. No LLM involved.

  python scorecard.py grade  --metrics <state-dir>/metrics.json
      -> the run score (0-100 of the weight that is known), coverage, safety flag, each dimension grade
  python scorecard.py trend  --dir ~/.claude/big-project-retros
      -> one row per *.metrics.json, oldest first, then the largest gaps of the newest complete run
  python scorecard.py export --metrics <state-dir>/metrics.json --to ~/.claude/big-project-retros
                             --name <YYYY-MM-DD>-<goal-slug> [--inputs <state-dir>/inputs.json]
      -> copies metrics.json only if every key is allowed and no string matches inputs.json "scrubPatterns"
         (regexes for ticket ids, client and server names). Exit 2 = refused, nothing written.

Grades are 0-5. A metric with no value, or a per-10-hour rate for a run shorter than minHours, is
unknown and never counts as 0. A dimension is unknown when less than half of its metric weight is
known. A run without an owner score is "incomplete": shown, never ranked.
"""
import argparse
import glob
import json
import os
import re
import sys

CARD_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "references", "scorecard.json")
TOP_KEYS = {"schemaVersion", "runId", "runDate", "goalKind", "skillVersion", "scorecardVersion", "unattendedHours",
            "backfilled", "scoreKind", "metrics", "complaintsBySkill"}
METRIC_KEYS = {"id", "value", "unit", "label", "source"}
SAFE_TEXT = re.compile(r"^[A-Za-z0-9 ._:/()+,=<>%-]{0,120}$")  # short tokens only; a quote does not fit


def load_card(path=CARD_PATH):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def grade_metric(spec, value, hours, card):
    """0-5, or None when unknown."""
    if value is None:
        return None
    kind = spec["grade"]
    if kind == "direct":
        return value if value in (1, 2, 3, 4, 5) else None
    if kind == "map":
        return spec["map"].get(value)
    if spec.get("per10h"):
        if not hours or hours < card.get("minHours", 1):
            return None
        value = value * 10 / hours
    if kind == "atLeast":
        return next((g for t, g in spec["bands"] if value >= t), 0)
    if kind == "atMost":
        return next((g for t, g in spec["bands"] if value <= t), 0)
    if kind == "between":
        return next((g for lo, hi, g in spec["bands"] if lo <= value <= hi), 0)
    raise ValueError(f"unknown grade kind {kind}")


def grade_run(run, card):
    values = {m["id"]: m.get("value") for m in run.get("metrics") or [] if isinstance(m, dict)}
    hours = run.get("unattendedHours")
    dims = {}
    for d in card["dimensions"]:
        known = [(m["weight"], grade_metric(m, values.get(m["id"]), hours, card)) for m in d["metrics"]]
        known = [(w, g) for w, g in known if g is not None]
        total = sum(m["weight"] for m in d["metrics"])
        weight = sum(w for w, _ in known)
        dims[d["id"]] = round(sum(w * g for w, g in known) / weight, 2) if weight >= total / 2 else None
    weights = {d["id"]: d["weight"] for d in card["dimensions"]}
    coverage = sum(weights[k] for k, g in dims.items() if g is not None)
    earned = sum(weights[k] * g / 5 for k, g in dims.items() if g is not None)
    flags = [values.get(k) for k in card["safety"]]
    safety = "SAFETY" if "FAIL" in flags else "UNKNOWN" if None in flags else "PASS"
    return {"runId": run.get("runId"), "score": round(100 * earned / coverage) if coverage else None,
            "coverage": coverage, "status": "complete" if values.get("ownerScore") is not None else "incomplete",
            "safety": safety, "dimensions": dims}


def gaps(graded, card):
    """(dimension, weight x (5 - grade)) for the known dimensions, largest first: where improve mode starts."""
    weights = {d["id"]: d["weight"] for d in card["dimensions"]}
    out = [(k, round(weights[k] * (5 - g), 1)) for k, g in graded["dimensions"].items() if g is not None]
    return sorted(out, key=lambda x: -x[1])


def trend(folder, card):
    runs = []
    for path in glob.glob(os.path.join(folder, "*.metrics.json")):
        try:
            with open(path, encoding="utf-8") as f:
                runs.append(json.load(f))
        except (OSError, ValueError):
            continue
    runs.sort(key=lambda r: str(r.get("runDate", "")))
    dim_ids = [d["id"] for d in card["dimensions"]]
    lines = ["| Date | Run | Skill | Owner | Score (coverage) | Safety | " + " | ".join(dim_ids) + " |",
             "|---" * (6 + len(dim_ids)) + "|"]
    newest = None
    by_skill = {}
    for r in runs:
        g = grade_run(r, card)
        owner = next((m.get("value") for m in r.get("metrics") or [] if m.get("id") == "ownerScore"), None)
        kind = f" ({r['scoreKind']})" if r.get("scoreKind") else ""
        score = "-" if g["score"] is None else f"{g['score']}% ({g['coverage']}%)"
        if g["status"] == "incomplete":
            score += " incomplete"
        cells = [str(r.get("runDate", "?")), str(r.get("runId", "?")), str(r.get("skillVersion", "?")),
                 f"{owner if owner is not None else '-'}{kind}", score, g["safety"]]
        cells += ["-" if g["dimensions"][k] is None else str(g["dimensions"][k]) for k in dim_ids]
        lines.append("| " + " | ".join(cells) + " |")
        if g["status"] == "complete":
            newest = g
        for skill, n in (r.get("complaintsBySkill") or {}).items():
            by_skill[skill] = by_skill.get(skill, 0) + n
    if newest:
        lines += ["", f"Largest gaps of the newest complete run ({newest['runId']}): weight x (5 - grade)", ""]
        lines += [f"- {k}: {v}" for k, v in gaps(newest, card)]
    if by_skill:
        lines += ["", "Owner complaints by skill, all runs (repeats point improve mode at that skill):", ""]
        lines += [f"- {k}: {v}" for k, v in sorted(by_skill.items(), key=lambda x: -x[1])]
    return "\n".join(lines) + "\n"


def export_problem(run, patterns):
    """'' when the run may leave the repo; otherwise the first reason it may not."""
    extra = set(run) - TOP_KEYS
    if extra:
        return f"keys not allowed outside the repo: {', '.join(sorted(extra))}"
    strings = [run.get("goalKind"), run.get("runId"), run.get("runDate"), run.get("skillVersion"), run.get("scoreKind")]
    for m in run.get("metrics") or []:
        if not isinstance(m, dict) or set(m) - METRIC_KEYS:
            return f"metric keys not allowed: {m}"
        if m.get("id") not in _metric_ids() and m.get("id") not in ("unattendedHours",):
            return f"metric id not allowed: {m.get('id')}"
        strings += [m.get("value") if isinstance(m.get("value"), str) else None, m.get("unit"), m.get("source"), m.get("label")]
    strings += list((run.get("complaintsBySkill") or {}).keys())
    for s in (x for x in strings if isinstance(x, str)):
        if not SAFE_TEXT.match(s):
            return f"text not allowed outside the repo (only short tokens): {s[:40]}"
        for p in patterns:
            if re.search(p, s):
                return f"scrub pattern {p} matches: {s[:40]}"
    return ""


def _metric_ids():
    card = load_card()
    return {m["id"] for d in card["dimensions"] for m in d["metrics"]} | set(card["safety"])


def export(src, folder, name, patterns):
    with open(src, encoding="utf-8") as f:
        run = json.load(f)
    problem = export_problem(run, patterns)
    if problem:
        print(f"REFUSED: {problem}")
        sys.exit(2)
    os.makedirs(folder, exist_ok=True)
    out = os.path.join(folder, f"{name}.metrics.json")
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(run, f, indent=2)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("what", choices=["grade", "trend", "export"])
    ap.add_argument("--metrics", help="a run's metrics.json. Example: docs/proj-123/autopilot/metrics.json")
    ap.add_argument("--dir", help="trend: folder of *.metrics.json. Example: ~/.claude/big-project-retros")
    ap.add_argument("--to", help="export: target folder. Example: ~/.claude/big-project-retros")
    ap.add_argument("--name", help="export: file name stem. Example: 2026-10-29-invoice-fixes")
    ap.add_argument("--inputs", help="export: the run's inputs.json, for scrubPatterns. Example: docs/proj-123/autopilot/inputs.json")
    a = ap.parse_args()
    card = load_card()
    if a.what == "grade":
        with open(a.metrics, encoding="utf-8") as f:
            print(json.dumps(grade_run(json.load(f), card), indent=2))
    elif a.what == "trend":
        print(trend(os.path.expanduser(a.dir), card), end="")
    else:
        pats = []
        if a.inputs and os.path.isfile(a.inputs):
            with open(a.inputs, encoding="utf-8-sig") as f:
                pats = json.load(f).get("scrubPatterns") or []
        print("EXPORTED " + export(a.metrics, os.path.expanduser(a.to), a.name, pats))
