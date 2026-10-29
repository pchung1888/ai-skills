"""Self-check for scripts/generate.py. Run: python evals/test_generate.py   Prints GENERATE TEST PASS.
Needs node on PATH: it syntax-checks the generated workflow script and runs it against fake agents."""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
GEN = os.path.join(HERE, "..", "scripts", "generate.py")
SESSION = "sess-0001"
R = {"check": "python -m pytest tests/test_one.py -q", "estimateK": 20}  # every task needs its own check and size
INPUTS = {"goal": "PROJ-123 invoice fixes", "repoPath": "D:\\work\\my`repo", "branch": "topic/123-fixes",
          "stateDir": "docs/proj-123/autopilot", "weeklyCap": 85, "disks": "C:,D:", "minGB": 1,
          "exclusiveResources": "SQL Server", "effort": None, "workerModel": "sonnet",
          "domainCritic": "ping-personal:iris", "caps": {"mail": 300}, "sessions": [SESSION],
          "baseCommit": "4b8d`3b26", "remote": "origin", "remoteTagsAtStart": [], "remoteHeadsAtStart": []}
SPEC = {"name": "s3-build", "summary": "spikes, then parallel code",
        "steps": [{**R, "id": "T5", "agent": "ping-personal:vex", "phase": "Spikes"},
                  [{**R, "id": "T2", "agent": "ping-personal:bunny", "phase": "Code", "commits": True,
                    "resources": ["SQL Server"]},
                   {**R, "id": "T3", "agent": "ping-personal:vex", "phase": "Code", "model": "inherit",
                    "resources": ["IIS"], "needs": ["T5"]}]],
        "review": "T3"}
# Fake Workflow API: T1 never verifies; every gate seat call answers VOTES in order (a retry of a null
# seat consumes the next entry); LASTLINE is what a passing verifier prints last; reports what ran.
CK = json.dumps(R["check"])
STUBS = """
const calls = []; const prompts = {}; const types = {}; let seat = 0; const votes = (process.env.VOTES || '').split(',')
async function agent(prompt, o) {
  calls.push(o.label); prompts[o.label] = prompt; types[o.label] = o.agentType
  if (o.label === 'stage:check') return { passed: process.env.STAGE_PASS !== '0', lastLine: process.env.STAGE_LAST || 'x' }
  if (o.label === 'final:spec') return { findings: [{ severity: 'HIGH', text: 'spec gap', closed: false }] }
  if (o.label === 'final:standards') return { findings: [{ severity: 'LOW', text: 'style', closed: false }] }
  if (o.label.endsWith(':verify')) return { passed: !o.label.startsWith('T1'), lastLine: process.env.LASTLINE || 'x' }
  if (o.label.includes(':gate:')) { const v = votes[seat++]; if (v === 'null') return null; return { vote: v, instruction: 'i', howToReverse: 'r' } }
  if (o.label.endsWith(':review')) return { findings: [{ severity: 'LOW', text: 't', closed: true }] }
  return { task: o.label, passed: true, doneCheckOutput: '', summary: 's', problems: [] }
}
async function parallel(fs) { return Promise.all(fs.map(f => f())) }
function phase() {}
function log() {}
"""


def gen(state, what, *args, session=SESSION):
    env = dict(os.environ)
    env.pop("CLAUDE_CODE_SESSION_ID", None)
    if session:
        env["CLAUDE_CODE_SESSION_ID"] = session
    return subprocess.run([sys.executable, GEN, what, *args, "--state-dir", state], capture_output=True, text=True, env=env)


PLAN = "".join(f"## Task T{n} - something\n" for n in range(1, 6))


def refused(state, spec_path, spec, needle):
    json.dump(spec, open(spec_path, "w"))
    r = gen(state, "stage", "--spec", spec_path)
    assert r.returncode != 0 and needle in r.stderr, (needle, r.stderr)


def main():
    tmp = tempfile.mkdtemp()
    try:
        state = os.path.join(tmp, "autopilot")
        os.makedirs(os.path.join(state, "stages"))
        inputs_path = os.path.join(state, "inputs.json")
        json.dump(INPUTS, open(inputs_path, "w"))
        plan_path = os.path.join(state, "plan.md")
        open(plan_path, "w").write(PLAN)
        spec = os.path.join(state, "stages", "s3.json")
        json.dump(SPEC, open(spec, "w"))

        r = gen(state, "tick")
        assert r.returncode == 0, r.stderr
        tick = open(os.path.join(state, "tick-prompt.txt"), encoding="utf-8").read()
        assert "<" + "STATE_DIR>" not in tick and "live-usage/sess-0001.json" in tick
        assert 'scripts/run_state.py" next --state-dir "docs/proj-123/autopilot"' in tick
        assert "personal-quota/quota.ps1" in tick
        # Report shape: 30 minutes and plain by default; the user's interval sets the cron and reaches the reporter.
        assert "cron: 7,37 * * * *" in r.stdout and "30-minute tick" in tick and "Report shape: plain" in tick, r.stdout
        assert "workflows/<runId>.json" in tick, "RESULT names the exact result record"
        json.dump(dict(INPUTS, report={"everyMin": 15, "style": "copilot", "taskList": True, "ids": True}), open(inputs_path, "w"))
        r = gen(state, "tick")
        tick = open(os.path.join(state, "tick-prompt.txt"), encoding="utf-8").read()
        assert "cron: 7,22,37,52 * * * *" in r.stdout and "15-minute tick" in tick, r.stdout
        assert "Report shape: copilot, with the full task list, task ids allowed" in tick, tick
        for bad in ({"everyMin": 7}, {"style": "loud"}, "15"):
            json.dump(dict(INPUTS, report=bad), open(inputs_path, "w"))
            r = gen(state, "tick")
            assert r.returncode != 0 and "inputs.json report" in r.stderr, (bad, r.stderr)
        json.dump(INPUTS, open(inputs_path, "w"))

        r = gen(state, "stage", "--spec", spec)
        assert r.returncode == 0, r.stderr
        js = open(os.path.join(state, "stages", "s3-build.js"), encoding="utf-8").read()
        assert "name: \"proj-123-invoice-fixes-s3-build\"" in js
        assert "phases: [{ title: \"Spikes\" }, { title: \"Code\" }, { title: \"Review\" }]" in js
        assert "parallel([() => run(\"T2\", \"ping-personal:bunny\", \"Code\", WORKER_MODEL, [], true, \"\", \"\", " + CK + "), " \
               "() => run(\"T3\", \"ping-personal:vex\", \"Code\", undefined, [\"T5\"], false, \"\", \"\", " + CK + ")])" in js
        assert "const REPO_PATH = \"D:\\\\work\\\\my`repo\"" in js, "values are inserted as JSON strings"
        assert "const EFFORT = undefined" in js and "const WORKER_MODEL = \"sonnet\"" in js
        assert "const HELPER_EFFORT = 'low'" in js and "agentType: 'ping-personal:rhea', model: 'sonnet'" in js
        assert js.count("if (halt.by) return done()") == 2, "only a critic-gate stop ends the stage"
        assert "!results[" not in js.split("// ---- stage body (generated")[1], "no stop on a task that did not pass"
        assert "return done(await review(\"T3\", \"ping-personal:iris\"))" in js

        def run_node(js_text, votes="", lastline="", **extra_env):
            wrapped = os.path.join(tmp, "check.js")
            body = js_text.replace("export const meta", "const meta")
            with open(wrapped, "w", encoding="utf-8") as f:
                f.write(STUBS + "async function __wf() {\n" + body + "\n}\n"
                        "__wf().then(r => console.log(JSON.stringify({ r, calls, prompts, types })))\n")
            c = subprocess.run(["node", "--check", wrapped], capture_output=True, text=True)
            assert c.returncode == 0, c.stderr
            p = subprocess.run(["node", wrapped], capture_output=True, text=True, env=dict(os.environ, VOTES=votes, LASTLINE=lastline, **extra_env))
            assert p.returncode == 0, p.stderr
            return json.loads(p.stdout)

        # Behaviour: T1 fails; two seats defer it (L4: the third is not asked); the stage continues.
        # T2 needs T1 -> deferred too (M3: blocked by T1, so a retry never re-runs it); T3 passes.
        flow = {"name": "s4", "summary": "defer", "steps": [
            {**R, "id": "T1", "agent": "ping-personal:bunny", "phase": "A"},
            {**R, "id": "T2", "agent": "ping-personal:bunny", "phase": "A", "needs": ["T1"]},
            {**R, "id": "T3", "agent": "ping-personal:bunny", "phase": "B"}], "review": "T3"}
        spec4 = os.path.join(state, "stages", "s4.json")
        json.dump(flow, open(spec4, "w"))
        assert gen(state, "stage", "--spec", spec4).returncode == 0
        js4 = open(os.path.join(state, "stages", "s4.js"), encoding="utf-8").read()
        out = run_node(js4, "defer,defer,defer")
        res = out["r"]["results"]
        assert res["T1"]["deferred"] is True and res["T1"]["deferredBy"] == "agent" and res["T1"]["passed"] is False, res
        assert res["T2"]["deferred"] is True and res["T2"]["deferredBy"] == "agent" and not res["T2"].get("notRun"), res
        assert res["T2"]["reason"] == "blocked by T1" and "T2:gate" not in " ".join(out["calls"]), res
        assert res["T3"]["passed"] is True and out["r"]["stoppedBy"] is None, res
        assert out["r"]["review"]["findings"][0]["severity"] == "LOW"
        gates = [c for c in out["calls"] if ":gate:" in c]
        assert len(gates) == 2 and all(c.startswith("T1:") for c in gates), gates
        # H5: every gate seat is told defer is not allowed for code this run changed.
        assert "defer is not allowed: vote retry or stop" in out["prompts"][gates[0]], out["prompts"][gates[0]]
        # Two real stop votes end the stage at T1; T3 never runs.
        out = run_node(js4, "stop,stop,retry")
        assert out["r"]["stoppedBy"] == "critic-gate" and out["r"]["stoppedAt"] == "T1" and "T3" not in out["r"]["results"], out
        # No two seats agree (defer, retry, stop) -> defer with reason "no critic quorum", never a stop.
        out = run_node(js4, "defer,retry,stop")
        r1 = out["r"]["results"]["T1"]
        assert out["r"]["stoppedBy"] is None and r1["deferred"] and r1["deferredBy"] == "agent" and r1["reason"] == "no critic quorum", out
        out = run_node(js4, "stop,defer,retry")
        assert out["r"]["stoppedBy"] is None and out["r"]["results"]["T1"]["deferred"], out
        # H6: two seats return nothing, each is asked once more and is still empty -> one lone vote -> defer.
        out = run_node(js4, "defer,null,null,null,null")
        assert out["r"]["stoppedBy"] is None and out["r"]["results"]["T1"]["reason"] == "no critic quorum", out
        assert len([c for c in out["calls"] if c.endswith(":retry")]) == 2, out["calls"]
        # H6: a null seat is retried once; the retry's stop plus the third seat's stop is a real quorum.
        out = run_node(js4, "null,stop,defer,stop")
        assert out["r"]["stoppedBy"] == "critic-gate", out
        # A failed (not deferred) dependency leaves its dependent not-run: retry wins, the re-check still fails.
        out = run_node(js4, "retry,retry")
        res = out["r"]["results"]
        assert res["T1"]["passed"] is False and res["T1"]["deferred"] is False, res
        assert res["T2"]["notRun"] is True and res["T2"]["deferred"] is False, res
        # M4: passLine. The verifier must pass AND print that exact last line (trimmed).
        pl = dict(flow, name="s5", steps=[{**R, "id": "T3", "agent": "ping-personal:bunny", "phase": "A", "passLine": "ALL OK"}])
        spec5 = os.path.join(state, "stages", "s5.json")
        json.dump(pl, open(spec5, "w"))
        assert gen(state, "stage", "--spec", spec5).returncode == 0
        js5 = open(os.path.join(state, "stages", "s5.js"), encoding="utf-8").read()
        assert '"ALL OK", ' + CK + ')' in js5
        assert run_node(js5, "", " ALL OK ")["r"]["results"]["T3"]["passed"] is True
        out = run_node(js5, "defer,defer", "ALL OK but wrong")
        assert out["r"]["results"]["T3"]["passed"] is False and out["r"]["results"]["T3"]["deferred"] is True, out
        # Task ids with quotes and backticks stay valid JavaScript.
        weird = dict(flow, steps=[{**R, "id": "T\"`1", "agent": "ping-personal:bunny", "phase": "P\"x", "text": "a`${b}\\"}],
                     review="T\"`1")
        json.dump(weird, open(spec4, "w"))
        assert gen(state, "stage", "--spec", spec4).returncode == 0
        run_node(open(os.path.join(state, "stages", "s4.js"), encoding="utf-8").read())

        # Item 1: the verifier runs the task's own scoped check, never plan.md's done-check.
        solo = {"name": "s6", "summary": "one task", "steps": [dict(R, id="T3", agent="ping-personal:bunny", phase="A",
                                                                     check="python run_t3.py --fast")]}
        spec6 = os.path.join(state, "stages", "s6.json")
        json.dump(solo, open(spec6, "w"))
        assert gen(state, "stage", "--spec", spec6).returncode == 0
        js6 = open(os.path.join(state, "stages", "s6.js"), encoding="utf-8").read()
        out = run_node(js6)
        assert "python run_t3.py --fast" in out["prompts"]["T3:verify"], out["prompts"]["T3:verify"]
        # The verifier writes the run-log row with log_row.py (real clock); workers never edit the logs.
        assert "/scripts/log_row.py\" run --state-dir \"docs/proj-123/autopilot\" --task \"T3\"" in out["prompts"]["T3:verify"]
        assert "<" + "SKILL_DIR>" not in js6 and "file-checklist" not in out["prompts"]["T3"]
        assert "log_row.py\" effect" in out["prompts"]["T3"] and "Write tool" in out["prompts"]["T3"]
        assert out["r"]["stageCheck"] is None, "no stageCheck in the spec: nothing is returned for it"
        # Item 2: the run's base commit is inserted as a JSON string and drives "changed by this run".
        assert 'const BASE_COMMIT = "4b8d`3b26"' in js6
        assert "git diff 4b8d`3b26" in out["prompts"]["T3"]
        out = run_node(js4, "defer,defer,defer")
        assert "(git diff 4b8d`3b26)" in out["prompts"][[c for c in out["calls"] if ":gate:" in c][0]], "the gate's own rule names the base commit"
        # Item 1+5 stageCheck: after every task, one rhea verifier (sonnet, low) runs the full done command once.
        sc = dict(solo, name="s7", stageCheck={"command": "python full_done.py", "passLine": "ALL OK"})
        spec7 = os.path.join(state, "stages", "s7.json")
        json.dump(sc, open(spec7, "w"))
        assert gen(state, "stage", "--spec", spec7).returncode == 0
        js7 = open(os.path.join(state, "stages", "s7.js"), encoding="utf-8").read()
        assert "phases: [{ title: \"A\" }, { title: \"Stage check\" }]" in js7
        out = run_node(js7, "", "", STAGE_LAST=" ALL OK ")
        assert out["r"]["stageCheck"] == {"passed": True, "lastLine": " ALL OK "}, out["r"]
        assert out["calls"][-1] == "stage:check" and out["calls"].count("stage:check") == 1, out["calls"]
        assert "python full_done.py" in out["prompts"]["stage:check"]
        assert out["types"]["stage:check"] == "ping-personal:rhea"
        assert run_node(js7, "", "", STAGE_LAST="ALL OK but wrong")["r"]["stageCheck"]["passed"] is False
        assert run_node(js7, "", "", STAGE_PASS="0", STAGE_LAST="ALL OK")["r"]["stageCheck"]["passed"] is False
        # A critic-gate stop ends the stage before the stage check.
        sc4 = dict(flow, name="s8", stageCheck={"command": "python full_done.py"})
        json.dump(sc4, open(spec4, "w"))
        assert gen(state, "stage", "--spec", spec4).returncode == 0
        out = run_node(open(os.path.join(state, "stages", "s8.js"), encoding="utf-8").read(), "stop,stop")
        assert out["r"]["stoppedBy"] == "critic-gate" and out["r"]["stageCheck"] is None and "stage:check" not in out["calls"], out
        # Item 3 finalReview: Spec axis (amanda) then Standards axis (ms-mario), one after the other, never merged.
        fr = dict(solo, name="s9", finalReview=True)
        spec9 = os.path.join(state, "stages", "s9.json")
        json.dump(fr, open(spec9, "w"))
        assert gen(state, "stage", "--spec", spec9).returncode == 0
        js9 = open(os.path.join(state, "stages", "s9.js"), encoding="utf-8").read()
        out = run_node(js9)
        assert out["calls"][-2:] == ["final:spec", "final:standards"], out["calls"]
        assert out["types"]["final:spec"] == "ping-personal:amanda" and out["types"]["final:standards"] == "ping-personal:ms-mario"
        assert "git diff 4b8d`3b26...HEAD" in out["prompts"]["final:spec"] and "GOAL-BRIEF.md" in out["prompts"]["final:spec"]
        assert "CLAUDE.md" in out["prompts"]["final:standards"]
        rv = out["r"]["review"]
        assert rv["spec"]["findings"][0]["text"] == "spec gap" and rv["standards"]["findings"][0]["text"] == "style" and "findings" not in rv, rv
        assert "phases: [{ title: \"A\" }, { title: \"Review\" }]" in js9
        # A stage without finalReview keeps the old single-review shape.
        assert "findings" in run_node(js)["r"]["review"] and "final:spec" not in run_node(js)["calls"]

        # Refusals.
        a, b ={**R, "id": "T1", "phase": "P"}, {**R, "id": "T2", "phase": "P"}
        refused(state, spec, dict(SPEC, steps=[[]]), "empty group")
        refused(state, spec, dict(SPEC, steps=[[dict(a, id=f"T{n}", agent="general-purpose") for n in range(1, 4)]],
                                  review=None), "limit is 2")  # M6
        refused(state, spec, dict(SPEC, review="T9"), "review task T9")
        refused(state, spec, dict(SPEC, steps=[dict(a, agent="ping-personal:nobody")], review=None), "ping-personal:nobody")
        refused(state, spec, dict(SPEC, steps=[dict(a, agent="someone-else")], review=None), "someone-else")
        refused(state, spec, dict(SPEC, steps=[dict(a, agent="ping-personal:amanda", commits=True)], review=None), "no Bash")
        # A task agent with no Write tool can never write its output (a plan critic task given to ms-mario).
        refused(state, spec, dict(SPEC, steps=[dict(a, agent="ping-personal:ms-mario")], review=None), "has no Write tool")
        refused(state, spec, dict(SPEC, steps=[dict(a, agent="Explore")], review=None), "has no Write tool")
        refused(state, spec, dict(SPEC, steps=[[dict(a, agent="general-purpose", resources=["IIS"]),
                                                dict(b, agent="general-purpose", resources=["iis "])]], review=None), "resource")
        refused(state, spec, dict(SPEC, steps=[[dict(a, agent="general-purpose"),
                                                dict(b, agent="general-purpose", needs=["T1"])]], review=None), "same or a later")
        refused(state, spec, dict(SPEC, reviewer="ping-personal:nobody"), "reviewer")
        # M10: codex:codex-rescue is a critic seat only, never a task agent or the reviewer.
        refused(state, spec, dict(SPEC, steps=[dict(a, agent="codex:codex-rescue")], review=None), "codex:codex-rescue")
        refused(state, spec, dict(SPEC, reviewer="codex:codex-rescue"), "reviewer")
        refused(state, spec, dict(SPEC, steps=[dict(a, agent="general-purpose", passLine="  ")], review=None), "passLine")
        # Items 1+5: check and estimateK are REQUIRED per task and the refusal names the task.
        bare = {"id": "T7", "agent": "general-purpose", "phase": "P", "text": "x"}
        refused(state, spec, dict(SPEC, steps=[dict(bare, estimateK=5)], review=None), "task T7 has no 'check'")
        refused(state, spec, dict(SPEC, steps=[dict(bare, check="  ", estimateK=5)], review=None), "task T7 has no 'check'")
        refused(state, spec, dict(SPEC, steps=[dict(bare, check="c")], review=None), "task T7 has no 'estimateK'")
        for bad_k in (0, -3, True, "20"):
            refused(state, spec, dict(SPEC, steps=[dict(bare, check="c", estimateK=bad_k)], review=None), "task T7 has no 'estimateK'")
        too_big = ("split it: one task must fit one fresh context (about 100K, beyond which quality drops)")
        refused(state, spec, dict(SPEC, steps=[dict(bare, check="c", estimateK=101)], review=None), too_big)
        refused(state, spec, dict(SPEC, steps=[dict(bare, check="c", estimateK=250)], review=None), "task T7")
        json.dump(dict(SPEC, steps=[dict(bare, check="c", estimateK=100)], review=None), open(spec, "w"))
        assert gen(state, "stage", "--spec", spec).returncode == 0, "exactly 100K fits one context"
        # stageCheck and finalReview shapes.
        refused(state, spec, dict(SPEC, stageCheck={"command": " "}), "stageCheck")
        refused(state, spec, dict(SPEC, stageCheck="python x.py"), "stageCheck")
        refused(state, spec, dict(SPEC, finalReview=True), "finalReview replaces review")
        refused(state, spec, dict(SPEC, review=None, reviewer="ping-personal:iris", finalReview=True), "finalReview replaces review")
        refused(state, spec, dict(SPEC, review=None, finalReview="yes"), "finalReview must be")
        # M9: a task with no text needs a "Task <id>" heading in plan.md; the message names the task.
        no_text = dict(SPEC, steps=[dict(a, id="T9", agent="general-purpose")], review=None)
        refused(state, spec, no_text, "T9")
        open(plan_path, "w").write(PLAN + "Do Task T9 later (not a heading)\n")
        refused(state, spec, no_text, "T9")
        open(plan_path, "w").write("### Task T90 - near miss\n")
        refused(state, spec, no_text, "T9")
        open(plan_path, "w").write(PLAN + "### Task T9 - now described\n")
        json.dump(no_text, open(spec, "w"))
        assert gen(state, "stage", "--spec", spec).returncode == 0
        json.dump(dict(no_text, steps=[dict(no_text["steps"][0], id="T8", text="inline instructions")]), open(spec, "w"))
        open(plan_path, "w").write("")
        assert gen(state, "stage", "--spec", spec).returncode == 0
        os.remove(plan_path)
        refused(state, spec, no_text, "plan.md")
        open(plan_path, "w").write(PLAN)
        # Inputs: a missing key, caps / sessions required, a session id that is not listed, a bad domain critic.
        json.dump(dict(INPUTS, branch=""), open(inputs_path, "w"))
        r = gen(state, "tick")
        assert r.returncode != 0 and "missing: branch" in r.stderr, r.stderr
        for k in ("caps", "sessions", "baseCommit", "remoteTagsAtStart", "remoteHeadsAtStart"):
            json.dump({x: v for x, v in INPUTS.items() if x != k}, open(inputs_path, "w"))
            r = gen(state, "tick")
            assert r.returncode != 0 and f"missing: {k}" in r.stderr, r.stderr
        json.dump(dict(INPUTS, remoteTagsAtStart="abc refs/tags/v1"), open(inputs_path, "w"))
        r = gen(state, "tick")
        assert r.returncode != 0 and "remoteTagsAtStart must be a list" in r.stderr, r.stderr
        json.dump(INPUTS, open(inputs_path, "w"))
        r = gen(state, "tick", session="sess-other")
        assert r.returncode != 0 and "not in inputs.json sessions" in r.stderr, r.stderr
        r = gen(state, "tick", session="")
        assert r.returncode != 0 and "CLAUDE_CODE_SESSION_ID" in r.stderr, r.stderr
        json.dump(dict(INPUTS, domainCritic="ping-personal:nobody"), open(inputs_path, "w"))
        r = gen(state, "tick")
        assert r.returncode != 0 and "domainCritic" in r.stderr, r.stderr
        # M10: codex:codex-rescue is accepted as the domain critic and becomes a gate seat.
        json.dump(dict(INPUTS, domainCritic="codex:codex-rescue"), open(inputs_path, "w"))
        assert gen(state, "tick").returncode == 0
        json.dump(SPEC, open(spec, "w"))
        assert gen(state, "stage", "--spec", spec).returncode == 0
        assert "'ping-personal:rhea', \"codex:codex-rescue\"]" in open(os.path.join(state, "stages", "s3-build.js"), encoding="utf-8").read()

        sys.path.insert(0, os.path.dirname(GEN))
        import generate
        try:
            generate.check_filled("run <" + "TASK_ID_9> now", "probe")
            raise AssertionError("an unfilled placeholder was not refused")
        except SystemExit as e:
            assert "TASK_ID_9" in str(e)
        print("GENERATE TEST PASS")
    finally:
        shutil.rmtree(tmp)


if __name__ == "__main__":
    main()
