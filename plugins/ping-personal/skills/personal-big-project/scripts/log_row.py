"""Append one row to a run's log files with a real-clock time, in the exact shape check_run.py reads.
Agents call this instead of editing the logs by hand, so no row is malformed, no time is guessed and
no side effect goes past its cap.

  python log_row.py run      --state-dir D --task T3 --what "passed: ALL OK" [--evidence <path>]
      -> one row in log/run-log.md: | Day MM-DD HH:MM | T3 | passed: ALL OK | <path> |
  python log_row.py effect   --state-dir D --kind mail --count 1 --note "test statement" [--key send-T3-1]
      -> one row in log/side-effects.md, written BEFORE the action. Refused (exit 2, nothing written)
         when the kind has no cap in inputs.json "caps" or the new total would pass the cap. --key names
         one real action: a retry of the same action passes the same key and is not counted twice.
  python log_row.py baseline --state-dir D <repo-relative path> [...]   |   --none
      -> "<sha256>  <path>" lines in baseline-hashes.txt (repo root = inputs.json "repoPath", read from the
         state folder when relative). Hash only files that must not change during the run. --none writes
         "none" for a run with nothing to baseline.
Exit 0 = written (or already logged), 2 = refused.
"""
import argparse
import hashlib
import os
import sys
from datetime import datetime

import statefiles

DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")  # fixed English names: the locale never changes them
HEADERS = {"run-log.md": "| When | Task | What happened | Evidence |",
           "side-effects.md": "| When | Kind | Count | Note |"}


def refuse(msg):
    print(f"REFUSED: {msg}")
    sys.exit(2)


def now_text():
    t = datetime.now()
    return f"{DAYS[t.weekday()]} {t:%m-%d %H:%M}"


def cell(text):
    return " ".join(str(text).split()).replace("|", "\\|")


def append_row(path, cells):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fresh = not os.path.exists(path) or not statefiles.read_text(path).strip()
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        if fresh:
            header = HEADERS[os.path.basename(path)]
            f.write(header + "\n" + "|---" * (header.count("|") - 1) + "|\n")
        f.write("| " + " | ".join(cell(c) for c in cells) + " |\n")


def inputs_of(state):
    inputs = statefiles.read_json_safe(os.path.join(state, "inputs.json"))
    if not isinstance(inputs, dict):
        refuse(f"{state}/inputs.json is missing or not valid JSON")
    return inputs


def effect(state, kind, count, note, key):
    caps = inputs_of(state).get("caps")
    caps = caps if isinstance(caps, dict) else {}
    if kind not in caps:
        refuse(f"kind '{kind}' has no cap in inputs.json; allowed kinds: {', '.join(sorted(caps)) or 'none'}")
    if count < 1:
        refuse("count must be 1 or more")
    path = os.path.join(state, "log", "side-effects.md")
    rows = statefiles.table_rows(path)
    if key and any(len(r) > 3 and r[3].startswith(f"[{key}]") for r in rows):
        print(f"ALREADY LOGGED: {key}")
        return
    used = sum(int(r[2]) for r in rows if len(r) > 2 and r[1] == kind and r[2].isdigit())
    if used + count > caps[kind]:
        refuse(f"{kind}: {used} used + {count} would pass the cap {caps[kind]}; do not act")
    append_row(path, [now_text(), kind, count, (f"[{key}] " if key else "") + note])
    print(f"LOGGED {kind} {used + count} of {caps[kind]}")


def baseline(state, paths, none):
    out = os.path.join(state, "baseline-hashes.txt")
    if none:
        with open(out, "a", encoding="utf-8", newline="\n") as f:
            f.write("none\n")
        return
    if not paths:
        refuse("give repo-relative paths, or --none")
    root = os.path.join(state, str(inputs_of(state).get("repoPath", "")))
    lines = []
    for p in paths:
        full = os.path.join(root, p)
        if not os.path.isfile(full):
            refuse(f"not a file under the repo root: {p}")
        with open(full, "rb") as f:
            lines.append(f"{hashlib.sha256(f.read()).hexdigest()}  {p.replace(os.sep, '/')}\n")
    with open(out, "a", encoding="utf-8", newline="\n") as f:
        f.writelines(lines)
    print(f"BASELINED {len(lines)} file(s)")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("what", choices=["run", "effect", "baseline"])
    ap.add_argument("paths", nargs="*", help="baseline only: repo-relative files. Example: reports/expected.csv")
    ap.add_argument("--state-dir", required=True, help="state folder. Example: docs/proj-123/autopilot")
    ap.add_argument("--task", help="run: task id, or 'stage' for the stage check. Example: T3")
    ap.add_argument("--what", dest="text", help="run: what happened, plain words. Example: passed: ALL CHECKS PASS")
    ap.add_argument("--evidence", default="-", help="run: evidence path or command. Example: logs/t3.txt")
    ap.add_argument("--kind", help="effect: a kind named in inputs.json caps. Example: mail")
    ap.add_argument("--count", type=int, default=1, help="effect: how many. Example: 1")
    ap.add_argument("--note", default="", help="effect: what and to whom. Example: test statement to the owner")
    ap.add_argument("--key", default="", help="effect: one id per real action, reused by a retry. Example: send-T3-1")
    ap.add_argument("--none", action="store_true", help="baseline: nothing to baseline in this run")
    a = ap.parse_args()
    if a.what == "run":
        if not a.task or not a.text:
            refuse("run needs --task and --what")
        append_row(os.path.join(a.state_dir, "log", "run-log.md"), [now_text(), a.task, a.text, a.evidence])
    elif a.what == "effect":
        if not a.kind:
            refuse("effect needs --kind")
        effect(a.state_dir, a.kind, a.count, a.note, a.key)
    else:
        baseline(a.state_dir, a.paths, a.none)


if __name__ == "__main__":
    main()
