"""Self-check for scripts/run_state.py. Run: python evals/test_run_state.py   Prints RUN STATE TEST PASS.
Uses fake journals in a temp folder, passed through --journals, and a fixed clock (--now)."""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
RS = os.path.join(HERE, "..", "scripts", "run_state.py")
NOW = "2026-10-17T10:00:00Z"
RESET = "2026-10-17T12:00:00Z"
TMP = tempfile.mkdtemp()
SEQ = [0]


def run(state, *args):
    r = subprocess.run([sys.executable, RS, *args, "--state-dir", state], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def new_state(stages="s1,s2", **inputs):
    SEQ[0] += 1
    state = os.path.join(TMP, f"st{SEQ[0]}")
    os.makedirs(os.path.join(state, "stages"))
    os.makedirs(os.path.join(state, "wf"))
    base = {"weeklyCap": 85, "disks": TMP, "minGB": 0, "sessions": []}
    json.dump(dict(base, **inputs), open(os.path.join(state, "inputs.json"), "w"))
    run(state, "init", "--stages", stages)
    return state


def spec(state, name, ids):
    json.dump({"steps": [{"id": i} for i in ids]}, open(os.path.join(state, "stages", name + ".json"), "w"))


def nxt(state, five=10, week=20, ctx=10, now=NOW, reset=RESET):
    return run(state, "next", "--five", str(five), "--week", str(week), "--reset", reset, "--ctx", str(ctx),
               "--now", now, "--journals", os.path.join(state, "wf"), "--no-box")


def journal(state, run_id, status="completed", results=None, stopped_by=None, tokens=None):
    body = {"status": status}
    if tokens is not None:
        body["totalTokens"] = tokens
    if results is not None:
        body["result"] = {"results": results, "stoppedBy": stopped_by}
    path = os.path.join(state, "wf", run_id + ".json")
    json.dump(body, open(path, "w"))
    return path


def res(passed=False, deferred=False, by=None, not_run=False):
    return {"passed": passed, "deferred": deferred, "deferredBy": by, "notRun": not_run, "problems": []}


def launch_and_result(state, stage, run_id, results, stopped_by=None, status="completed"):
    run(state, "record", "launch", stage, run_id)
    p = journal(state, run_id, status, results, stopped_by)
    run(state, "record", "result", stage, "--journal", p)


def stage_info(state, name):
    return next(s for s in run(state, "status")["stages"] if s["name"] == name)


def main():
    try:
        # 1 closed -> CLOSE and the tick is deleted
        s = new_state()
        run(s, "record", "close", "owner-stop")
        r = nxt(s)
        assert (r["action"], r["reason"], r["deleteTick"]) == ("CLOSE", "owner-stop", True), r

        # 2 disk below minGB -> STOP disk
        s = new_state(minGB=1e9)
        r = nxt(s)
        assert (r["action"], r["reason"]) == ("STOP", "disk"), r

        # 3 paused -> WAIT, even at 95% (never a second PAUSE); once the pause time passes, PAUSE is possible
        s = new_state()
        run(s, "record", "pause", "2026-10-17T12:05:00Z")
        assert nxt(s)["action"] == "WAIT"
        assert nxt(s, five=95)["action"] == "WAIT"
        assert nxt(s, five=95, now="2026-10-17T12:10:00Z", reset="2026-10-17T17:00:00Z")["action"] == "PAUSE"
        assert json.load(open(os.path.join(s, "run-state.json")))["paused"]["resumeScheduled"] is True

        # 4 five >= 90 -> PAUSE until reset + 5 min; quota-log row has the exact format
        s = new_state()
        r = nxt(s, five=92)
        assert (r["action"], r["reason"]) == ("PAUSE", "2026-10-17T12:05:00Z"), r
        row = open(os.path.join(s, "log", "quota-log.md"), encoding="utf-8").read().splitlines()[-1]
        assert re.fullmatch(r"\| [A-Z][a-z]{2} \d\d-\d\d \d\d:\d\d \| 92% \| 20% \| 2026-10-17T12:00:00Z \| PAUSE \|", row), row
        local = datetime.fromisoformat(NOW.replace("Z", "+00:00")).astimezone().strftime("%a %m-%d %H:%M")
        assert row.startswith(f"| {local} |"), row
        #   forecast looks one tick (30 min) ahead: 40% then 80% an hour later -> 80 + 40 * 0.5 = 100 -> PAUSE below 90
        s = new_state()
        assert nxt(s, five=40, now="2026-10-17T09:00:00Z")["action"] == "LAUNCH"
        assert nxt(s, five=80)["action"] == "PAUSE"
        #   the reset being far away does not matter: 40 -> 70 in an hour reaches only 85 by the next tick -> no pause
        s = new_state()
        nxt(s, five=40, now="2026-10-17T09:00:00Z")
        assert nxt(s, five=70)["action"] != "PAUSE"
        s = new_state()
        nxt(s, five=40, now="2026-10-17T09:00:00Z")
        assert nxt(s, five=41)["action"] == "LAUNCH"  # slow burn: no pause
        #   two readings only 15 minutes apart are noise: 40 -> 80 in 15 min does not forecast a pause
        s = new_state()
        nxt(s, five=40, now="2026-10-17T09:45:00Z")
        assert nxt(s, five=80)["action"] != "PAUSE"
        #   L3: the resume time is rounded UP to the next whole minute
        s = new_state()
        r = nxt(s, five=95, reset="2026-10-17T12:00:30Z")
        assert r["reason"] == "2026-10-17T12:06:00Z", r

        # 5 weekly cap: wait for the running stage, else stop
        s = new_state()
        run(s, "record", "launch", "s1", "wf_a")
        r = nxt(s, week=90)
        assert (r["action"], r["stage"]) == ("WAIT", "s1"), r
        s = new_state()
        r = nxt(s, week=90)
        assert (r["action"], r["reason"]) == ("STOP", "weekly-cap"), r
        #   C2: a running stage whose journal is final is recorded (RESULT); the next tick then stops
        s = new_state(stages="s1,s2")
        spec(s, "s1", ["T1"])
        run(s, "record", "launch", "s1", "wf_a")
        p = journal(s, "wf_a", "completed", {"T1": res(passed=True)})
        r = nxt(s, week=90)
        assert (r["action"], r["stage"], r["items"]) == ("RESULT", "s1", [p]), r
        run(s, "record", "result", "s1", "--journal", p)
        r = nxt(s, week=90)
        assert (r["action"], r["reason"]) == ("STOP", "weekly-cap"), r

        # 6 ctx >= 70 -> HANDOFF once, the run continues
        s = new_state()
        assert nxt(s, ctx=80)["action"] == "HANDOFF"
        run(s, "record", "handoff")
        assert nxt(s, ctx=80)["action"] == "LAUNCH"
        #   M7: dropping under 70% re-arms the handoff, so the next crossing gets one more
        assert nxt(s, ctx=40)["action"] == "LAUNCH"
        assert nxt(s, ctx=80)["action"] == "HANDOFF"

        # 7 running stage: no journal / running journal -> WAIT; final status -> RESULT
        s = new_state()
        run(s, "record", "launch", "s1", "wf_a")
        assert nxt(s)["action"] == "WAIT"
        journal(s, "wf_a", "running")
        assert nxt(s)["action"] == "WAIT"
        p = journal(s, "wf_a", "completed", {"T1": res(passed=True)})
        r = nxt(s)
        assert (r["action"], r["stage"], r["runId"], r["items"]) == ("RESULT", "s1", "wf_a", [p]), r

        # 8 interrupted (journal not completed) -> RESUME with the same runId; WAIT when 5h is high
        s = new_state()
        launch_and_result(s, "s1", "wf_a", None, status="killed")
        assert stage_info(s, "s1")["status"] == "interrupted"
        r = nxt(s)
        assert (r["action"], r["runId"]) == ("RESUME", "wf_a"), r
        assert nxt(s, five=70)["action"] == "WAIT"

        #   C1: resumed <stage> puts the stage back to running and clears the pause; the tick then waits
        #   (journal not final) or reports the result (final)
        s = new_state()
        run(s, "record", "launch", "s1", "wf_a")
        run(s, "record", "pause", "2026-10-17T12:05:00Z")
        assert stage_info(s, "s1")["status"] == "interrupted"  # H1: a pause interrupts the running stage
        run(s, "record", "resumed", "s1")
        assert stage_info(s, "s1")["status"] == "running" and run(s, "status")["paused"]["until"] is None
        journal(s, "wf_a", "running")
        assert nxt(s)["action"] == "WAIT"
        p = journal(s, "wf_a", "completed", {"T1": res(passed=True)})
        assert nxt(s)["action"] == "RESULT"
        #   pauses are not faults: three pause/resume rounds never fail the stage
        s = new_state()
        run(s, "record", "launch", "s1", "wf_a")
        for _ in range(3):
            run(s, "record", "pause", "2026-10-17T12:05:00Z")
            run(s, "record", "resumed", "s1")
        run(s, "record", "pause", "2026-10-17T12:05:00Z")
        assert stage_info(s, "s1")["status"] == "interrupted" and stage_info(s, "s1")["resumes"] == 0
        #   C1: 2 crash-resumes in a row with no new outcome -> failed -> RETRY of the unresolved tasks
        s = new_state()
        spec(s, "s1", ["T1", "T2"])
        launch_and_result(s, "s1", "wf_a", None, status="killed")
        run(s, "record", "resumed", "s1")
        run(s, "record", "interrupted", "s1")  # H1: the coordinator reports a dead workflow
        assert (stage_info(s, "s1")["status"], stage_info(s, "s1")["resumes"]) == ("interrupted", 1)
        run(s, "record", "resumed", "s1")
        run(s, "record", "interrupted", "s1")
        assert stage_info(s, "s1")["status"] == "failed"
        r = nxt(s)
        assert (r["action"], r["items"]) == ("RETRY", ["T1", "T2"]), r
        run(s, "record", "launch", "s1", "wf_b")
        assert stage_info(s, "s1")["resumes"] == 0
        #   a new outcome ends the streak: one crash-resume, then a result, then a crash is only interrupted
        s = new_state()
        launch_and_result(s, "s1", "wf_a", None, status="killed")
        run(s, "record", "resumed", "s1")
        run(s, "record", "interrupted", "s1")
        run(s, "record", "resumed", "s1")
        p = journal(s, "wf_a", "completed", {"T1": res()})
        run(s, "record", "result", "s1", "--journal", p)
        assert stage_info(s, "s1")["resumes"] == 0
        run(s, "record", "resumed", "s1")
        run(s, "record", "interrupted", "s1")
        assert stage_info(s, "s1")["status"] == "interrupted"

        # 9 failed -> RETRY lists only failed / not-run tasks; two attempts with no new pass -> STOP no-progress
        s = new_state()
        spec(s, "s1", ["T1", "T2", "T3"])
        launch_and_result(s, "s1", "wf_a", {"T1": res(passed=True), "T2": res(), "T3": res(not_run=True)})
        r = nxt(s)
        assert (r["action"], r["items"]) == ("RETRY", ["T2", "T3"]), r
        assert nxt(s, five=70)["action"] == "WAIT"
        launch_and_result(s, "s1", "wf_b", {"T2": res()})
        assert nxt(s)["action"] == "RETRY"
        launch_and_result(s, "s1", "wf_c", {"T2": res()})
        r = nxt(s)
        assert (r["action"], r["reason"]) == ("STOP", "no-progress"), r

        # 10 stopped by the critic gate -> STOP critic-stop
        s = new_state()
        launch_and_result(s, "s1", "wf_a", {"T1": res()}, stopped_by="critic-gate")
        r = nxt(s)
        assert (r["action"], r["reason"]) == ("STOP", "critic-stop"), r
        # override clears the stop only after a log/decisions.md "override:" row names the stage (rule 14)
        ov = subprocess.run([sys.executable, RS, "record", "override", "s1", "--state-dir", s], capture_output=True, text=True)
        assert ov.returncode != 0 and "override:" in ov.stderr, ov.stdout + ov.stderr
        os.makedirs(os.path.join(s, "log"), exist_ok=True)
        with open(os.path.join(s, "log", "decisions.md"), "w", encoding="utf-8") as f:
            f.write("| Sat 11-14 01:00 | override: s1 stop rule, rhea + ms-mario voted retry | a, b | new root cause | low |\n")
        run(s, "record", "override", "s1")
        r = nxt(s)
        assert (r["action"], r["stage"]) == ("RETRY", "s1"), r

        # 11 first pending stage -> LAUNCH; WAIT when 5h >= 60
        s = new_state()
        r = nxt(s)
        assert (r["action"], r["stage"]) == ("LAUNCH", "s1"), r
        assert nxt(s, five=65)["action"] == "WAIT"
        #   measured launch gate: s1 moved the 5h meter 20 points for 1M tokens, so s2 (1M estimated) may
        #   launch at 65 (65 + 20 < 90); at 75 it waits. Without a measurement the flat 60 holds (above).
        s = new_state()
        json.dump({"steps": [{"id": "T2"}], "estimateTokens": 1000000}, open(os.path.join(s, "stages", "s2.json"), "w"))
        assert nxt(s, five=10)["action"] == "LAUNCH"
        run(s, "record", "launch", "s1", "wf_g1")
        run(s, "record", "result", "s1", "--journal", journal(s, "wf_g1", "completed", {"T1": res(passed=True)}, tokens=1000000))
        assert nxt(s, five=30)["action"] == "LAUNCH"
        assert json.load(open(os.path.join(s, "run-state.json")))["fivePerMTok"] == 20.0
        r = nxt(s, five=65)
        assert (r["action"], r["stage"]) == ("LAUNCH", "s2"), r
        assert nxt(s, five=75)["action"] == "WAIT"
        #   meter values come from the usage file; typed-in numbers are refused outside tests (--now)
        s = new_state()
        usage = os.path.join(s, "usage.json")
        json.dump({"writtenAt": NOW, "ctxPct": 12, "claude": [
            {"window": "5h", "percentUsed": 35, "resetsAt": "2026-10-17T12:00:00.000Z"},
            {"window": "7d", "percentUsed": 20, "resetsAt": "2026-10-20T12:00:00.000Z"}]}, open(usage, "w"))
        r = run(s, "next", "--usage", usage, "--now", NOW, "--journals", os.path.join(s, "wf"), "--no-box")
        assert r["action"] == "LAUNCH", r
        assert "| 35% | 20% | 2026-10-17T12:00:00Z |" in open(os.path.join(s, "log", "quota-log.md")).read()
        typed = subprocess.run([sys.executable, RS, "next", "--state-dir", s, "--five", "35", "--week", "20",
                                "--reset", RESET, "--ctx", "10", "--no-box"], capture_output=True, text=True)
        assert typed.returncode != 0 and "--usage" in typed.stdout + typed.stderr, typed

        # H4: STOP names the running stage so the tick can TaskStop it first
        s = new_state(minGB=1e9)
        run(s, "record", "launch", "s1", "wf_a")
        r = nxt(s)
        assert (r["action"], r["stage"], r["runId"]) == ("STOP", "s1", "wf_a"), r

        # a result entry's own "reason" (for example "blocked by T1") is stored as the task reason
        s = new_state(stages="s1")
        launch_and_result(s, "s1", "wf_a", {"T1": dict(res(deferred=True, by="agent"), reason="blocked by T0", problems=["x"])})
        assert json.load(open(os.path.join(s, "run-state.json")))["stages"][0]["tasks"]["T1"]["reason"] == "blocked by T0"

        # defer does not stop progress: a stage whose only task is deferred is done, noProgress stays 0
        s = new_state(stages="s1")
        launch_and_result(s, "s1", "wf_a", {"T1": res(deferred=True, by="agent")})
        assert stage_info(s, "s1")["status"] == "done"
        assert run(s, "status")["noProgress"] == 0

        # 12 every stage done, verdict null -> FINAL; owner defer resolves a failed stage; verdict counts
        s = new_state()
        launch_and_result(s, "s1", "wf_a", {"T1": res(passed=True), "T2": res(deferred=True, by="agent")})
        launch_and_result(s, "s2", "wf_b", {"T3": res()})
        assert stage_info(s, "s2")["status"] == "failed"
        run(s, "record", "defer", "T3", "owner", "needs", "an", "account")
        assert stage_info(s, "s2")["status"] == "done"
        assert nxt(s)["action"] == "FINAL"
        run(s, "record", "final", "--done-line", "ALL CHECKS PASS")

        # 13 verdict set -> CHECK, then CLOSE done after checked pass, delete the tick
        v = run(s, "status")["verdict"]
        assert v == "PASS (3 of 3 tasks; 2 deferred, 1 by agents)", v
        r = nxt(s)
        assert r["action"] == "CHECK", r
        run(s, "record", "checked", "pass")
        r = nxt(s)
        assert (r["action"], r["reason"], r["deleteTick"]) == ("CLOSE", "done", True), r
        #   H3: a failing check is written into the verdict and the run still closes (never loops)
        s = new_state(stages="s1")
        launch_and_result(s, "s1", "wf_a", {"T1": res(passed=True)})
        run(s, "record", "final", "--done-line", "ALL CHECKS PASS")
        assert nxt(s)["action"] == "CHECK"
        run(s, "record", "checked", "fail", "baselines,verdict")
        v = run(s, "status")["verdict"]
        assert v == "PASS (1 of 1 tasks; 0 deferred, 0 by agents) - RUN CHECK FAIL (baselines,verdict)", v
        r = nxt(s)
        assert (r["action"], r["reason"], r["deleteTick"]) == ("CLOSE", "done-with-check-fail", True), r
        run(s, "record", "close", "done-with-check-fail")
        run(s, "record", "close", "awaiting-owner-score")
        #   the verdict follows the done command's last line, never the task count alone
        s = new_state(stages="s1")
        launch_and_result(s, "s1", "wf_a", {"T1": res(passed=True)})
        run(s, "record", "final", "--done-line", "ALL CHECKS FAIL; 2 of 9 failed")
        v = run(s, "status")["verdict"]
        assert v == "FAIL (done command: ALL CHECKS FAIL, 2 of 9 failed; 1 of 1 tasks; 0 deferred, 0 by agents)", v
        s = new_state(stages="s1")
        launch_and_result(s, "s1", "wf_a", {"T1": res(passed=True)})
        r = subprocess.run([sys.executable, RS, "record", "final", "--state-dir", s], capture_output=True, text=True)
        assert r.returncode != 0 and "--done-line" in r.stderr, r

        # M1: a resolved run finishes before the disk, quota and weekly checks
        s = new_state(stages="s1", minGB=1e9)
        launch_and_result(s, "s1", "wf_a", {"T1": res(passed=True)})
        assert nxt(s, five=95, week=99, ctx=99)["action"] == "FINAL"
        run(s, "record", "final", "--done-line", "ALL CHECKS PASS")
        assert nxt(s, five=95, week=99)["action"] == "CHECK"

        # M2: final is refused while a stage is not done; --stopped writes a STOPPED verdict (CLOSE gives the stop reason)
        s = new_state()
        spec(s, "s1", ["T1", "T2"])
        spec(s, "s2", ["T3"])
        launch_and_result(s, "s1", "wf_a", {"T1": res(passed=True), "T2": res(deferred=True, by="agent")})
        r = subprocess.run([sys.executable, RS, "record", "final", "--state-dir", s], capture_output=True, text=True)
        assert r.returncode != 0 and "every stage done" in r.stderr, r
        run(s, "record", "final", "--stopped", "weekly-cap")
        v = run(s, "status")["verdict"]
        assert v == "STOPPED (weekly-cap; 1 of 3 tasks passed; 1 deferred, 1 by agents)", v
        assert nxt(s)["action"] == "CHECK"
        run(s, "record", "checked", "pass")
        r = nxt(s)
        assert (r["action"], r["reason"]) == ("CLOSE", "weekly-cap"), r

        # M5: open HIGH / CRITICAL review findings are stored per stage and counted in the verdict
        s = new_state(stages="s1")
        run(s, "record", "launch", "s1", "wf_a")
        p = journal(s, "wf_a", "completed", {"T1": res(passed=True)})
        body = json.load(open(p))
        body["result"]["review"] = {"findings": [
            {"severity": "HIGH", "text": "a", "closed": False}, {"severity": "critical", "text": "b", "closed": False},
            {"severity": "HIGH", "text": "c", "closed": True}, {"severity": "LOW", "text": "d", "closed": False}]}
        json.dump(body, open(p, "w"))
        run(s, "record", "result", "s1", "--journal", p)
        run(s, "record", "final", "--done-line", "ALL CHECKS PASS")
        v = run(s, "status")["verdict"]
        assert v == "PASS (1 of 1 tasks; 0 deferred, 0 by agents; 2 open review findings)", v

        # A review step (a read-only agent inside a stage) returns findings: they are saved to reviews/<id>.md
        # and its open HIGH / CRITICAL count joins the verdict; a retry result without the step keeps the count.
        s = new_state(stages="s1")
        run(s, "record", "launch", "s1", "wf_a")
        judge = dict(res(passed=True), findings=[{"severity": "HIGH", "text": "reply order | wrong", "closed": False},
                                                 {"severity": "LOW", "text": "wording", "closed": False}])
        p = journal(s, "wf_a", "completed", {"J1": judge, "T1": res(passed=False)})
        run(s, "record", "result", "s1", "--journal", p)
        saved = open(os.path.join(s, "reviews", "J1.md"), encoding="utf-8").read()
        assert "| 1 | HIGH | reply order \\| wrong | open |" in saved and "| 2 | LOW | wording | open |" in saved, saved
        run(s, "record", "launch", "s1", "wf_b")
        run(s, "record", "result", "s1", "--journal", journal(s, "wf_b", "completed", {"T1": res(passed=True)}))
        run(s, "record", "final", "--done-line", "ALL CHECKS PASS")
        v = run(s, "status")["verdict"]
        assert v == "PASS (2 of 2 tasks; 0 deferred, 0 by agents; 1 open review findings)", v

        # stageCheck: a failing one adds the synthetic task "<stage>:check" (failed), so the stage fails and RETRY lists it
        def with_extra(path, **extra):
            body = json.load(open(path))
            body["result"].update(extra)
            json.dump(body, open(path, "w"))

        s = new_state(stages="s1")
        spec(s, "s1", ["T1"])
        run(s, "record", "launch", "s1", "wf_a")
        p = journal(s, "wf_a", "completed", {"T1": res(passed=True)})
        with_extra(p, stageCheck={"passed": False, "lastLine": "ALL CHECKS: FAIL"})
        run(s, "record", "result", "s1", "--journal", p)
        info = stage_info(s, "s1")
        assert info["status"] == "failed" and info["stageCheck"] == {"passed": False, "lastLine": "ALL CHECKS: FAIL"}, info
        task = json.load(open(os.path.join(s, "run-state.json")))["stages"][0]["tasks"]["s1:check"]
        assert task["outcome"] == "failed" and "ALL CHECKS: FAIL" in task["reason"], task
        r = nxt(s)
        assert (r["action"], r["items"]) == ("RETRY", ["s1:check"]), r
        #   the retry (a fix task plus the stage check again): a passing stage check resolves the synthetic task
        run(s, "record", "launch", "s1", "wf_b")
        p = journal(s, "wf_b", "completed", {"FIX1": res(passed=True)})
        with_extra(p, stageCheck={"passed": True, "lastLine": "ALL CHECKS: PASS"})
        run(s, "record", "result", "s1", "--journal", p)
        info = stage_info(s, "s1")
        assert info["status"] == "done" and info["stageCheck"]["passed"] is True, info
        assert json.load(open(os.path.join(s, "run-state.json")))["stages"][0]["tasks"]["s1:check"]["outcome"] == "passed"
        #   a passing stage check on the first attempt is recorded and adds no task
        s = new_state(stages="s1")
        run(s, "record", "launch", "s1", "wf_a")
        p = journal(s, "wf_a", "completed", {"T1": res(passed=True)})
        with_extra(p, stageCheck={"passed": True, "lastLine": "ALL CHECKS: PASS"})
        run(s, "record", "result", "s1", "--journal", p)
        assert stage_info(s, "s1")["status"] == "done" and stage_info(s, "s1")["tasks"] == 1
        assert stage_info(s, "s1")["stageCheck"]["lastLine"] == "ALL CHECKS: PASS"

        # final review: open HIGH / CRITICAL findings are counted per axis and the verdict never merges them
        s = new_state(stages="s1")
        run(s, "record", "launch", "s1", "wf_a")
        p = journal(s, "wf_a", "completed", {"T1": res(passed=True)})
        with_extra(p, review={"spec": {"findings": [{"severity": "HIGH", "text": "a", "closed": False},
                                                    {"severity": "CRITICAL", "text": "b", "closed": False},
                                                    {"severity": "HIGH", "text": "c", "closed": True}]},
                              "standards": {"findings": [{"severity": "HIGH", "text": "d", "closed": False},
                                                         {"severity": "LOW", "text": "e", "closed": False}]}})
        run(s, "record", "result", "s1", "--journal", p)
        assert stage_info(s, "s1")["openByAxis"] == {"spec": 2, "standards": 1}, stage_info(s, "s1")
        run(s, "record", "final", "--done-line", "ALL CHECKS PASS")
        v = run(s, "status")["verdict"]
        assert v == "PASS (1 of 1 tasks; 0 deferred, 0 by agents; spec: 2 open, standards: 1 open)", v
        #   one axis clean: it is still listed (with 0), not hidden or folded into the other
        s = new_state(stages="s1")
        run(s, "record", "launch", "s1", "wf_a")
        p = journal(s, "wf_a", "completed", {"T1": res(passed=True)})
        with_extra(p, review={"spec": {"findings": []}, "standards": {"findings": [{"severity": "HIGH", "text": "d", "closed": False}]}})
        run(s, "record", "result", "s1", "--journal", p)
        run(s, "record", "final", "--done-line", "ALL CHECKS PASS")
        v = run(s, "status")["verdict"]
        assert v.endswith("; spec: 0 open, standards: 1 open)"), v

        # report flag: true while the run log has rows not yet reported
        s = new_state()
        os.makedirs(os.path.join(s, "log"))
        open(os.path.join(s, "log", "run-log.md"), "w").write(
            "| When | Task | What | Evidence |\n|---|---|---|---|\n| Sat 10-17 01:00 | T1 | a | x |\n| Sat 10-17 01:05 | T2 | b | y |\n")
        assert nxt(s)["report"] is True
        run(s, "record", "reported", "2")
        assert nxt(s)["report"] is False
        # add-stage: a stage added after every stage is done launches before FINAL; a duplicate is refused
        s = new_state("s1")
        spec(s, "s1", ["T1"])
        launch_and_result(s, "s1", "wf_add1", {"T1": res(passed=True)})
        run(s, "record", "add-stage", "s0-harden", "s1")
        run(s, "record", "add-stage", "s2-fix", "s0-harden")
        assert [x["name"] for x in run(s, "status")["stages"]] == ["s1", "s0-harden", "s2-fix"]
        no_after = subprocess.run([sys.executable, RS, "record", "add-stage", "s3-x", "--state-dir", s], capture_output=True, text=True)
        assert no_after.returncode != 0 and "goes after" in no_after.stdout + no_after.stderr, no_after
        r = nxt(s)
        assert (r["action"], r["stage"]) == ("LAUNCH", "s0-harden"), r
        dup = subprocess.run([sys.executable, RS, "record", "add-stage", "s1", "--state-dir", s], capture_output=True, text=True)
        assert dup.returncode != 0
        # cost: stage estimates scale the open stages; one warning at 1.5x, the next only at +0.5
        s = new_state("s1,s2,s3")
        for n in ("s1", "s2", "s3"):
            json.dump({"steps": [{"id": n + "T"}], "estimateTokens": 1000}, open(os.path.join(s, "stages", n + ".json"), "w"))
        run(s, "record", "launch", "s1", "wf_c1")
        run(s, "record", "result", "s1", "--journal", journal(s, "wf_c1", "completed", {"s1T": res(passed=True)}, tokens=2000))
        c = nxt(s)["cost"]
        assert (c["spent"], c["projected"], c["estimate"], c["ratio"], c["warn"]) == (2000, 6000, 3000, 2.0, True), c
        assert nxt(s)["cost"]["warn"] is False  # warned once at 2.0; the next warning needs 2.5
        assert run(s, "status")["stages"][0]["name"] == "s1"
        # cost without stage estimates: GOAL-BRIEF.md midpoint; under 1.5x no warning
        s = new_state("s1,s2")
        spec(s, "s1", ["T1"])
        open(os.path.join(s, "GOAL-BRIEF.md"), "w").write("Cost estimate: 2K-4K\n")
        run(s, "record", "launch", "s1", "wf_c2")
        run(s, "record", "result", "s1", "--journal", journal(s, "wf_c2", "completed", {"T1": res(passed=True)}, tokens=1500))
        c = nxt(s)["cost"]
        assert (c["projected"], c["estimate"], c["ratio"], c["warn"]) == (3000, 3000, 1.0, False), c
        assert nxt(new_state())["cost"] is None  # nothing finished yet
        #   the accepted GOAL-BRIEF.md range is the yardstick even with stage estimates, and the re-estimate
        #   starts before any stage finishes (the sum of specs written so far once hid a 5.8x overrun)
        s = new_state("s1,s2,s3")
        for n in ("s1", "s2", "s3"):
            json.dump({"steps": [{"id": n + "T"}], "estimateTokens": 2000}, open(os.path.join(s, "stages", n + ".json"), "w"))
        open(os.path.join(s, "GOAL-BRIEF.md"), "w").write("Cost estimate: 2K-4K\n")
        c = nxt(s)["cost"]
        assert (c["projected"], c["estimate"], c["ratio"], c["warn"]) == (6000, 3000, 2.0, True), c
        # refresh: every next rebuilds the task table and TIMELINE.md, whatever the action
        s = new_state("s1")
        assert nxt(s)["refresh"].startswith("skipped"), "no tasks.csv yet"
        open(os.path.join(s, "tasks.csv"), "w").write("id,stage,what,estimate,added\nT1,s1,do it,10,\n")
        os.makedirs(os.path.join(s, "log"), exist_ok=True)
        open(os.path.join(s, "log", "decisions.md"), "w").write("| When | Decision | Options | Why | Cost |\n|---|---|---|---|---|\n| Sat 10-17 01:00 | go | a or b | cheap | 0 |\n")
        r = nxt(s)
        assert r["refresh"] == "ok", r["refresh"]
        assert "| T1 |" in open(os.path.join(s, "STATUS.md")).read()
        assert "decision: go" in open(os.path.join(s, "TIMELINE.md")).read()
        assert r["box"]["result"].startswith("skipped")
        # RESUME copies the journal into journals/ before the resumed run overwrites it
        s = new_state("s1")
        spec(s, "s1", ["T1"])
        run(s, "record", "launch", "s1", "wf_r1")
        journal(s, "wf_r1", "running", tokens=5)
        run(s, "record", "interrupted", "s1")
        r = nxt(s)
        assert r["action"] == "RESUME" and r["archived"] and os.path.exists(r["archived"]), r
        assert json.load(open(r["archived"]))["totalTokens"] == 5
        print("RUN STATE TEST PASS")
    finally:
        shutil.rmtree(TMP, ignore_errors=True)


if __name__ == "__main__":
    main()
