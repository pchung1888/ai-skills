"""Build <state-dir>/PROGRESS.md, the fixed-row progress table, from the plan's task list, the
workflow journals and the run log. No LLM involved, so a refresh costs no tokens.

Inputs, all under --state-dir:
  tasks.csv        columns id,stage,what,estimate,added (extra columns are kept). Written by the
                   coordinator from plan.md; this script appends unplanned work as rows with
                   added=ADDED and never removes or reorders a row, so the table keeps the same shape
                   all weekend.
  log/run-log.md   table rows "| when | task id | what happened | evidence |".
  run-state.json   task outcomes (passed, deferred, failed, not-run) set the Status word when present;
                   the journal state is only the fallback.
Journals: wf_*.json written by the Workflow tool, by default every journal of every session listed in
inputs.json "sessions" (under ~/.claude/projects/*/<session id>/workflows/). An agent that appears in
two journals (a resumed workflow) counts once, by agentId.

An agent belongs to the task named by the first word of its label, split on ':' or space, so
"T8", "T8:fix" and "T8:gate:rhea" all count toward task T8.

Usage: python build_table.py --state-dir docs/proj-123/autopilot [--journals DIR ...]
"""
import argparse
import csv
import os
import re
import tempfile
from datetime import datetime

import statefiles

FIELDS = ["id", "stage", "what", "estimate", "added"]
HEADER = ("| # | Stage | Task | What it does (plain words, <=12 words) | Status | Started | Finished "
          "| Tokens used | Token estimate | Notes |")
NOTE_CHARS = 120  # keeps each row readable on a phone
OUTCOME_WORDS = {"passed": "Done", "failed": "Failed", "not-run": "Not run"}


def day_time(ms):
    return datetime.fromtimestamp(ms / 1000).strftime("%a %m-%d %H:%M")


def task_id(label):
    return re.split(r"[:\s]", label.strip(), maxsplit=1)[0]


def read_tasks(path):
    """(rows, columns): every column of tasks.csv is kept, so a column the coordinator adds survives."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        columns = list(FIELDS) + [c for c in (reader.fieldnames or []) if c and c not in FIELDS]
        rows = [{c: (r.get(c) or "").strip() for c in columns}
                for r in reader if any((v or "").strip() for v in r.values() if isinstance(v, str))]
    return rows, columns


def write_tasks(path, tasks, columns):
    """Atomic write (temp file, then os.replace), so a crash never leaves a half-written tasks.csv."""
    handle, temp_path = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(path)), suffix=".tmp")
    try:
        with os.fdopen(handle, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            writer.writerows(tasks)
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def read_agents(journal_dirs):
    """Every agent once (resumed workflows deduped by agentId), oldest workflow first, with a 'task' key."""
    agents, _ = statefiles.unique_agents(statefiles.read_journals(journal_dirs))
    return [dict(a, task=task_id(a["label"])) for a in agents if a.get("label")]


def read_log(path):
    """task id -> list of (when, what, evidence), in file order."""
    rows = {}
    for cells in statefiles.table_rows(path):
        if len(cells) >= 3:
            rows.setdefault(cells[1], []).append((cells[0], cells[2], cells[3] if len(cells) > 3 else ""))
    return rows


def read_outcomes(state_dir):
    """task id -> (outcome, deferredBy) from run-state.json, the coordinator's single record of results."""
    run_state = statefiles.read_json_safe(os.path.join(state_dir, "run-state.json"))
    outcomes = {}
    stages = run_state.get("stages") if isinstance(run_state, dict) else None
    for stage in stages or []:
        for tid, info in (stage.get("tasks") or {}).items():
            if isinstance(info, dict) and info.get("outcome"):
                outcomes[tid] = (info["outcome"], info.get("deferredBy"))
    return outcomes


def status_of(agents, log_lines, outcome=None):
    if outcome:
        kind, by = outcome
        word = f"Deferred ({by or 'agent'})" if kind == "deferred" else OUTCOME_WORDS.get(kind, kind.capitalize())
    else:
        states = {a.get("state", "") for a in agents}
        if not agents:
            word = "Done (logged)" if log_lines else "Not started"
        elif "running" in states:
            word = "Running"
        elif states == {"done"}:
            word = "Done"
        else:
            word = ", ".join(sorted(s.capitalize() for s in states - {"done"}))
    counts = [m for _, what, _ in log_lines for m in re.findall(r"\((\d+/\d+)\)", what)]
    return f"{word} ({counts[-1]})" if counts else word


def row_for(n, t, agents, log_lines, outcome=None):
    timed = [a for a in agents if statefiles.number(a.get("startedAt"))]
    terminal = outcome is not None and outcome[0] in ("passed", "deferred", "failed")
    done = agents and (all(a.get("state") == "done" for a in agents) or terminal)
    started = day_time(min(statefiles.number(a["startedAt"]) for a in timed)) if timed else "-"
    if done and timed:
        finished = day_time(max(statefiles.number(a["startedAt"]) + statefiles.number(a.get("durationMs"))
                                for a in timed))
    elif log_lines and not agents:
        finished = log_lines[-1][0]
    else:
        finished = "-"
    tokens = f"{sum(statefiles.number(a.get('tokens')) for a in agents):,}" if agents else "don't know"
    notes = []
    fixes = sum(1 for a in agents if ":fix" in a["label"] or "-fix" in a["label"])
    if fixes:
        notes.append(f"fix rounds: {fixes}")
    if any(":gate" in a["label"] for a in agents):
        notes.append("critic gate voted")
    if t["added"]:
        notes.insert(0, "ADDED")
    if log_lines:
        notes.append(log_lines[-1][1][:NOTE_CHARS])
    cells = [str(n), t["stage"], t["id"], t["what"], status_of(agents, log_lines, outcome), started, finished,
             tokens, t["estimate"] or "don't know", "; ".join(notes)]
    return "| " + " | ".join(c.replace("|", "/") for c in cells) + " |"


def build(state_dir, journal_dirs, now=None):
    tasks_path = os.path.join(state_dir, "tasks.csv")
    tasks, columns = read_tasks(tasks_path)
    agents = read_agents(journal_dirs)
    log = read_log(os.path.join(state_dir, "log", "run-log.md"))
    outcomes = read_outcomes(state_dir)

    known = {t["id"] for t in tasks}
    for a in agents:
        if a["task"] not in known:
            known.add(a["task"])
            tasks.append({"id": a["task"], "stage": a.get("phaseTitle") or a["workflow"],
                          "what": a["label"][:60], "estimate": "", "added": "ADDED"})
    tasks = [{c: t.get(c, "") for c in columns} for t in tasks]
    write_tasks(tasks_path, tasks, columns)

    by_task = {}
    for a in agents:
        by_task.setdefault(a["task"], []).append(a)
    now = now or datetime.now()
    lines = [
        "# Progress",
        "",
        f"Built {now.strftime('%a %m-%d %H:%M')} by scripts/build_table.py from tasks.csv, the workflow "
        "journals and log/run-log.md. Times are local, Day MM-DD HH:MM. Rows are never deleted or reordered.",
        "",
        HEADER,
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    lines += [row_for(i, t, by_task.get(t["id"], []), log.get(t["id"], []), outcomes.get(t["id"]))
              for i, t in enumerate(tasks, 1)]
    added = [t for t in tasks if t["added"]]
    if added:
        lines += ["", "## Added along the way", ""] + [f"- {t['id']}: {t['what']}" for t in added]
    lines += ["", "## Task details", ""]
    for t in tasks:
        evidence = next((e for _, _, e in reversed(log.get(t["id"], [])) if e and e != "-"), "none yet")
        lines.append(f"- {t['id']}: plan.md section \"Task {t['id']}\"; live log log/run-log.md; evidence {evidence}")
    out = os.path.join(state_dir, "PROGRESS.md")
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--state-dir", required=True, help="state folder holding tasks.csv. Example: docs/proj-123/autopilot")
    ap.add_argument("--journals", nargs="*", help="journal folders; default: the workflows folder of every session in inputs.json")
    args = ap.parse_args()
    dirs = args.journals
    if dirs is None:
        inputs = statefiles.read_json_safe(os.path.join(args.state_dir, "inputs.json"))
        dirs = statefiles.journal_dirs(inputs if isinstance(inputs, dict) else {})
    if not dirs:
        # Normal before the first stage launches: every row shows "Not started".
        print("note: no journal folder found; building from tasks.csv and the run log only")
    print(build(args.state_dir, dirs))
