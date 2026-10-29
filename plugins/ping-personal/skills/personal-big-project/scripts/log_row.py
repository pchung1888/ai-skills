"""Append one row to a run's log files with a real-clock time, in the exact shape check_run.py reads.
Agents call this instead of editing the logs by hand, so no row is malformed, no time is guessed and
no side effect goes past its cap.

  python log_row.py run      --state-dir D --task T3 --what "passed: ALL OK" [--evidence <path>]
  python log_row.py run      --state-dir D --task T3 --what-file log/verify-T3.txt [--evidence <path>]
      -> one row in log/run-log.md: | Day MM-DD HH:MM | T3 | passed: ALL OK | <path> |
         --what-file reads the text from a file, so command output never passes through a shell.
  python log_row.py effect   --state-dir D --kind mail --count 1 --note "test statement" [--key send-T3-1]
      -> one row in log/side-effects.md, written BEFORE the action. Refused (exit 2, nothing written)
         when the kind has no cap in inputs.json "caps" or the new total would pass the cap. --key names
         one real action: a retry of the same action passes the same key and is not counted twice.
         A retry writes a count-0 row and exits 3 (ALREADY LOGGED); past MAX_REPLAYS retries it is refused.
         --kind push also needs --ref <branch> when inputs.json "protectedBranches" is not empty, and is
         refused when that branch is protected (the target branch of an open review request: pushing
         to it can merge the request). Example: --ref topic/123-fixes
  python log_row.py status   --state-dir D [--note "stage 2 running"]
      -> one row in log/status-log.md each time STATUS.md's Now block is rewritten (scorecard: statusGap).
  python log_row.py baseline --state-dir D <repo-relative path> [...]   |   --none
      -> "<sha256>  <path>" lines in baseline-hashes.txt (repo root = inputs.json "repoPath", read from the
         state folder when relative). Hash only files that must not change during the run. --none writes
         "none" for a run with nothing to baseline.
  python log_row.py send     --state-dir D --kind mail --count 2 --note "status mails" --key T5-1 [--retry] -- <command ...>
      -> the effect row first, then runs the command and exits with its exit code. Refused (exit 2) means the
         command never ran. A counted key exits 3 without running, unless --retry says the earlier try did
         not happen. Example command: pwsh -NoProfile -File tests/send-status.ps1
  python log_row.py usage    --state-dir D
      -> one line per capped kind: "OK|WARN|FULL <kind> <used> of <cap>"; WARN from 80% of the cap.
  python log_row.py raise-cap --state-dir D --kind mail --to 400 --note "<the owner's words>"
      -> the owner's answer to a cap question: sets inputs.json caps.<kind> and adds a log/decisions.md row.
         Refused below what is already used.
Exit 0 = written, 2 = refused, 3 = already logged (a retry of a counted action); send exits with its command's code.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime

import statefiles

DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")  # fixed English names: the locale never changes them
MAX_REPLAYS = 2  # retries allowed per --key; more means the action is repeating, not retrying
WARN_PCT = 80  # usage prints WARN from this share of a cap, so the owner hears before the cap stops a task
HEADERS = {"run-log.md": "| When | Task | What happened | Evidence |",
           "side-effects.md": "| When | Kind | Count | Note |",
           "decisions.md": "| When | Decision | Options | Why | Cost |",
           "status-log.md": "| When | What |"}


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


def check_push(inputs, ref):
    protected = [str(b).strip() for b in inputs.get("protectedBranches") or [] if str(b).strip()]
    if not protected:
        return
    if not ref:
        refuse(f"push needs --ref <branch>: protected branches are {', '.join(protected)}")
    branch = ref.strip()
    if branch.startswith("refs/heads/"):
        branch = branch[len("refs/heads/"):]
    if branch in protected:
        refuse(f"{branch} is protected (the target of an open review request); do not push to it")


def effect(state, kind, count, note, key, ref=""):
    inputs = inputs_of(state)
    if kind == "push":
        check_push(inputs, ref)
    caps = inputs.get("caps")
    caps = caps if isinstance(caps, dict) else {}
    if kind not in caps:
        refuse(f"kind '{kind}' has no cap in inputs.json; allowed kinds: {', '.join(sorted(caps)) or 'none'}")
    if count < 1:
        refuse("count must be 1 or more")
    path = os.path.join(state, "log", "side-effects.md")
    rows = statefiles.table_rows(path)
    tagged = [r for r in rows if len(r) > 3 and r[3].startswith(f"[{key}]")] if key else []
    if tagged:
        replays = sum(1 for r in tagged if r[2] == "0")
        if replays >= MAX_REPLAYS:
            refuse(f"key {key} already retried {replays} times; do not act")
        append_row(path, [now_text(), kind, 0, f"[{key}] replay: {note}"])
        print(f"ALREADY LOGGED: {key} (retry {replays + 1} of {MAX_REPLAYS}, not counted)")
        return 3
    used = used_of(rows, kind)
    if used + count > caps[kind]:
        refuse(f"CAP REACHED: {kind}: {used} used + {count} would pass the cap {caps[kind]}; do not act. "
               "Stop this task and report it: the coordinator asks the owner by phone to raise the cap or stop")
    append_row(path, [now_text(), kind, count, (f"[{key}] " if key else "") + note])
    print(f"LOGGED {kind} {used + count} of {caps[kind]}")
    return 0


def used_of(rows, kind):
    return sum(int(r[2]) for r in rows if len(r) > 2 and r[1] == kind and r[2].isdigit())


def send(state, kind, count, note, key, ref, retry, command):
    """Log first, then run the sending command, so a send can never happen before its row exists."""
    if not command:
        refuse("send needs the sending command after --. Example: -- pwsh -NoProfile -File send-test.ps1")
    if effect(state, kind, count, note, key, ref) == 3 and not retry:
        sys.exit(3)  # counted before; --retry only when the earlier try did not happen
    sys.stdout.flush()
    sys.exit(subprocess.run(command).returncode)


def usage(state):
    """One line per capped kind: OK, WARN (80% or more of the cap) or FULL. The tick sends WARN and FULL to the phone."""
    caps = inputs_of(state).get("caps") or {}
    rows = statefiles.table_rows(os.path.join(state, "log", "side-effects.md"))
    for kind, cap in sorted(caps.items()):
        used = used_of(rows, kind)
        word = "FULL" if used >= cap else "WARN" if used * 100 >= cap * WARN_PCT else "OK"
        print(f"{word} {kind} {used} of {cap}")


def raise_cap(state, kind, to, note):
    """The owner's answer to a cap question: set the new cap in inputs.json and log it as a decision."""
    if to is None or not note:
        refuse("raise-cap needs --kind, --to and --note (the owner's words)")
    inputs = inputs_of(state)
    caps = inputs.get("caps") if isinstance(inputs.get("caps"), dict) else {}
    used = used_of(statefiles.table_rows(os.path.join(state, "log", "side-effects.md")), kind)
    if to < used:
        refuse(f"{kind}: new cap {to} is below the {used} already used")
    old = caps.get(kind, 0)
    inputs["caps"] = dict(caps, **{kind: to})
    with open(os.path.join(state, "inputs.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(inputs, f, indent=2)
    append_row(os.path.join(state, "log", "decisions.md"),
               [now_text(), f"{kind} cap {old} -> {to}", "raise the cap or stop", note, f"{used} used so far"])
    print(f"RAISED {kind} cap {old} -> {to}")


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
    ap.add_argument("what", choices=["run", "effect", "send", "usage", "raise-cap", "status", "baseline"])
    ap.add_argument("paths", nargs="*", help="baseline only: repo-relative files. Example: reports/expected.csv")
    ap.add_argument("--state-dir", required=True, help="state folder. Example: docs/proj-123/autopilot")
    ap.add_argument("--task", help="run: task id, or 'stage' for the stage check. Example: T3")
    ap.add_argument("--what", dest="text", help="run: what happened, plain words. Example: passed: ALL CHECKS PASS")
    ap.add_argument("--what-file", help="run: a file holding the --what text. Example: log/verify-T3.txt")
    ap.add_argument("--evidence", default="-", help="run: evidence path or command. Example: logs/t3.txt")
    ap.add_argument("--kind", help="effect: a kind named in inputs.json caps. Example: mail")
    ap.add_argument("--count", type=int, default=1, help="effect: how many. Example: 1")
    ap.add_argument("--note", default="", help="effect: what and to whom. Example: test statement to the owner")
    ap.add_argument("--key", default="", help="effect: one id per real action, reused by a retry. Example: send-T3-1")
    ap.add_argument("--ref", default="", help="effect push: the branch pushed to. Example: topic/123-fixes")
    ap.add_argument("--retry", action="store_true", help="send: run again although the key was counted; only when the earlier try did not happen")
    ap.add_argument("--to", type=int, help="raise-cap: the new cap. Example: 400")
    ap.add_argument("--none", action="store_true", help="baseline: nothing to baseline in this run")
    argv = sys.argv[1:]
    command = argv[argv.index("--") + 1:] if "--" in argv else []
    a = ap.parse_args(argv[:argv.index("--")] if "--" in argv else argv)
    if a.what == "run":
        if a.what_file:
            try:
                a.text = statefiles.read_text(a.what_file).strip()
            except OSError as e:
                refuse(f"cannot read --what-file: {e}")
        if not a.task or not a.text:
            refuse("run needs --task and --what or --what-file")
        append_row(os.path.join(a.state_dir, "log", "run-log.md"), [now_text(), a.task, a.text, a.evidence])
    elif a.what == "effect":
        if not a.kind:
            refuse("effect needs --kind")
        sys.exit(effect(a.state_dir, a.kind, a.count, a.note, a.key, a.ref))
    elif a.what == "send":
        if not a.kind:
            refuse("send needs --kind")
        send(a.state_dir, a.kind, a.count, a.note, a.key, a.ref, a.retry, command)
    elif a.what == "status":
        append_row(os.path.join(a.state_dir, "log", "status-log.md"), [now_text(), a.note or "Now block rewritten"])
    elif a.what == "usage":
        usage(a.state_dir)
    elif a.what == "raise-cap":
        if not a.kind:
            refuse("raise-cap needs --kind")
        raise_cap(a.state_dir, a.kind, a.to, a.note)
    else:
        baseline(a.state_dir, a.paths, a.none)


if __name__ == "__main__":
    main()
