"""Check a run's state folder against the rules the owner cannot see from their phone. The final stage
must print RUN CHECK PASS before the run may call itself done; the tick may run it any time.
It fails closed: a missing file or a row it cannot read is a named FAIL, never a silent pass.

  python check_run.py --state-dir docs/proj-123/autopilot --transcript <session>.jsonl

Prints one line per check, "PASS <name>" or "FAIL <name>: <why>". Exit 1 on any FAIL.

Checks and the files they read (all under --state-dir unless noted):
  required-files  inputs.json, STATUS.md, tasks.csv, log/run-log.md, log/side-effects.md,
                  baseline-hashes.txt (may be empty), run-state.json, OWNER-REPORT.md all exist
  inputs          inputs.json has caps (kind -> whole number) and unattendedSince (ISO time; no zone = UTC)
  log-times       every log/run-log.md row starts with a real-clock time "Day MM-DD HH:MM"
  report-plain    reports/*.md hold no ids, hashes or run codes (the owner reads them on a phone), unless
                  inputs.json "report" has "ids": true (the owner asked for task ids at start)
  table-rows      every task id in tasks.csv still has a row in the Tasks section of STATUS.md
  table-fresh     the first line of the STATUS.md Tasks section starts "Built Day MM-DD HH:MM" (build_table.py
                  writes it) and that stamp is not older than the newest log/run-log.md row by more than
                  the tick interval (inputs.json report.everyMin, default 30) plus 5 minutes; a frozen table
                  fails. Example: stamp "Built Sat 10-17 08:00", newest row "Sat 10-17 09:00", every 30 -> FAIL
  reports-saved   when run-state.json "lastReportedLogRows" is above 0, reports/ holds at least one .md file,
                  and every reports/*.md name is YYYY-MM-DD-HHMM.md, optionally with a -suffix before .md.
                  Example: reports/2026-10-17-0830.md or reports/2026-10-17-0830-final.md
  side-effects    log/side-effects.md totals per kind stay within inputs.json "caps"; every row is
                  "| Day MM-DD HH:MM | kind | whole number | note |" and its kind has a cap
  baselines       every line of baseline-hashes.txt ("<sha256>  <repo-relative path>", written by
                  log_row.py baseline; a "*" before the path and a "none" line are accepted) is well formed
                  and its file is unchanged; repo root = inputs.json "repoPath". A path listed in inputs.json
                  "baselineChangesApproved" (repo-relative, forward or back slashes; set at the door with
                  the owner present) may change without a FAIL.
                  Example: "baselineChangesApproved": ["baseline/expected.txt"]
  verdict         OWNER-REPORT.md contains run-state.json's verdict string exactly; the verdict is
                  "PASS (P of T tasks; N deferred, M by agents ...)", "FAIL (done command: <last line>; P of T
                  tasks; ...)" or "STOPPED (reason; P of T tasks passed;
                  N deferred, M by agents ...)", and its counts equal the outcomes in run-state.json
  no-questions    --transcript is required: no AskUserQuestion call after inputs.json "unattendedSince"
  remote-tags     git ls-remote --tags <remote> shows no tag added or moved since inputs.json remoteTagsAtStart
  remote-branches git ls-remote --heads <remote> differs from remoteHeadsAtStart only on inputs.json "branch"
  final-commit    the remote head of inputs.json "branch" equals the local HEAD of repoPath
  owner-report    OWNER-REPORT.md has the headings "## Evidence" and "## Merge danger", and the merge danger
                  section says "one-way door" or "two-way door" for the run as a whole
  owner-feedback  log/owner-feedback.md has a row for every owner message after unattendedSince (ticks, resume
                  prompts and notices are not owner messages), each "| when | class | skill | missed what |
                  like | quote |" with a class from statefiles.OWNER_CLASSES. Only rows whose minute is strictly
                  after the unattendedSince minute count (setup talk stamped in that same minute does not).
                  Each message is matched one-to-one, oldest first, to a row timed from 1 minute before to 5
                  minutes after the message's local time. Extra rows are fine (one message may carry a fix and
                  a complaint). FAIL names how many messages have no row and the first one's local time.
                  Messages after run-state.json "closed.at" are not counted (the session went on after the run).
                  Example: a message at Sat 10-17 01:00 is matched by a row stamped Sat 10-17 01:03
  owner-score     log/owner-feedback.md has a class "score" row whose like cell is 1-5 (the closing ask)
  deliverable     GOAL-BRIEF.md has a non-empty "## Deliverable" section (SKILL.md start step 2)
  audit-first     GOAL-BRIEF.md has a non-empty "## Old version" section; unless it starts with "none", the state
                  folder holds a non-empty audit-old.md (SKILL.md rule 17). Example section: "web/holiday-v1.asp,
                  build skill react-vite-start"
  ui-browser      every UI task (stage spec "ui": true, or a spec text, check or plan.md "Task <id>" section
                  naming a .html/.jsx/.tsx/.vue page; a step with "ui": false is never a UI task, so a review
                  or evidence task that only names a page opts out. Only an explicit false opts out)
                  has a check that launches Chromium (playwright, puppeteer or chromium in the command or a
                  file it names); a run whose diff from baseCommit changes such a page needs one (rule 13).
                  Each UI task not deferred in run-state.json leaves proof in proof/<task id>/: a PNG
                  screenshot or a Playwright trace zip (context.tracing.stop(path=...)). Example: proof/T3/grid.png
  fidelity        when GOAL-BRIEF.md names an old version and the run has a UI task, fidelity/index.html (old and
                  new page side by side, per state; the owner signs off from it) exists, names no NOT-RUN state,
                  and tags every state with its measured count. Example: <div data-state="edit" data-differences="0">
  not-run-claims  when the run log names a NOT-RUN check or a task stayed not-run, OWNER-REPORT.md and reports/*.md
                  never say "complete" or "best" ("not complete" and "incomplete" are fine; SKILL.md rule 2)
The result lines are also written to log/run-check.txt; the scorecard reads its safety rows from there.
The three git checks run git inside inputs.json "repoPath" (read from the state folder when relative), which must
be the root of a git repo; remote = inputs.json "remote" (default origin). A git failure is a named FAIL.
"""
import argparse
import csv
import glob
import hashlib
import os
import re
import subprocess
import zipfile
from datetime import datetime, timedelta

import statefiles

# Shared with the other scripts; the old local names stay as aliases (tests import check_run.DAY_TIME).
DAY_TIME = statefiles.DAY_TIME
IDS = statefiles.OWNER_CODES
SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")
DEFERRED_COUNTS = re.compile(r"(\d+) deferred, (\d+) by agents")
PASS_VERDICT = re.compile(r"^(?:PASS \(|FAIL \(done command: [^;]*; )(\d+) of (\d+) tasks;")
STOPPED_VERDICT = re.compile(r"^STOPPED \([^;]*; (\d+) of (\d+) tasks passed;")
REQUIRED_FILES = ["inputs.json", "STATUS.md", "tasks.csv", os.path.join("log", "run-log.md"),
                  os.path.join("log", "side-effects.md"), "baseline-hashes.txt", "run-state.json", "OWNER-REPORT.md"]


def check_inputs(inputs):
    if not isinstance(inputs, dict):
        return "inputs.json is missing or not valid JSON"
    caps = inputs.get("caps")
    if not isinstance(caps, dict):
        return "inputs.json has no caps object (kind -> total allowed)"
    badcaps = [k for k, v in caps.items() if not isinstance(v, int) or isinstance(v, bool) or v < 0]
    if badcaps:
        return f"caps must be whole numbers, bad: {', '.join(badcaps)}"
    since = inputs.get("unattendedSince")
    if not since:
        return "inputs.json has no unattendedSince"
    try:
        statefiles.parse_time(since)
    except ValueError:
        return f"unattendedSince is not an ISO time: {since}"
    if not isinstance(inputs.get("baseCommit"), str) or not inputs["baseCommit"].strip():
        return "inputs.json has no baseCommit (the commit HEAD pointed at when the run started)"
    for key in ("remoteTagsAtStart", "remoteHeadsAtStart"):
        if not isinstance(inputs.get(key), list):
            return f"inputs.json has no {key} list ('<sha> <ref>' lines of git ls-remote at start)"
    return ""


def check_log_times(state):
    bad = [r[0] for r in statefiles.table_rows(os.path.join(state, "log", "run-log.md")) if not DAY_TIME.match(r[0])]
    return f"{len(bad)} run-log rows without a Day MM-DD HH:MM time, first: '{bad[0]}'" if bad else ""


def check_report_plain(state, inputs):
    report = inputs.get("report") if isinstance(inputs.get("report"), dict) else {}
    if report.get("ids") is True:  # the owner asked for task ids in their reports at start
        return ""
    hits = []
    for path in sorted(glob.glob(os.path.join(state, "reports", "*.md"))):
        hits += [f"{os.path.basename(path)}: {c}" for c in statefiles.owner_codes(statefiles.read_text(path))]
    return f"{len(hits)} codes in owner reports, first: {hits[0]}" if hits else ""


def check_table_rows(state):
    tasks_path = os.path.join(state, "tasks.csv")
    if not os.path.exists(tasks_path):
        return "tasks.csv not found"
    with open(tasks_path, newline="", encoding="utf-8-sig") as f:
        ids = [(r.get("id") or "").strip() for r in csv.DictReader(f)]
    shown = {r[2] for r in statefiles.task_rows(os.path.join(state, "STATUS.md")) if len(r) > 2}
    gone = [i for i in ids if i and i not in shown]
    return f"tasks missing from the STATUS.md Tasks section (run build_table.py): {', '.join(gone)}" if gone else ""


BUILT = re.compile(r"^Built (\S+ \d\d-\d\d \d\d:\d\d)\b")
REPORT_NAME = re.compile(r"^\d{4}-\d\d-\d\d-\d{4}(-[A-Za-z0-9_.-]+)?\.md$")


def minute_of(cell):
    """datetime of a 'Day MM-DD HH:MM' log time, or None. The year is fixed (a leap year), so only differences matter."""
    key = statefiles.day_key(cell)
    # ponytail: no year, so a run crossing New Year compares January as earlier; add the year if that happens
    return datetime.strptime("2000-" + key, "%Y-%m-%d %H:%M") if key else None


def check_table_fresh(state, inputs):
    """The Tasks table was rebuilt recently: its 'Built' stamp is within one tick (+5 min) of the newest log row."""
    status = os.path.join(state, "STATUS.md")
    if not os.path.isfile(status):
        return "STATUS.md not found"
    _, section, _ = statefiles.task_section(statefiles.read_text(status))
    if section is None:
        return "STATUS.md has no Tasks section (run build_table.py)"
    first = next((l.strip() for l in section.splitlines() if l.strip()), "")
    found = BUILT.match(first)
    built = minute_of(found.group(1)) if found else None
    if not built:
        return "the STATUS.md Tasks section does not start with 'Built Day MM-DD HH:MM' (run build_table.py)"
    stamps = [minute_of(r[0]) for r in statefiles.table_rows(os.path.join(state, "log", "run-log.md"))]
    newest = max((t for t in stamps if t), default=None)
    report = inputs.get("report") if isinstance(inputs.get("report"), dict) else {}
    every = report.get("everyMin")
    every = every if isinstance(every, int) and not isinstance(every, bool) else 30
    if newest and newest - built > timedelta(minutes=every + 5):
        late = int((newest - built).total_seconds() // 60)
        return (f"the Tasks table was built {late} minutes before the newest run-log row "
                f"(limit {every + 5}); it is frozen, run build_table.py")
    return ""


def check_reports_saved(state):
    """Reports are kept on disk, not only posted: once one was posted, reports/ holds well-named files."""
    run_state = statefiles.read_json_safe(os.path.join(state, "run-state.json"))
    posted = run_state.get("lastReportedLogRows") if isinstance(run_state, dict) else 0
    files = sorted(os.path.basename(p) for p in glob.glob(os.path.join(state, "reports", "*.md")))
    timed = [n for n in files if REPORT_NAME.match(n)]
    # Other notes (a box-health diagnosis) may live in reports/ too; only the timed posts are counted.
    if isinstance(posted, int) and not isinstance(posted, bool) and posted > 0 and not timed:
        return (f"{posted} log rows were reported but reports/ holds no YYYY-MM-DD-HHMM.md file; "
                "save every report with log_row.py report")
    return ""


def check_side_effects(state, inputs):
    raw_caps = inputs.get("caps") if isinstance(inputs.get("caps"), dict) else {}
    caps = {k: v for k, v in raw_caps.items() if isinstance(v, int) and not isinstance(v, bool)}  # bad caps are the inputs check's FAIL
    used, problems = {}, []
    for r in statefiles.table_rows(os.path.join(state, "log", "side-effects.md")):
        if len(r) < 3 or not r[2].isdigit():
            problems.append(f"row not '| when | kind | whole number | note |': {' | '.join(r)}")
            continue
        if r[1] not in caps:
            problems.append(f"kind '{r[1]}' has no cap in inputs.json")
        used[r[1]] = used.get(r[1], 0) + int(r[2])
    problems += [f"{k} {n} > cap {caps[k]}" for k, n in used.items() if k in caps and n > caps[k]]
    return "; ".join(problems) if problems else ""


def check_baselines(state, inputs):
    hashes = os.path.join(state, "baseline-hashes.txt")
    if not os.path.exists(hashes):
        return "baseline-hashes.txt not found"
    # A relative repoPath is read from the state folder (used by the eval fixtures).
    root = os.path.join(state, str(inputs.get("repoPath", "")))
    approved = inputs.get("baselineChangesApproved")
    approved = {str(a).replace("\\", "/").lstrip("*") for a in approved} if isinstance(approved, list) else set()
    changed, malformed = [], []
    for line in statefiles.read_text(hashes).splitlines():
        if not line.strip() or line.strip() == "none":
            continue
        parts = line.strip().split(None, 1)
        if len(parts) != 2 or not SHA256.match(parts[0]):
            malformed.append(line.strip()[:60])
            continue
        path = os.path.join(root, parts[1].lstrip("*"))  # sha256sum -b marks a path with "*"
        actual = hashlib.sha256(open(path, "rb").read()).hexdigest() if os.path.isfile(path) else "missing"
        if actual != parts[0].lower() and parts[1].lstrip("*").replace("\\", "/") not in approved:
            changed.append(parts[1])
    problems = []
    if malformed:
        problems.append(f"{len(malformed)} malformed hash lines, first: '{malformed[0]}'")
    if changed:
        problems.append(f"baseline files changed after capture: {', '.join(changed)}")
    return "; ".join(problems)


def check_verdict(state):
    run_state = statefiles.read_json_safe(os.path.join(state, "run-state.json"))
    verdict = run_state.get("verdict") if isinstance(run_state, dict) else None
    if not isinstance(verdict, str) or not verdict.strip():
        return "run-state.json has no verdict"
    owner = os.path.join(state, "OWNER-REPORT.md")
    if not os.path.exists(owner):
        return "OWNER-REPORT.md not found"
    report = statefiles.read_text(owner)
    if verdict not in report:
        return f"OWNER-REPORT.md does not contain the verdict '{verdict}'"
    deferred = by_agents = passed = 0
    ids = set()
    for stage in run_state.get("stages") or []:
        spec = statefiles.read_json_safe(os.path.join(state, "stages", str(stage.get("name")) + ".json")) or {}
        for step in spec.get("steps", []) if isinstance(spec, dict) else []:
            ids.update(t.get("id") for t in (step if isinstance(step, list) else [step]) if isinstance(t, dict))
        for tid, info in (stage.get("tasks") or {}).items():
            ids.add(tid)
            if isinstance(info, dict) and info.get("outcome") == "deferred":
                deferred += 1
                by_agents += info.get("deferredBy") == "agent"
            passed += isinstance(info, dict) and info.get("outcome") == "passed"
    total = len(ids)
    stopped = STOPPED_VERDICT.match(verdict)
    ok = PASS_VERDICT.match(verdict) or stopped
    if not ok:
        return "verdict must start with 'PASS (', 'FAIL (done command: ...;' or 'STOPPED (' and carry 'P of T tasks'"
    want = (passed, total) if stopped else (passed + deferred, total)
    if (int(ok.group(1)), int(ok.group(2))) != want:
        return f"verdict says {ok.group(1)} of {ok.group(2)} tasks; run-state.json has {want[0]} of {want[1]}"
    counted = DEFERRED_COUNTS.search(report)
    if not counted:
        return "OWNER-REPORT.md has no 'N deferred, M by agents' counts"
    if (int(counted.group(1)), int(counted.group(2))) != (deferred, by_agents):
        return (f"OWNER-REPORT.md says {counted.group(1)} deferred, {counted.group(2)} by agents; "
                f"run-state.json has {deferred} deferred, {by_agents} by agents")
    return ""


def check_no_questions(inputs, transcript):
    if not transcript:
        return "--transcript is required"
    if not os.path.isfile(transcript):
        return f"transcript not found: {transcript}"
    try:
        start = statefiles.parse_time(inputs.get("unattendedSince"))
    except (ValueError, TypeError):
        return "inputs.json has no usable unattendedSince"
    asked = []
    for d in statefiles.read_jsonl_safe(transcript):
        if d.get("type") != "assistant" or not d.get("timestamp"):
            continue
        content = (d.get("message") or {}).get("content")
        names = [c.get("name") for c in content if isinstance(c, dict) and c.get("type") == "tool_use"] if isinstance(content, list) else []
        try:
            when = statefiles.parse_time(d["timestamp"])
        except ValueError:
            continue
        if "AskUserQuestion" in names and when >= start:
            asked.append(d["timestamp"])
    return f"asked the owner {len(asked)} time(s) while unattended, first at {asked[0]}" if asked else ""


def check_owner_feedback(state, inputs, transcript):
    """A log/owner-feedback.md row for every owner message after unattendedSince, each row with one known class."""
    if not transcript or not os.path.isfile(transcript):
        return "--transcript is required"
    try:
        start = statefiles.parse_time(inputs.get("unattendedSince"))
    except (ValueError, TypeError):
        return "inputs.json has no usable unattendedSince"
    local_start = start.astimezone().replace(tzinfo=None, second=0, microsecond=0)
    closed = (statefiles.read_json_safe(os.path.join(state, "run-state.json")) or {}).get("closed")
    try:  # messages typed after run_state.py close belong to a later conversation in the same session
        end = statefiles.parse_time(closed["at"])
    except (KeyError, ValueError, TypeError):
        end = None
    sent = []  # local time of every owner message after unattendedSince
    for d in statefiles.read_jsonl_safe(transcript):
        try:
            when = statefiles.parse_time(d["timestamp"])
        except (KeyError, ValueError):
            continue
        if when >= start and (end is None or when <= end) and statefiles.is_owner_message(d):
            sent.append(when.astimezone().replace(tzinfo=None))
    rows = statefiles.table_rows(os.path.join(state, "log", "owner-feedback.md"))
    bad = [r[1] if len(r) > 1 else "?" for r in rows if len(r) < 6 or r[1] not in statefiles.OWNER_CLASSES]
    if bad:
        return f"rows with a class not in {', '.join(statefiles.OWNER_CLASSES)} (or fewer than 6 cells): {', '.join(bad)}"
    times = sorted(t for t in (row_time(r[0], local_start) for r in rows) if t and t > local_start)
    unmatched = []
    for m in sorted(sent):  # greedy, oldest message first; every window has the same width, so this is optimal
        low = m.replace(second=0, microsecond=0) - timedelta(minutes=1)
        pick = next((t for t in times if low <= t <= m + timedelta(minutes=5)), None)
        if pick is None:
            unmatched.append(m)
        else:
            times.remove(pick)
    if unmatched:
        return (f"{len(unmatched)} owner message(s) after unattendedSince have no feedback row within "
                f"-1/+5 minutes, first at {unmatched[0].strftime('%a %m-%d %H:%M')}; tag every owner message")
    return ""


def row_time(cell, local_start):
    """datetime of a 'Day MM-DD HH:MM' log time (the box's local clock, rule 6), or None when unreadable.
    An unreadable row matches no message, so a bad row can never hide a dropped one."""
    # ponytail: year comes from unattendedSince, so a run crossing New Year misreads January rows
    try:
        return datetime.strptime(f"{local_start.year} {cell.strip()[4:]}", "%Y %m-%d %H:%M")
    except ValueError:
        return None


def check_owner_score(state):
    rows = statefiles.table_rows(os.path.join(state, "log", "owner-feedback.md"))
    if any(len(r) > 4 and r[1] == "score" and r[4].strip() in ("1", "2", "3", "4", "5") for r in rows):
        return ""
    return "no owner score row (class score, Like 1-5); ask the owner for a 1-5 score at close"


GIT_TIMEOUT_S = 60


def git(repo, *args):
    """(ok, output) of one git command inside repo. Never raises: a missing git, a timeout or a bad exit is (False, why)."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_") or k in ("GIT_SSH", "GIT_SSH_COMMAND")}
    env["GIT_TERMINAL_PROMPT"] = "0"  # never wait for a password
    try:
        done = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, timeout=GIT_TIMEOUT_S, env=env)
    except (OSError, subprocess.SubprocessError) as e:
        return False, f"git {args[0]} could not run: {e}"
    if done.returncode != 0:
        return False, f"git {' '.join(args[:2])} failed: {(done.stderr or done.stdout).strip()[:200]}"
    return True, done.stdout


def ref_lines(lines):
    """Set of '<sha> <ref>' lines from git ls-remote output lines (the tab becomes one space)."""
    return {" ".join(str(line).split()) for line in lines if str(line).strip()}


def git_setup(state, inputs):
    """(repo, remote, problem): repoPath resolved like check_baselines does, and proof it is a git repo root."""
    repo = os.path.join(state, str(inputs.get("repoPath", "")))
    ok, top = git(repo, "rev-parse", "--show-toplevel")
    if not ok:
        return repo, "", top
    if os.path.normcase(os.path.realpath(top.strip())) != os.path.normcase(os.path.realpath(repo)):
        return repo, "", f"repoPath {repo} is not the root of a git repo (root is {top.strip()})"
    remote = str(inputs.get("remote") or "origin")
    if remote.startswith("-"):
        return repo, "", f"inputs.json remote {remote!r} starts with '-', so git would read it as an option"
    return repo, remote, ""


def check_remote_tags(state, inputs):
    start = inputs.get("remoteTagsAtStart")
    if not isinstance(start, list):
        return "inputs.json has no remoteTagsAtStart list"
    repo, remote, problem = git_setup(state, inputs)
    if problem:
        return problem
    ok, out = git(repo, "ls-remote", "--tags", remote)
    if not ok:
        return out
    changed = sorted(ref_lines(out.splitlines()) - ref_lines(start))
    return f"{len(changed)} tag(s) added or moved on {remote}, first: {changed[0]}" if changed else ""


def check_remote_branches(state, inputs):
    start = inputs.get("remoteHeadsAtStart")
    branch = inputs.get("branch")
    if not isinstance(start, list) or not branch:
        return "inputs.json needs a remoteHeadsAtStart list and a branch"
    repo, remote, problem = git_setup(state, inputs)
    if problem:
        return problem
    ok, out = git(repo, "ls-remote", "--heads", remote)
    if not ok:
        return out
    mine = f"refs/heads/{branch}"
    others = lambda lines: {l for l in lines if l.split(" ", 1)[-1] != mine}  # noqa: E731
    changed = sorted(others(ref_lines(out.splitlines())) ^ others(ref_lines(start)))
    return f"{len(changed)} branch line(s) other than {branch} differ on {remote}, first: {changed[0]}" if changed else ""


def check_final_commit(state, inputs):
    branch = inputs.get("branch")
    if not branch:
        return "inputs.json has no branch"
    repo, remote, problem = git_setup(state, inputs)
    if problem:
        return problem
    ok, out = git(repo, "ls-remote", "--heads", remote, f"refs/heads/{branch}")
    if not ok:
        return out
    if not out.strip():
        return f"branch {branch} is not on {remote}"
    ok, head = git(repo, "rev-parse", "HEAD")
    if not ok:
        return head
    remote_sha = out.split()[0]
    return "" if remote_sha == head.strip() else f"{remote}/{branch} is {remote_sha[:12]} but local HEAD is {head.strip()[:12]}"


def check_owner_report(state):
    path = os.path.join(state, "OWNER-REPORT.md")
    if not os.path.isfile(path):
        return "OWNER-REPORT.md not found"
    text = statefiles.read_text(path)
    if not re.search(r"^## Evidence[ \t]*$", text, re.M):
        return "OWNER-REPORT.md has no '## Evidence' heading"
    found = re.search(r"^## Merge danger[ \t]*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    if not found:
        return "OWNER-REPORT.md has no '## Merge danger' heading"
    if not re.search(r"\b(one|two)-way door\b", found.group(1), re.I):
        return "the Merge danger section does not say 'one-way door' or 'two-way door' for the run"
    return ""


def check_deliverable(state):
    """GOAL-BRIEF.md settles the deliverable at the door: a non-empty '## Deliverable' section."""
    path = os.path.join(state, "GOAL-BRIEF.md")
    if not os.path.isfile(path):
        return "GOAL-BRIEF.md not found"
    text = statefiles.read_text(path)
    found = re.search(r"^## Deliverable[ \t]*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    if not found:
        return "GOAL-BRIEF.md has no '## Deliverable' section (first-run test, manifest, folder contract)"
    return "" if found.group(1).strip() else "GOAL-BRIEF.md '## Deliverable' section is empty"


def check_audit_first(state):
    """Rule 17: a run that builds a new version audits the old one first, into audit-old.md."""
    path = os.path.join(state, "GOAL-BRIEF.md")
    if not os.path.isfile(path):
        return "GOAL-BRIEF.md not found"
    found = re.search(r"^## Old version[ \t]*$(.*?)(?=^## |\Z)", statefiles.read_text(path), re.M | re.S)
    if not found or not found.group(1).strip():
        return "GOAL-BRIEF.md has no '## Old version' section (the old version's path, or none)"
    if found.group(1).strip().lower().startswith("none"):
        return ""
    audit = os.path.join(state, "audit-old.md")
    if not os.path.isfile(audit) or not statefiles.read_text(audit).strip():
        return "GOAL-BRIEF.md names an old version but the state folder has no audit-old.md (audit it before building)"
    return ""


UI_FILE = re.compile(r"\.(html?|jsx|tsx|vue|svelte)\b", re.I)
REAL_BROWSER = re.compile(r"chromium|playwright|puppeteer", re.I)


def launches_browser(command, roots):
    """True when the check command (a string or a list of them), or a file it names (looked up under each
    root), drives a real browser."""
    if isinstance(command, list):  # str(list) wraps names in quotes and brackets, so no file name matched
        return any(launches_browser(str(c), roots) for c in command)
    if REAL_BROWSER.search(command):
        return True
    # ponytail: a text match, not proof a browser ran; it catches a stub harness, not a worker set on cheating
    bases = [os.path.realpath(r) for r in roots]
    for token in re.findall(r'"([^"]+)"|(\S+)', command):
        name = token[0] or token[1]
        for base in bases:
            path = os.path.realpath(os.path.join(base, name))
            inside = any(os.path.commonpath([path, b]) == b for b in bases if os.path.splitdrive(path)[0] == os.path.splitdrive(b)[0])
            if inside and os.path.isfile(path) and REAL_BROWSER.search(statefiles.read_text(path)):
                return True
    return False


PNG_HEAD = b"\x89PNG\r\n\x1a\n"
TASK_ID = re.compile(r"^[A-Za-z0-9_-][A-Za-z0-9_.-]*$")


def is_proof(path):
    """A real screenshot (PNG signature, then the IHDR header chunk) or a Playwright trace zip (a *.trace member)."""
    with open(path, "rb") as f:
        head = f.read(16)
    if head[:8] == PNG_HEAD and head[12:16] == b"IHDR":
        return True
    if zipfile.is_zipfile(path):
        try:
            with zipfile.ZipFile(path) as z:
                return any(n.endswith(".trace") for n in z.namelist())
        except zipfile.BadZipFile:
            return False
    return False


def has_proof(state, tid):
    """proof/<task id>/ holds at least one file is_proof accepts. An id that could leave proof/ has none."""
    # ponytail: no freshness test; a screenshot copied in from an old run passes. Compare with
    # unattendedSince if that ever happens (mtime is fine here: proof files are untracked run output).
    if not TASK_ID.match(tid):
        return False
    folder = os.path.join(state, "proof", tid)
    return os.path.isdir(folder) and any(
        os.path.isfile(p) and is_proof(p) for p in (os.path.join(folder, n) for n in os.listdir(folder)))


def task_outcomes(state):
    """task id -> outcome from run-state.json ("passed", "deferred", ...)."""
    run_state = statefiles.read_json_safe(os.path.join(state, "run-state.json"))
    out = {}
    for stage in (run_state.get("stages") or []) if isinstance(run_state, dict) else []:
        for tid, info in ((stage.get("tasks") or {}) if isinstance(stage, dict) else {}).items():
            if isinstance(info, dict):
                out[str(tid)] = info.get("outcome")
    return out


def ui_steps(state):
    """The run's UI tasks: stage spec "ui": true, or a page named in the task text, check or plan.md section."""
    steps = []
    for spec_path in sorted(glob.glob(os.path.join(state, "stages", "*.json"))):
        for step in (statefiles.read_json_safe(spec_path) or {}).get("steps") or []:
            steps.extend(step if isinstance(step, list) else [step])
    plan = {}  # task id -> its plan.md section; generate.py reads task text from "## Task <id>" headings
    plan_path = os.path.join(state, "plan.md")
    if os.path.isfile(plan_path):
        for m in re.finditer(r"^#+ .*?\bTask (\S+?)\b.*?$(.*?)(?=^#+ .*?\bTask \S|\Z)",
                             statefiles.read_text(plan_path), re.M | re.S):
            plan[m.group(1)] = m.group(2)
    ui = [s for s in steps if isinstance(s, dict) and s.get("kind") != "review"
          and (s.get("ui") or (s.get("ui") is not False and UI_FILE.search(f"{s.get('text', '')} {s.get('check', '')} {plan.get(str(s.get('id')), '')}")))]
    return ui


def check_fidelity(state):
    """Rule 17: a rebuild of an existing page is judged against the old page, not a score the run chose.
    The side-by-side page fidelity/index.html (old and new per state) must exist and hold no NOT-RUN state."""
    read = lambda *p: statefiles.read_text(os.path.join(state, *p)) if os.path.isfile(os.path.join(state, *p)) else ""
    found = re.search(r"^## Old version[ \t]*$(.*?)(?=^## |\Z)", read("GOAL-BRIEF.md"), re.M | re.S)
    old = found.group(1).strip().lower() if found else ""
    if not old or old.startswith("none") or not ui_steps(state):
        return ""
    page = read("fidelity", "index.html")
    if not page.strip():
        return "the run rebuilds an existing page but has no fidelity/index.html (old and new side by side, per state)"
    if re.search(r"NOT[- ]RUN", page, re.I):
        return "fidelity/index.html has a NOT-RUN state; the rebuild is not complete until every state is compared"
    # Each state's tag carries its measured count, so a page that compared nothing cannot pass.
    # Example: <div data-state="edit" data-differences="0">. The check does not set a pass line; the user signs off.
    states = re.findall(r"<[^>]*\bdata-state=[^>]*>", page)
    if not states:
        return 'fidelity/index.html lists no state (each state needs a tag like <div data-state="edit" data-differences="0">)'
    uncounted = [t for t in states if not re.search(r'\bdata-differences="\d+"', t)]
    if uncounted:
        return f"fidelity/index.html: {len(uncounted)} of {len(states)} states have no data-differences count"
    return ""


def check_not_run_claims(state):
    """Rule 2: when any check did not run (a NOT-RUN in the run log, or a task left not-run), no report may
    call the run complete or best. "not complete" and "incomplete" are honest and pass."""
    log = os.path.join(state, "log", "run-log.md")
    skipped = [r[1] for r in statefiles.table_rows(log) if len(r) > 2 and re.search(r"NOT[- ]RUN", " ".join(r), re.I)]
    skipped += [t for t, o in task_outcomes(state).items() if o == "not-run"]
    if not skipped:
        return ""
    reports = [os.path.join(state, "OWNER-REPORT.md")] + sorted(glob.glob(os.path.join(state, "reports", "*.md")))
    claims = [f"{os.path.basename(p)}: {m.group(0)!r}" for p in reports if os.path.isfile(p)
              for m in [re.search(r"(?<!not )\b(complete|best)\b", statefiles.read_text(p), re.I)] if m]
    if claims:
        return f"NOT-RUN check(s) for {', '.join(sorted(set(skipped)))}, yet a report claims it: {'; '.join(claims[:3])}"
    return ""


def check_ui_browser(state, inputs):
    """Rule 13: every UI task's check launches a real browser, and a run that ships a page has a UI task."""
    ui = ui_steps(state)
    repo = os.path.join(state, str(inputs.get("repoPath", "")))
    stub = [str(s.get("id", "?")) for s in ui if not launches_browser(s.get("check") or "", (repo, state))]
    if stub:
        return f"UI task(s) whose check never launches Chromium: {', '.join(stub)}"
    outcomes = task_outcomes(state)
    unproven = [str(s.get("id", "?")) for s in ui
                if outcomes.get(str(s.get("id"))) != "deferred" and not has_proof(state, str(s.get("id", "")))]
    if unproven:
        return (f"UI task(s) with no screenshot (.png) or Playwright trace (.zip) in proof/<task id>/: "
                f"{', '.join(unproven)}")
    if not ui and inputs.get("baseCommit"):
        base = str(inputs["baseCommit"])
        if base.startswith("-"):
            return f"inputs.json baseCommit {base!r} starts with '-', so git would read it as an option"
        ok, out = git(repo, "diff", "--name-only", "--diff-filter=d", "--end-of-options", base, "HEAD")  # a deleted page ships nothing
        if not ok:
            return out
        pages = [f for f in out.splitlines() if UI_FILE.search(f)]
        if pages:
            return f"the run changed {pages[0]} but no task is a UI task with a real-browser check"
    return ""


def run(state, transcript, only=None):
    results = []

    def check(name, problem):
        results.append(f"FAIL {name}: {problem}" if problem else f"PASS {name}")

    try:
        missing = [f for f in REQUIRED_FILES if not os.path.isfile(os.path.join(state, f))]
        check("required-files", f"missing: {', '.join(missing)}" if missing else "")
        inputs = statefiles.read_json_safe(os.path.join(state, "inputs.json"))
        check("inputs", check_inputs(inputs))
        inputs = inputs if isinstance(inputs, dict) else {}
        check("log-times", check_log_times(state))
        check("report-plain", check_report_plain(state, inputs))
        check("table-rows", check_table_rows(state))
        check("table-fresh", check_table_fresh(state, inputs))
        check("reports-saved", check_reports_saved(state))
        check("side-effects", check_side_effects(state, inputs))
        check("baselines", check_baselines(state, inputs))
        check("verdict", check_verdict(state))
        check("no-questions", check_no_questions(inputs, transcript))
        check("remote-tags", check_remote_tags(state, inputs))
        check("remote-branches", check_remote_branches(state, inputs))
        check("final-commit", check_final_commit(state, inputs))
        check("owner-report", check_owner_report(state))
        check("owner-feedback", check_owner_feedback(state, inputs, transcript))
        check("owner-score", check_owner_score(state))
        check("deliverable", check_deliverable(state))
        check("audit-first", check_audit_first(state))
        check("ui-browser", check_ui_browser(state, inputs))
        check("fidelity", check_fidelity(state))
        check("not-run-claims", check_not_run_claims(state))
    except Exception as e:  # a crashed check is a named FAIL, never a stale PASS left in run-check.txt
        check("crash", f"{type(e).__name__}: {e}")

    if only:  # a stage check of a few named checks: print them, keep run-check.txt for the full run
        results = [r for r in results if r.split(":")[0].split(" ", 1)[1] in set(only) | {"crash"}]
    failed = sum(r.startswith("FAIL") for r in results)
    results.append(f"RUN CHECK FAIL ({failed})" if failed else "RUN CHECK PASS")
    print("\n".join(results))
    if only:
        return 1 if failed else 0
    # The latest result stays in the state folder: the scorecard reads its safety rows from here.
    os.makedirs(os.path.join(state, "log"), exist_ok=True)
    with open(os.path.join(state, "log", "run-check.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(results) + "\n")
    return 1 if failed else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--state-dir", required=True, help="state folder. Example: docs/proj-123/autopilot")
    ap.add_argument("--transcript", help="coordinator transcript .jsonl (required, else no-questions fails). Example: ~/.claude/projects/<proj>/<session>.jsonl")
    ap.add_argument("--only", help="comma list of checks to run, for a stage check before FINAL. Example: owner-report")
    a = ap.parse_args()
    raise SystemExit(run(a.state_dir, a.transcript, a.only.split(",") if a.only else None))
