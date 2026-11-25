"""Run-state machine for /personal-big-project: decides the next coordinator action in code, so the
unattended tick follows the same rules every time. State lives in <state-dir>/run-state.json; nobody
edits it by hand. Every command prints ONE JSON object on stdout; exit 1 only for invalid input.

  python run_state.py init   --state-dir docs/proj-123/autopilot --stages s1-plan,s2-build
  python run_state.py next   --state-dir docs/proj-123/autopilot --usage ~/.claude/live-usage/<session id>.json
      [--now 2026-10-17T06:00:00Z] [--journals DIR ...] [--no-box]
      --usage is the meter source: the live-usage file (or quota.ps1 -Json output); a file older than 15 minutes
      is refreshed by running personal-quota's quota.ps1. Tests pass --five --week --reset --ctx with --now;
      typed-in meter values without --now are refused, because one tick once logged a meter nobody measured.
      -> {"action", "stage", "runId", "items", "reason", "report", "deleteTick", "cost", "refresh", "box"};
         also appends one row to log/quota-log.md. Every call, whatever the action, also rebuilds the
         STATUS.md task table (build_table.py) and TIMELINE.md (timeline.py) ("refresh": "ok" or the
         error), runs box_health.ps1 ("box": {result, new, hints}; --no-box skips it), and re-estimates
         the run after each finished stage ("cost": {spent, projected, estimate, ratio, warn}; warn true
         means phone the owner). A RESUME first copies the stage journal into journals/ ("archived"),
         because the resumed run overwrites it. --now fixes the clock (tests). --journals replaces the
         default journal folders found through inputs.json "sessions" (tests).
  python run_state.py record --state-dir D launch s1-plan wf_ab12cd34-001     (status running, attempt + 1)
  python run_state.py record --state-dir D result s1-plan --journal C:/.../wf_ab12cd34-001.json
  python run_state.py record --state-dir D pause 2026-10-17T08:15:00Z         (one resume is scheduled; a running stage becomes interrupted)
  python run_state.py record --state-dir D interrupted s1-plan                 (the workflow died or was TaskStopped)
  python run_state.py record --state-dir D resumed s1-plan                     (stage running again, pause cleared)
  python run_state.py record --state-dir D handoff
  python run_state.py record --state-dir D override s3-build                  (lift a critic-gate stop; needs a log/decisions.md "override:" row naming the stage)
  python run_state.py record --state-dir D add-stage s8-judge-fix s7-build   (new pending stage, right after the named one; the second name is required)
  python run_state.py record --state-dir D final --done-line "ALL CHECKS PASS" (refused unless every stage is done;
      the done command's last line decides PASS or FAIL, the task counts only follow it)
  python run_state.py record --state-dir D final --stopped weekly-cap          (STOPPED verdict for a run that cannot finish)
  python run_state.py record --state-dir D checked pass|fail [names]           (check_run.py outcome; fail is reported, never hidden)
  python run_state.py record --state-dir D reported 12                         (run-log rows already reported)
  python run_state.py record --state-dir D defer T4 owner "needs the owner's account"
  python run_state.py record --state-dir D close done|done-with-check-fail|awaiting-owner-score|no-progress|weekly-cap|disk|critic-stop|owner-stop
  python run_state.py status --state-dir D                                     (compact summary)

Inputs read from <state-dir>/inputs.json: weeklyCap, disks, minGB, sessions. Stage specs are
<state-dir>/stages/<name>.json. A journal's "result" has the shape the generated stage script returns
(see references/stage-workflow.template.js); a result entry with "notRun": true is a skipped task.
A result's "stageCheck" {passed, lastLine}: a failing one adds the failed task "<stage>:check" (RETRY items
include it; a later passing stageCheck resolves it). A result's "review" is {findings} or, for a final
review, {spec: {findings}, standards: {findings}}; open HIGH/CRITICAL are counted per axis and the verdict
lists them as "spec: N open, standards: M open", never merged. A result entry with "findings" is a review
step (kind "review"): its findings are saved to <state-dir>/reviews/<id>.md and its open HIGH/CRITICAL count
joins the verdict's open review findings.
"""
import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from statefiles import (cost_estimate, journal_dirs, number, read_json_safe, read_text,  # noqa: E402
                        table_rows, unique_agents)

# The personal-quota heavy-work band, applied to the 5h meter only: the weekly meter cannot reset
# over a weekend and weeklyCap already guards it. Once a stage has measured 5h points per million tokens,
# a stage with estimateTokens may launch higher, up to PAUSE_5H minus its own need (can_launch).
LAUNCH_5H = 60
USAGE_STALE_MIN = 15  # a live-usage file older than this is refreshed with quota.ps1
PAUSE_5H = 90  # at or above this the 5h window is nearly spent
RESUME_GAP_MIN = 5  # minutes after the 5h reset before the paused run is resumed
MIN_FORECAST_MIN = 20  # two readings closer than this give a burn rate that is mostly noise
NEXT_TICK_H = 0.5  # the forecast looks one tick ahead (ticks run about every 30 min), not to the reset
MAX_RESUMES = 2  # resumes in a row with no new outcome before the stage counts as failed
HANDOFF_CTX = 70  # coordinator context % at which a handoff is written
CLOSE_REASONS = ("done", "done-with-check-fail", "awaiting-owner-score", "no-progress", "weekly-cap", "disk", "critic-stop", "owner-stop")
STOP_REASONS = ("no-progress", "weekly-cap", "disk", "critic-stop", "owner-stop")  # final --stopped <reason>
DEFERRERS = ("agent", "owner")
AXES = ("spec", "standards")  # the two axes of a final review
COST_WARN = 1.5  # projected run total / estimate at which the tick asks the owner by phone
COST_STEP = 0.5  # after a warning, the next one comes only when the ratio has grown by this much
BOX_TIMEOUT_S = 90


def bad(msg):
    raise SystemExit(f"RUN STATE FAIL: {msg}")


def parse_iso(s):
    """ISO 8601 -> aware datetime; a naive time is read as UTC (same rule as inputs.json)."""
    try:
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        bad(f"not an ISO time: {s}. Example: 2026-10-17T08:10:00Z")
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def iso(d):
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def state_path(state_dir):
    return os.path.join(state_dir, "run-state.json")


def load(state_dir):
    st = read_json_safe(state_path(state_dir))
    if st is None:
        bad(f"{state_path(state_dir)} missing or unreadable; run init first")
    return st


def save(state_dir, st):
    tmp = state_path(state_dir) + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(st, f, indent=1)
    os.replace(tmp, state_path(state_dir))  # a reader never sees a half-written file


def stage_of(st, name):
    for s in st["stages"]:
        if s["name"] == name:
            return s
    bad(f"unknown stage '{name}'")


def resolved(s):
    return bool(s["tasks"]) and all(t["outcome"] in ("passed", "deferred") for t in s["tasks"].values())


def all_done(st):
    return bool(st["stages"]) and all(s["status"] == "done" for s in st["stages"])


def progress(s):
    """Tasks that moved forward. A deferral counts, so deferring never trips the no-progress stop."""
    return sum(1 for t in s["tasks"].values() if t["outcome"] in ("passed", "deferred"))


# ---- init / record ----

def new_stage(name):
    return {"name": name, "status": "pending", "runId": None, "attempt": 0, "tasks": {},
            "passedCountByAttempt": [0], "resumes": 0, "interruptedBy": None, "openFindings": 0,
            "openByAxis": None, "stageCheck": None}


def init(state_dir, stages):
    names = [n.strip() for n in stages.split(",") if n.strip()]
    if not names or len(names) != len(set(names)):
        bad("--stages needs a comma list of unique stage names. Example: s1-plan,s2-build")
    os.makedirs(state_dir, exist_ok=True)
    save(state_dir, {
        "stages": [new_stage(n) for n in names],
        "paused": {"until": None, "resumeScheduled": False}, "noProgress": 0,
        "lastReportedLogRows": 0, "handoffAt": None, "verdict": None, "checked": None, "stoppedReason": None, "closed": None})
    return {"ok": True, "stages": names}


def spec_task_ids(state_dir, name):
    spec = read_json_safe(os.path.join(state_dir, "stages", name + ".json")) or {}
    return [t["id"] for step in spec.get("steps", []) for t in (step if isinstance(step, list) else [step])]


def mark_interrupted(st, s, by="crash"):
    """A stage that lost its workflow. A pause is not a fault; a crash is, and MAX_RESUMES crashes in a
    row with no new outcome turn the stage into a failed one (RETRY with a fresh spec, or the no-progress stop)."""
    s["status"], s["interruptedBy"] = "interrupted", by
    if by == "crash" and s.get("resumes", 0) >= MAX_RESUMES:
        s["status"] = "failed"
        st["noProgress"] += 1


def open_high(findings):
    """Open HIGH or CRITICAL findings in a list of {severity, text, closed}."""
    return sum(1 for f in findings or [] if isinstance(f, dict) and not f.get("closed")
               and str(f.get("severity", "")).upper() in ("HIGH", "CRITICAL"))


def save_findings(state_dir, tid, findings):
    """reviews/<step id>.md: a review step's findings, so the coordinator and the owner can read them."""
    os.makedirs(os.path.join(state_dir, "reviews"), exist_ok=True)
    rows = ["| # | Severity | Finding | State |", "|---|---|---|---|"]  # check_answers.py keys answers by #
    for n, f in enumerate((f for f in findings if isinstance(f, dict)), 1):
        text = " ".join(str(f.get("text", "")).split()).replace("|", "\\|")
        rows.append(f"| {n} | {str(f.get('severity', '')).upper()} | {text} | {'closed' if f.get('closed') else 'open'} |")
    with open(os.path.join(state_dir, "reviews", f"{tid}.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(f"# Review step {tid}\n\n" + "\n".join(rows) + "\n")


def apply_result(state_dir, st, s, journal):
    j = read_json_safe(journal) if journal else None
    res = (j or {}).get("result")
    if not j or j.get("status") != "completed" or not isinstance(res, dict):
        mark_interrupted(st, s)
        return
    s["resumes"], s["interruptedBy"] = 0, None  # a new outcome ends the resume streak
    s["lastTokens"] = journal_tokens(j)  # this attempt alone; learn_rate reads it
    s["tokens"] = s.get("tokens", 0) + s["lastTokens"]  # every attempt adds up; cost_check reads it
    review = res.get("review") if isinstance(res.get("review"), dict) else {}
    axes = {a: open_high(review[a].get("findings")) for a in AXES if isinstance(review.get(a), dict)}
    if axes:  # a final review: the axes are counted apart and never merged
        s["openByAxis"] = axes
        s["openFindings"] = sum(axes.values())
    elif isinstance(review.get("findings"), list) and review["findings"]:
        s["openFindings"] = open_high(review["findings"])
    got = res.get("results") or {}
    for tid in spec_task_ids(state_dir, s["name"]):
        if tid not in got:  # the stage ended before this task ran
            s["tasks"].setdefault(tid, {"outcome": "not-run", "deferredBy": None, "reason": ""})
    for tid, r in got.items():
        if isinstance(r.get("findings"), list):  # a review step: keep its findings, count the open ones
            save_findings(state_dir, tid, r["findings"])
            s.setdefault("openByStep", {})[tid] = open_high(r["findings"])
        out = "passed" if r.get("passed") else "deferred" if r.get("deferred") else "not-run" if r.get("notRun") else "failed"
        s["tasks"][tid] = {"outcome": out, "deferredBy": r.get("deferredBy") if out == "deferred" else None,
                           "reason": (r.get("reason") or "; ".join(r.get("problems") or []))[:200]}
    check = res.get("stageCheck")
    if isinstance(check, dict):
        s["stageCheck"] = {"passed": bool(check.get("passed")), "lastLine": str(check.get("lastLine", ""))[:200]}
        synthetic = s["name"] + ":check"
        if not check.get("passed"):  # one failed task for the coordinator to write one fix task for
            s["tasks"][synthetic] = {"outcome": "failed", "deferredBy": None,
                                     "reason": "stage check failed: " + s["stageCheck"]["lastLine"]}
        elif synthetic in s["tasks"]:
            s["tasks"][synthetic] = {"outcome": "passed", "deferredBy": None, "reason": ""}
    s["status"] = "done" if resolved(s) else "stopped" if res.get("stoppedBy") == "critic-gate" else "failed"
    count = progress(s)
    grew = count > s["passedCountByAttempt"][-1]
    s["passedCountByAttempt"].append(count)
    st["noProgress"] = 0 if grew else st["noProgress"] + 1


def journal_tokens(j):
    """Tokens one stage journal spent: its totalTokens, else the sum over its agents."""
    total = number(j.get("totalTokens"))
    if total:
        return total
    agents, _ = unique_agents([j])
    return sum(number(a.get("tokens")) for a in agents)


def done_passed(line):
    """True when the done command's last line reports a pass: it ends in PASS and names no FAIL."""
    return bool(re.search(r"\bPASS\s*$", line)) and not re.search(r"\bFAIL", line)


def record(state_dir, event, args, journal, now, done_line=None):
    st = load(state_dir)
    if event == "launch":
        s = stage_of(st, args[0])
        s.update(status="running", runId=args[1], attempt=s["attempt"] + 1, resumes=0, interruptedBy=None)
    elif event == "result":
        apply_result(state_dir, st, stage_of(st, args[0]), journal)
    elif event == "pause":
        st["paused"] = {"until": iso(parse_iso(args[0])), "resumeScheduled": True}
        for s in st["stages"]:
            if s["status"] == "running":
                mark_interrupted(st, s, "pause")
    elif event == "interrupted":
        mark_interrupted(st, stage_of(st, args[0]))
    elif event == "resumed":
        st["paused"] = {"until": None, "resumeScheduled": False}
        if args:
            s = stage_of(st, args[0])
            if s["interruptedBy"] != "pause":
                s["resumes"] = s.get("resumes", 0) + 1
            s["status"] = "running"
    elif event == "add-stage":  # a stage the plan did not know at init: scorer hardening, the judge fix stage
        if st["verdict"]:
            bad("add-stage is refused after final")
        if not args or any(s["name"] == args[0] for s in st["stages"]):
            bad("add-stage needs a new stage name. Example: add-stage s8-judge-fix s7-build")
        if len(args) < 2:  # a stage once landed after the final with no way to move it
            bad("add-stage needs the stage it goes after. Example: add-stage s8-judge-fix s7-build")
        st["stages"].insert(st["stages"].index(stage_of(st, args[1])) + 1, new_stage(args[0]))
    elif event == "override":  # rule 14: a critic-gate stop is lifted only by a logged vote, never by a hand edit
        s = stage_of(st, args[0])
        if s["status"] != "stopped":
            bad(f"override needs a stage the critic gate stopped; {args[0]} is {s['status']}")
        votes = [r for r in table_rows(os.path.join(state_dir, "log", "decisions.md"))
                 if len(r) > 1 and r[1].startswith("override:") and re.search(rf"\b{re.escape(args[0])}\b", r[1])]
        if not votes:
            bad(f"override needs a log/decisions.md row whose decision starts 'override:' and names {args[0]}")
        s["status"] = "failed"  # the next tick retries its failed items like any failed stage
    elif event == "reported":
        st["lastReportedLogRows"] = int(args[0])
    elif event == "handoff":
        st["handoffAt"] = iso(now)
    elif event == "defer":
        if args[1] not in DEFERRERS:
            bad(f"defer deferredBy must be one of {DEFERRERS}")
        for s in st["stages"]:
            if args[0] in s["tasks"]:
                s["tasks"][args[0]] = {"outcome": "deferred", "deferredBy": args[1], "reason": " ".join(args[2:])}
                if s["status"] == "failed" and resolved(s):
                    s["status"] = "done"
                break
        else:
            bad(f"unknown task '{args[0]}'")
    elif event == "final":
        if st["verdict"]:
            bad("final was already recorded")
        stopped = args[1] if args[:1] == ["--stopped"] and len(args) > 1 else None
        if not stopped and not all_done(st):
            bad("final needs every stage done; use 'final --stopped <reason>' for a run that cannot finish")
        if stopped and stopped not in STOP_REASONS:
            bad(f"--stopped reason must be one of {STOP_REASONS}")
        if not stopped and not (done_line or "").strip():  # task counts once printed PASS while the done command failed
            bad('final needs --done-line "<the done command\'s last line>"; it decides PASS or FAIL')
        ids = {t for s in st["stages"] for t in s["tasks"]}
        for s in st["stages"]:
            ids.update(spec_task_ids(state_dir, s["name"]))
        tasks = [t for s in st["stages"] for t in s["tasks"].values()]
        deferred = [t for t in tasks if t["outcome"] == "deferred"]
        passed = sum(1 for t in tasks if t["outcome"] == "passed")
        by_agents = sum(1 for t in deferred if t["deferredBy"] == "agent")
        open_n = sum(s.get("openFindings", 0) for s in st["stages"] if not s.get("openByAxis"))
        open_n += sum(sum((s.get("openByStep") or {}).values()) for s in st["stages"])
        by_axis = [s["openByAxis"] for s in st["stages"] if s.get("openByAxis")]
        tail = f"; {open_n} open review findings" if open_n > 0 else ""
        if by_axis:  # never merged: each axis keeps its own count
            tail += "; " + ", ".join(f"{a}: {sum(x.get(a, 0) for x in by_axis)} open" for a in AXES)
        if stopped:
            st["stoppedReason"] = stopped
            st["verdict"] = (f"STOPPED ({stopped}; {passed} of {len(ids)} tasks passed; "
                             f"{len(deferred)} deferred, {by_agents} by agents{tail})")
        else:
            counts = f"{passed + len(deferred)} of {len(tasks)} tasks; {len(deferred)} deferred, {by_agents} by agents{tail}"
            line = " ".join(done_line.split()).replace(";", ",")
            st["verdict"] = f"PASS ({counts})" if done_passed(line) else f"FAIL (done command: {line}; {counts})"
    elif event == "checked":
        if not st["verdict"] or st["checked"]:
            bad("checked needs a verdict and is recorded once")
        if not args or args[0] not in ("pass", "fail"):
            bad("checked takes pass or fail. Example: checked fail baselines,verdict")
        st["checked"] = args[0]
        if args[0] == "fail":
            st["verdict"] += f" - RUN CHECK FAIL ({' '.join(args[1:]) or 'unnamed'})"
    elif event == "close":
        if args[0] not in CLOSE_REASONS:
            bad(f"close reason must be one of {CLOSE_REASONS}")
        st["closed"] = {"at": iso(now), "reason": args[0]}
    else:
        bad(f"unknown event '{event}'")
    save(state_dir, st)
    return {"ok": True, "event": event}


# ---- next ----

def free_gb(disk):
    d = disk.strip()
    return shutil.disk_usage(d + "\\" if re.fullmatch(r"[A-Za-z]:", d) else d).free / 2**30


def find_journal(dirs, run_id):
    for d in dirs:
        for p in glob.glob(os.path.join(d, "wf_*.json")):
            stem = os.path.basename(p)[:-5]
            if run_id and run_id in (stem, stem[3:]):
                return p
    return None


def last_quota_row(state_dir, now):
    """(time, five %) of the newest quota-log row, or None. The time cell has no year: take the latest past date."""
    rows = table_rows(os.path.join(state_dir, "log", "quota-log.md"))
    if not rows or len(rows[-1]) < 2:
        return None
    local = now.astimezone()
    try:
        five = int(rows[-1][1].rstrip("%"))
        for year in (local.year, local.year - 1):
            t = datetime.strptime(f"{year} {rows[-1][0]}", "%Y %a %m-%d %H:%M").astimezone()
            if t <= local:
                return t, five
    except ValueError:
        pass
    return None


def forecast_hits_100(prev, five, now):
    """True when the burn rate between the previous reading and now reaches 100% before the next tick."""
    if not prev:
        return False
    gap_h = (now - prev[0]).total_seconds() / 3600
    if gap_h * 60 < MIN_FORECAST_MIN:
        return False
    rate = (five - prev[1]) / gap_h
    return rate > 0 and five + rate * NEXT_TICK_H >= 100


def log_quota(state_dir, now, five, week, reset, action):
    path = os.path.join(state_dir, "log", "quota-log.md")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    new = not os.path.exists(path)
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        if new:
            f.write("| When | 5h | 7d | Reset | Action |\n|---|---|---|---|---|\n")
        f.write(f"| {now.astimezone().strftime('%a %m-%d %H:%M')} | {five:g}% | {week:g}% | {iso(reset)} | {action} |\n")


def pause_until(reset):
    """Reset + RESUME_GAP_MIN, rounded UP to the next whole minute so the resume is never early."""
    t = reset + timedelta(minutes=RESUME_GAP_MIN)
    return t.replace(second=0, microsecond=0) + timedelta(minutes=1) if t.second or t.microsecond else t


def decide(state_dir, st, inputs, five, week, reset, ctx, now, dirs, prev):
    stages = st["stages"]
    running = next((s for s in stages if s["status"] == "running"), None)

    def out(action, reason, stage=None, runId=None, items=(), delete=False):
        if action == "STOP" and not stage and running:  # the tick TaskStops it first
            stage, runId = running["name"], running["runId"]
        rows = len(table_rows(os.path.join(state_dir, "log", "run-log.md")))
        return {"action": action, "stage": stage, "runId": runId, "items": list(items), "reason": reason,
                "report": rows > st["lastReportedLogRows"], "deleteTick": delete}

    def running_result():
        """RESULT when the running stage's journal is final, else None."""
        jp = find_journal(dirs, running["runId"])
        j = read_json_safe(jp) if jp else None
        if j and j.get("status") not in (None, "running"):
            return out("RESULT", "journal has a final status", running["name"], running["runId"], [jp])
        return None

    if st["closed"]:
        return out("CLOSE", st["closed"]["reason"], delete=True)
    if st["verdict"] or all_done(st):  # a resolved run finishes before disk, quota or weekly checks can stop it
        if not st["verdict"]:
            return out("FINAL", "every stage is done")
        if not st["checked"]:
            return out("CHECK", "run check_run.py, then record checked pass|fail")
        if st["checked"] == "fail":
            return out("CLOSE", "done-with-check-fail", delete=True)
        return out("CLOSE", st["stoppedReason"] or "done", delete=True)
    for d in str(inputs["disks"]).split(","):
        if d.strip() and free_gb(d) < float(inputs["minGB"]):
            return out("STOP", "disk")
    if st["paused"]["until"] and parse_iso(st["paused"]["until"]) > now:
        return out("WAIT", f"paused until {st['paused']['until']}")
    if five >= PAUSE_5H or forecast_hits_100(prev, five, now):
        return out("PAUSE", iso(pause_until(reset)), running and running["name"], running and running["runId"])
    if week >= inputs["weeklyCap"]:
        if running:
            return running_result() or out("WAIT", "weekly cap reached; letting the running stage finish",
                                           running["name"], running["runId"])
        return out("STOP", "weekly-cap")
    if ctx >= HANDOFF_CTX and not st["handoffAt"]:
        return out("HANDOFF", f"coordinator context {ctx:g}%")
    if running:
        return running_result() or out("WAIT", "stage still running" if find_journal(dirs, running["runId"])
                                       else "journal not found yet", running["name"], running["runId"])
    def low(s):
        """Room in the 5h window to start stage s: under LAUNCH_5H always; higher when its own measured need fits
        under PAUSE_5H. A flat 60 once idled a run for hours with 17-25 points of headroom."""
        rate = number(st.get("fivePerMTok"))
        need = rate * stage_estimate(state_dir, s["name"]) / 1e6
        return five < max(LAUNCH_5H, PAUSE_5H - need) if rate and need else five < LAUNCH_5H

    for s in stages:
        if s["status"] == "interrupted":
            return out("RESUME", "stage was interrupted", s["name"], s["runId"]) if low(s) else out("WAIT", "5h meter high", s["name"])
    for s in stages:
        if s["status"] == "failed":
            if st["noProgress"] >= 2:
                return out("STOP", "no-progress", s["name"])
            ids = spec_task_ids(state_dir, s["name"]) or list(s["tasks"])
            todo = [t for t in ids if s["tasks"].get(t, {}).get("outcome") not in ("passed", "deferred")]
            todo += [t for t, i in s["tasks"].items() if t not in ids and i["outcome"] == "failed"]  # "<stage>:check"
            if low(s):
                return out("RETRY", "fresh spec of the failed tasks only", s["name"], items=todo)
            return out("WAIT", "5h meter high", s["name"])
    for s in stages:
        if s["status"] == "stopped":
            return out("STOP", "critic-stop", s["name"])
    for s in stages:
        if s["status"] == "pending":
            return out("LAUNCH", "next stage", s["name"]) if low(s) else out("WAIT", "5h meter high", s["name"])
    return out("WAIT", "no stage is pending, running or failed")  # unreachable unless run-state.json was edited by hand


def stage_estimate(state_dir, name):
    """estimateTokens of stages/<name>.json, or 0."""
    return number((read_json_safe(os.path.join(state_dir, "stages", name + ".json")) or {}).get("estimateTokens"))


def learn_rate(st, five, reset):
    """5h points per million tokens, measured from the last launched stage once its result is in, while the
    5h window has not reset since its launch. Stored in st["fivePerMTok"] for the launch gate."""
    lm = st.get("launchMeter")
    s = next((x for x in st["stages"] if lm and x["name"] == lm["stage"]), None)
    if not s or s["status"] in ("running", "pending") or s["attempt"] != lm["attempt"]:
        return
    st.pop("launchMeter")
    if lm["reset"] == iso(reset) and five > lm["five"] and number(s.get("lastTokens")):
        st["fivePerMTok"] = round((five - lm["five"]) / (number(s["lastTokens"]) / 1e6), 2)


def cost_check(state_dir, st):
    """Re-estimate the whole run on every tick and store it in st["cost"]. The yardstick is the owner's accepted
    GOAL-BRIEF.md "Cost estimate" midpoint, else the sum of the stage estimates: comparing with the sum of the
    specs written so far once hid a 5.8x overrun, because it grew with every stage the run added.
    Finished stages' actual / estimate ratio scales the open stages' estimates; an open stage with no estimate
    counts as the average finished stage. Starts once a stage has finished or has an estimate.
    warn is true once when the ratio first reaches COST_WARN, then again per COST_STEP above that."""
    stages = st["stages"]
    done = [s for s in stages if s["status"] == "done" and number(s.get("tokens"))]
    est = {s["name"]: stage_estimate(state_dir, s["name"]) for s in stages}
    still_open = [s for s in stages if s["status"] != "done"]
    if not done and not any(est[s["name"]] for s in still_open):
        return None
    spent = sum(number(s.get("tokens")) for s in stages)
    per_stage = sum(number(s["tokens"]) for s in done) / len(done) if done else 0
    known = [s for s in done if est[s["name"]]]
    scale = sum(number(s["tokens"]) for s in known) / sum(est[s["name"]] for s in known) if known else 1
    projected = spent + sum(est[s["name"]] * scale if est[s["name"]] else per_stage for s in still_open)
    brief_path = os.path.join(state_dir, "GOAL-BRIEF.md")
    brief = cost_estimate(read_text(brief_path)) if os.path.exists(brief_path) else None
    estimate = (brief[0] + brief[1]) / 2 if brief else sum(est.values())
    if not estimate:
        return None
    ratio = round(projected / estimate, 2) if estimate else 0
    warn = ratio >= max(COST_WARN, (st.get("costWarnedRatio") or 0) + COST_STEP)
    if warn:
        st["costWarnedRatio"] = ratio
    st["cost"] = {"spent": int(spent), "projected": int(projected), "estimate": int(estimate), "ratio": ratio}
    return dict(st["cost"], warn=warn)


def refresh(state_dir, dirs):
    """Rebuild the STATUS.md task table and TIMELINE.md on every tick. Both are scripts with no LLM, so
    this costs no tokens. A prompt step that only some ticks reached once froze the table for 9 hours."""
    if not os.path.exists(os.path.join(state_dir, "tasks.csv")):
        return "skipped: no tasks.csv yet"
    try:
        import build_table
        import timeline
        build_table.build(state_dir, dirs)
        timeline.build(state_dir)
        return "ok"
    except Exception as e:  # the tick must still act; the coordinator reads the error in the JSON
        return f"error: {type(e).__name__}: {e}"


def box_health(state_dir, inputs):
    """Run box_health.ps1, a read-only machine check, and return {result, new, hints}. new holds the
    WARN/FAIL lines whose name was not in the previous log/box-health.md row, so the tick phones only
    new problems; hints are commands the owner may run themselves (the run never runs them)."""
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "box_health.ps1")
    shell = shutil.which("pwsh") or shutil.which("powershell")
    if not shell or not os.path.exists(script):
        return {"result": "skipped: no PowerShell or no box_health.ps1", "new": [], "hints": []}
    cmd = [shell, "-NoProfile", "-File", script, "-StateDir", state_dir,
           "-Disks", str(inputs.get("disks") or "C:"), "-MinGB", str(inputs.get("minGB") or 1)]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=BOX_TIMEOUT_S,
                             encoding="utf-8", errors="replace").stdout or ""
    except (OSError, subprocess.SubprocessError) as e:
        return {"result": f"error: {e}", "new": [], "hints": []}
    lines = [l.strip() for l in out.splitlines() if l.strip()]
    detail = {l.split()[1]: l for l in lines if l.split()[0] in ("WARN", "FAIL") and len(l.split()) > 1}
    new = [detail.get(l.split()[1], l) for l in lines if l.startswith("NEW ") and len(l.split()) > 1]
    return {"result": next((l for l in reversed(lines) if l.startswith("BOX ")), "no BOX line"),
            "new": new, "hints": [l for l in lines if l.startswith("HINT ")]}


def archive_journal(state_dir, dirs, run_id, now):
    """Copy a stage journal into <state-dir>/journals/ before a resume reuses its run id and overwrites it,
    so the first attempt's agent times and tokens survive for the timeline and the retro."""
    path = find_journal(dirs, run_id)
    if not path:
        return None
    os.makedirs(os.path.join(state_dir, "journals"), exist_ok=True)
    dest = os.path.join(state_dir, "journals", f"{os.path.basename(path)[:-5]}-{now.strftime('%Y%m%dT%H%M%S')}.json")
    shutil.copyfile(path, dest)
    return dest


def next_action(state_dir, five, week, reset_s, ctx, now, journals, box=True):
    st = load(state_dir)
    inputs = read_json_safe(os.path.join(state_dir, "inputs.json"))
    if not inputs:
        bad("inputs.json missing or unreadable in --state-dir")
    reset = parse_iso(reset_s)
    prev = last_quota_row(state_dir, now)  # read before this call appends its own row
    if ctx < HANDOFF_CTX and st["handoffAt"]:  # every crossing of the threshold gets one handoff
        st["handoffAt"] = None
        save(state_dir, st)
    dirs = journals if journals is not None else journal_dirs(inputs)
    learn_rate(st, five, reset)
    res = decide(state_dir, st, inputs, five, week, reset, ctx, now, dirs, prev)
    log_quota(state_dir, now, five, week, reset, res["action"])
    if res["action"] == "RESUME":
        res["archived"] = archive_journal(state_dir, dirs, res["runId"], now)
    if res["action"] in ("LAUNCH", "RETRY", "RESUME"):  # learn_rate measures this stage once its result is in
        attempt = stage_of(st, res["stage"])["attempt"] + (res["action"] != "RESUME")
        st["launchMeter"] = {"stage": res["stage"], "five": five, "reset": iso(reset), "attempt": attempt}
    res["cost"] = cost_check(state_dir, st)
    save(state_dir, st)
    res["refresh"] = refresh(state_dir, dirs)
    res["box"] = box_health(state_dir, inputs) if box else {"result": "skipped: --no-box", "new": [], "hints": []}
    return res


def read_usage(path, now):
    """(five, week, reset, ctx) from a live-usage file ({writtenAt, ctxPct, claude: [...]}) or quota.ps1 -Json output
    (a list). A live-usage file older than USAGE_STALE_MIN is refreshed with personal-quota's quota.ps1; its
    ctxPct is still used, because quota.ps1 does not know the session's context."""
    doc = read_json_safe(os.path.expanduser(path))
    if doc is None:
        bad(f"--usage file missing or unreadable: {path}")
    entries = doc if isinstance(doc, list) else doc.get("claude") or []
    ctx = number(doc.get("ctxPct")) if isinstance(doc, dict) else 0
    written = doc.get("writtenAt") if isinstance(doc, dict) else None
    if written and (now - parse_iso(written)).total_seconds() > USAGE_STALE_MIN * 60:
        quota = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "personal-quota", "quota.ps1")
        shell = shutil.which("pwsh") or shutil.which("powershell")
        try:
            out = subprocess.run([shell, "-NoProfile", "-File", quota, "-Provider", "claude", "-Json"], capture_output=True,
                                 text=True, timeout=BOX_TIMEOUT_S, encoding="utf-8", errors="replace").stdout
            entries = json.loads(out)
        except (OSError, TypeError, subprocess.SubprocessError, ValueError) as e:
            bad(f"--usage file is older than {USAGE_STALE_MIN} min and quota.ps1 failed: {e}")
    win = {str(e.get("window")): e for e in (entries if isinstance(entries, list) else [entries]) if isinstance(e, dict)}
    if "5h" not in win or "7d" not in win:
        bad(f"--usage has no claude 5h and 7d entries: {path}")
    return number(win["5h"].get("percentUsed")), number(win["7d"].get("percentUsed")), str(win["5h"].get("resetsAt")), ctx


def status(state_dir):
    st = load(state_dir)

    def count(s, outcome):
        return sum(1 for t in s["tasks"].values() if t["outcome"] == outcome)

    return {"stages": [{"name": s["name"], "status": s["status"], "attempt": s["attempt"], "runId": s["runId"],
                        "passed": count(s, "passed"), "deferred": count(s, "deferred"), "tasks": len(s["tasks"]),
                        "resumes": s.get("resumes", 0), "openFindings": s.get("openFindings", 0), "openByAxis": s.get("openByAxis"),
                        "stageCheck": s.get("stageCheck")}
                       for s in st["stages"]],
            "paused": st["paused"], "noProgress": st["noProgress"], "verdict": st["verdict"], "checked": st["checked"], "closed": st["closed"]}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=["init", "next", "record", "status"])
    ap.add_argument("args", nargs="*", help="record: event and its values. Example: launch s1-plan wf_ab12cd34-001")
    ap.add_argument("--state-dir", required=True, help="Example: docs/proj-123/autopilot")
    ap.add_argument("--stages", help="init: comma list. Example: s1-plan,s2-build")
    ap.add_argument("--five", type=float, help="5h window used %%. Example: 35")
    ap.add_argument("--week", type=float, help="weekly window used %%. Example: 20")
    ap.add_argument("--reset", help="5h window reset, ISO. Example: 2026-10-17T08:10:00Z")
    ap.add_argument("--ctx", type=float, help="coordinator context used %%. Example: 40")
    ap.add_argument("--usage", help="next: live-usage or quota.ps1 -Json file. Example: ~/.claude/live-usage/<id>.json")
    ap.add_argument("--done-line", help='record final: the done command\'s last line. Example: "ALL CHECKS PASS"')
    ap.add_argument("--now", help="fixed clock, ISO (tests). Example: 2026-10-17T06:00:00Z")
    ap.add_argument("--stopped", help="record final: a run that cannot finish. Example: weekly-cap")
    ap.add_argument("--journal", help="record result: journal file. Example: C:/.../wf_ab12cd34-001.json")
    ap.add_argument("--journals", nargs="*", help="next: journal folders (tests). Example: D:/tmp/wf")
    ap.add_argument("--no-box", action="store_true", help="next: skip the box_health.ps1 machine check (tests)")
    a = ap.parse_args()
    now = parse_iso(a.now) if a.now else datetime.now(timezone.utc)
    if a.cmd == "init":
        if not a.stages:
            bad("init needs --stages")
        r = init(a.state_dir, a.stages)
    elif a.cmd == "next":
        if a.usage:
            five, week, reset, ctx = read_usage(a.usage, now)
            ctx = a.ctx if a.ctx is not None else ctx
        elif a.now and None not in (a.five, a.week, a.reset, a.ctx):
            five, week, reset, ctx = a.five, a.week, a.reset, a.ctx
        else:
            bad("next needs --usage <live-usage file>; --five --week --reset --ctx are for tests with --now")
        r = next_action(a.state_dir, five, week, reset, ctx, now, a.journals, box=not a.no_box)
    elif a.cmd == "record":
        if not a.args:
            bad("record needs an event")
        r = record(a.state_dir, a.args[0], a.args[1:] + (["--stopped", a.stopped] if a.stopped else []), a.journal, now,
                   a.done_line)
    else:
        r = status(a.state_dir)
    print(json.dumps(r))


if __name__ == "__main__":
    main()
