"""Check a run's state folder against the rules the owner cannot see from their phone. The final stage
must print RUN CHECK PASS before the run may call itself done; the tick may run it any time.
It fails closed: a missing file or a row it cannot read is a named FAIL, never a silent pass.

  python check_run.py --state-dir docs/proj-123/autopilot --transcript <session>.jsonl

Prints one line per check, "PASS <name>" or "FAIL <name>: <why>". Exit 1 on any FAIL.

Checks and the files they read (all under --state-dir unless noted):
  required-files  inputs.json, STATUS.md, tasks.csv, PROGRESS.md, log/run-log.md, log/side-effects.md,
                  baseline-hashes.txt (may be empty), run-state.json, OWNER-REPORT.md all exist
  inputs          inputs.json has caps (kind -> whole number) and unattendedSince (ISO time; no zone = UTC)
  log-times       every log/run-log.md row starts with a real-clock time "Day MM-DD HH:MM"
  report-plain    reports/*.md hold no ids, hashes or run codes (the owner reads them on a phone)
  table-rows      every task id in tasks.csv still has a row in PROGRESS.md
  side-effects    log/side-effects.md totals per kind stay within inputs.json "caps"; every row is
                  "| Day MM-DD HH:MM | kind | whole number | note |" and its kind has a cap
  baselines       every line of baseline-hashes.txt ("<sha256>  <repo-relative path>") is well formed and
                  its file is unchanged; repo root = inputs.json "repoPath"
  verdict         OWNER-REPORT.md contains run-state.json's verdict string exactly; the verdict is
                  "PASS (P of T tasks; N deferred, M by agents ...)" or "STOPPED (reason; P of T tasks passed;
                  N deferred, M by agents ...)", and its counts equal the outcomes in run-state.json
  no-questions    --transcript is required: no AskUserQuestion call after inputs.json "unattendedSince"
  remote-tags     git ls-remote --tags <remote> shows no tag added or moved since inputs.json remoteTagsAtStart
  remote-branches git ls-remote --heads <remote> differs from remoteHeadsAtStart only on inputs.json "branch"
  final-commit    the remote head of inputs.json "branch" equals the local HEAD of repoPath
  owner-report    OWNER-REPORT.md has the headings "## Evidence" and "## Merge danger", and the merge danger
                  section says "one-way door" or "two-way door" for the run as a whole
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

import statefiles

DAY_TIME = re.compile(r"^(Mon|Tue|Wed|Thu|Fri|Sat|Sun) \d\d-\d\d \d\d:\d\d$")
# Codes a manager would not understand: task/decision ids (T8, D27), stage codes (W4),
# git hashes, workflow run ids. Times like 08:15 and units like 5h do not match.
IDS = re.compile(r"\b[A-Z]{1,3}\d+[a-z]?\b|\b[0-9a-f]{7,40}\b|\bwf_[0-9a-f-]+")
SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")
DEFERRED_COUNTS = re.compile(r"(\d+) deferred, (\d+) by agents")
PASS_VERDICT = re.compile(r"^PASS \((\d+) of (\d+) tasks;")
STOPPED_VERDICT = re.compile(r"^STOPPED \([^;]*; (\d+) of (\d+) tasks passed;")
REQUIRED_FILES = ["inputs.json", "STATUS.md", "tasks.csv", "PROGRESS.md", os.path.join("log", "run-log.md"),
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


def check_report_plain(state):
    hits = []
    for path in sorted(glob.glob(os.path.join(state, "reports", "*.md"))):
        for m in IDS.finditer(statefiles.read_text(path)):
            hits.append(f"{os.path.basename(path)}: {m.group(0)}")
    return f"{len(hits)} codes in owner reports, first: {hits[0]}" if hits else ""


def check_table_rows(state):
    tasks_path = os.path.join(state, "tasks.csv")
    if not os.path.exists(tasks_path):
        return "tasks.csv not found"
    with open(tasks_path, newline="", encoding="utf-8-sig") as f:
        ids = [(r.get("id") or "").strip() for r in csv.DictReader(f)]
    shown = {r[2] for r in statefiles.table_rows(os.path.join(state, "PROGRESS.md")) if len(r) > 2}
    gone = [i for i in ids if i and i not in shown]
    return f"tasks missing from PROGRESS.md: {', '.join(gone)}" if gone else ""


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
    changed, malformed = [], []
    for line in statefiles.read_text(hashes).splitlines():
        if not line.strip():
            continue
        parts = line.strip().split(None, 1)
        if len(parts) != 2 or not SHA256.match(parts[0]):
            malformed.append(line.strip()[:60])
            continue
        path = os.path.join(root, parts[1])
        actual = hashlib.sha256(open(path, "rb").read()).hexdigest() if os.path.isfile(path) else "missing"
        if actual != parts[0].lower():
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
        return "verdict must start with 'PASS (' or 'STOPPED (' and carry 'P of T tasks'"
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


def run(state, transcript):
    results = []

    def check(name, problem):
        results.append(f"FAIL {name}: {problem}" if problem else f"PASS {name}")

    missing = [f for f in REQUIRED_FILES if not os.path.isfile(os.path.join(state, f))]
    check("required-files", f"missing: {', '.join(missing)}" if missing else "")
    inputs = statefiles.read_json_safe(os.path.join(state, "inputs.json"))
    check("inputs", check_inputs(inputs))
    inputs = inputs if isinstance(inputs, dict) else {}
    check("log-times", check_log_times(state))
    check("report-plain", check_report_plain(state))
    check("table-rows", check_table_rows(state))
    check("side-effects", check_side_effects(state, inputs))
    check("baselines", check_baselines(state, inputs))
    check("verdict", check_verdict(state))
    check("no-questions", check_no_questions(inputs, transcript))
    check("remote-tags", check_remote_tags(state, inputs))
    check("remote-branches", check_remote_branches(state, inputs))
    check("final-commit", check_final_commit(state, inputs))
    check("owner-report", check_owner_report(state))

    print("\n".join(results))
    failed = sum(r.startswith("FAIL") for r in results)
    print(f"RUN CHECK FAIL ({failed})" if failed else "RUN CHECK PASS")
    return 1 if failed else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--state-dir", required=True, help="state folder. Example: docs/proj-123/autopilot")
    ap.add_argument("--transcript", help="coordinator transcript .jsonl (required, else no-questions fails). Example: ~/.claude/projects/<proj>/<session>.jsonl")
    a = ap.parse_args()
    raise SystemExit(run(a.state_dir, a.transcript))
