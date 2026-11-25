"""Rebuild the Timeline section of <state-dir>/TIMELINE.md from the run's log files, oldest first.
run_state.py next calls it on every tick, so the timeline never goes stale and nobody rebuilds it by
hand. No LLM involved, so a refresh costs no tokens. Only the text between the timeline:begin and
timeline:end lines is rewritten; anything else in TIMELINE.md (an audit note, a summary) is kept.

Sources, all under --state-dir (a missing file is skipped):
  log/run-log.md        | when | task | what happened | evidence |       -> verifier rows
  log/decisions.md      | when | decision | options | why | cost |      -> coordinator decisions
  log/side-effects.md   | when | kind | count | note |                   -> sends, pushes, deploys
  log/owner-feedback.md | when | class | skill | missed | like | quote | -> owner messages
  log/status-log.md     | when | what |                                 -> Now block rewrites
  log/skill-friction.md | when | step | what did not fit | instead |    -> skill workarounds
  log/box-health.md     | when | result | warnings |                    -> machine health (not OK only)
  log/quota-log.md      | when | 5h | 7d | reset | action |             -> tick actions other than WAIT
  reports/*.md          file name YYYY-MM-DD-HHMM[-x].md                 -> saved reports
A row whose first cell is not a "Day MM-DD HH:MM" time is left out and counted in the header line.

Usage: python timeline.py --state-dir docs/proj-123/autopilot
"""
import argparse
import glob
import os
import re
import tempfile
from datetime import datetime

import statefiles

BEGIN = "<!-- timeline:begin - scripts/timeline.py rewrites this section every tick; do not edit it -->"
END = "<!-- timeline:end -->"
TEXT_CHARS = 160  # keeps each row readable on a phone
REPORT_NAME = re.compile(r"^(\d{4})-(\d\d)-(\d\d)-(\d\d)(\d\d)")
DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def short(text):
    text = " ".join(str(text).split())
    return text if len(text) <= TEXT_CHARS else text[:TEXT_CHARS - 3] + "..."


def cell(row, i):
    return row[i] if len(row) > i else ""


# file -> (who, function row -> what); "what" None drops the row
SOURCES = [
    ("run-log.md", "verifier", lambda r: f"{cell(r, 1)}: {cell(r, 2)}"),
    ("decisions.md", "coordinator", lambda r: f"decision: {cell(r, 1)}" + (f" ({cell(r, 3)})" if cell(r, 3) else "")),
    ("side-effects.md", "coordinator", lambda r: f"{cell(r, 1)} x{cell(r, 2)}: {cell(r, 3)}"),
    ("owner-feedback.md", "owner", lambda r: f"owner {cell(r, 1)}: {cell(r, 5)}"),
    ("status-log.md", "coordinator", lambda r: f"status: {cell(r, 1)}"),
    ("skill-friction.md", "coordinator", lambda r: f"friction at {cell(r, 1)}: {cell(r, 2)}"),
    ("box-health.md", "box", lambda r: None if cell(r, 1).startswith("BOX OK") else f"box: {cell(r, 1)} {cell(r, 2)}"),
    ("quota-log.md", "tick", lambda r: None if cell(r, 4) in ("", "WAIT") else f"tick: {cell(r, 4)} (5h {cell(r, 1)}, 7d {cell(r, 2)})"),
]


def collect(state):
    """(events, skipped): events are (sort key, when, who, what, source), in file order within a source."""
    events, skipped = [], 0
    for name, who, shape in SOURCES:
        for n, row in enumerate(statefiles.table_rows(os.path.join(state, "log", name)), 1):
            key = statefiles.day_key(row[0])
            if key is None:
                skipped += 1
                continue
            what = shape(row)
            if what:
                events.append((key, row[0], who, short(what), f"log/{name} row {n}"))
    for path in sorted(glob.glob(os.path.join(state, "reports", "*.md"))):
        m = REPORT_NAME.match(os.path.basename(path))
        if not m:
            continue
        y, mo, d, h, mi = (int(x) for x in m.groups())
        when = f"{DAYS[datetime(y, mo, d).weekday()]} {mo:02d}-{d:02d} {h:02d}:{mi:02d}"
        events.append((statefiles.day_key(when), when, "coordinator", "report saved", f"reports/{os.path.basename(path)}"))
    events.sort(key=lambda e: e[0])  # stable: rows of one minute keep their file order  # stable: rows of one minute keep their file order
    return events, skipped


def section(events, skipped, now):
    lines = [f"Built {now.strftime('%a %m-%d %H:%M')} by scripts/timeline.py from log/*.md and reports/. "
             f"{len(events)} events, oldest first. Times are local, Day MM-DD HH:MM, from each row's own clock."
             + (f" {skipped} rows without a time were left out." if skipped else ""),
             "", "| When | Who | What | Source |", "|---|---|---|---|"]
    lines += ["| " + " | ".join(c.replace("|", "\\|") for c in (when, who, what, src)) + " |"
              for _, when, who, what, src in events]
    return lines


def write(path, goal, lines):
    """Replace the timeline section (or add it at the end), atomically, keeping every other line."""
    text = statefiles.read_text(path) if os.path.exists(path) else f"# {goal} -- timeline\n\n"
    start = text.find(BEGIN)
    end = text.find(END, start + 1) if start >= 0 else -1
    if start < 0 or end < 0:
        before, after = text.rstrip("\n") + "\n\n## Timeline\n\n", "\n"
    else:
        before, after = text[:start], text[end + len(END):]
    body = before + BEGIN + "\n" + "\n".join(lines) + "\n" + END + after
    handle, temp_path = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(path)), suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as f:
            f.write(body if body.endswith("\n") else body + "\n")
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def build(state, now=None):
    events, skipped = collect(state)
    inputs = statefiles.read_json_safe(os.path.join(state, "inputs.json"))
    goal = inputs.get("goal", "run") if isinstance(inputs, dict) else "run"
    path = os.path.join(state, "TIMELINE.md")
    write(path, goal, section(events, skipped, now or datetime.now()))
    return path


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--state-dir", required=True, help="state folder. Example: docs/proj-123/autopilot")
    print(build(ap.parse_args().state_dir))
