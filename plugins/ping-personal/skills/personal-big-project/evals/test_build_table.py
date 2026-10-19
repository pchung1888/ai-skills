"""Self-check for scripts/build_table.py against trimmed journals from a real 37-hour run
(evals/fixtures/journals). Run: python evals/test_build_table.py   Prints BUILD TABLE TEST PASS."""
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import build_table  # noqa: E402
import statefiles  # noqa: E402

PLANNED = "T0 M1 T1 H2 H3 H4 H5 H6 T5a T2 T4 T3 T6a T7 T8 T5b T6b T9 T10 T11".split()
REAL_HEADER = ("| # | Stage | Task | What it does (plain words, <=12 words) | Status | Started | Finished "
               "| Tokens used | Token estimate | Notes |")  # header of the real run's hand-built table


def row(text, task):
    hit = [l for l in text.splitlines() if l.startswith("| ") and l.split(" | ")[2] == task]
    assert len(hit) == 1, f"expected one row for {task}, got {len(hit)}"
    return [c.strip() for c in hit[0].strip("|").split("|")]


def write(path, text, encoding="utf-8"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding=encoding, newline="") as f:
        f.write(text)


def agent(label, agent_id, started="1792300000000", tokens="100", state="done"):
    entry = {"type": "workflow_agent", "label": label, "state": state, "tokens": tokens, "durationMs": "1000"}
    if agent_id:
        entry["agentId"] = agent_id
    if started is not None:
        entry["startedAt"] = started
    return entry


def extra_cases():
    tmp = tempfile.mkdtemp()
    saved_env = {k: os.environ.get(k) for k in ("HOME", "USERPROFILE")}
    try:
        home = os.path.join(tmp, "home")
        os.environ["HOME"] = os.environ["USERPROFILE"] = home
        for sid, wf, agents in (
                ("sessA", "wf_a.json", [agent("T1", "id1"), agent("T2", "id2")]),
                ("sessB", "wf_b.json", [agent("T2", "id2", tokens="999"), agent("T3", "id3", started=None)])):
            write(os.path.join(home, ".claude", "projects", "proj", sid, "workflows", wf),
                  json.dumps({"workflowName": sid, "startTime": "1" if sid == "sessA" else "2", "workflowProgress": agents}))
        # A journal still being written must not crash the build.
        write(os.path.join(home, ".claude", "projects", "proj", "sessB", "workflows", "wf_half.json"), '{"workflowProgress": [')

        state = os.path.join(tmp, "autopilot")
        write(os.path.join(state, "tasks.csv"), "\ufeffid,stage,what,estimate,added,owner\nT1,S,one,,,ann\nT2,S,two,,,bob\nT3,S,three,,,cy\nT4,S,four,,,di\nT5,S,five,,,ed\nT6,S,six,,,flo\n",
              encoding="utf-8")
        write(os.path.join(state, "inputs.json"), json.dumps({"sessions": ["sessA", "sessB"]}))
        write(os.path.join(state, "run-state.json"), json.dumps({"stages": [{"name": "s1", "tasks": {
            "T1": {"outcome": "passed"}, "T2": {"outcome": "deferred", "deferredBy": "agent"},
            "T3": {"outcome": "deferred", "deferredBy": "owner"}, "T4": {"outcome": "failed"},
            "T5": {"outcome": "not-run"}}}]}))
        dirs = statefiles.journal_dirs(statefiles.read_json_safe(os.path.join(state, "inputs.json")))
        assert len(dirs) == 2, dirs  # both sessions, not only the current one
        text = open(build_table.build(state, dirs), encoding="utf-8").read()
        t1, t2, t3 = row(text, "T1"), row(text, "T2"), row(text, "T3")
        assert t1[4] == "Done" and t1[5] != "-", t1  # journal says done, outcome says passed
        assert t2[4] == "Deferred (agent)" and t2[7] == "999", t2  # id2 counted once, newest copy
        assert t3[4] == "Deferred (owner)" and t3[5] == "-", t3  # no startedAt -> "-"
        assert row(text, "T4")[4] == "Failed" and row(text, "T5")[4] == "Not run"
        assert row(text, "T6")[4] == "Not started"
        csv_text = open(os.path.join(state, "tasks.csv"), encoding="utf-8").read()
        assert csv_text.startswith("id,stage,what,estimate,added,owner") and "T3,S,three,,,cy" in csv_text, csv_text
        assert not [n for n in os.listdir(state) if n.endswith(".tmp")], "temp file left behind"

        # A task whose journal says done but run-state says failed shows Failed (outcome wins).
        write(os.path.join(state, "run-state.json"), json.dumps({"stages": [{"name": "s1", "tasks": {"T1": {"outcome": "failed"}}}]}))
        assert row(open(build_table.build(state, dirs), encoding="utf-8").read(), "T1")[4] == "Failed"
        # A half-written run-state.json falls back to the journal state.
        write(os.path.join(state, "run-state.json"), '{"stages": [')
        assert row(open(build_table.build(state, dirs), encoding="utf-8").read(), "T1")[4] == "Done"
        # A headerless run log and a pipe escaped in a cell lose no row.
        write(os.path.join(state, "log", "run-log.md"), "| Sat 10-17 07:54 | T6 | made a \\| b (3/4) | - |\n")
        assert row(open(build_table.build(state, dirs), encoding="utf-8").read(), "T6")[4] == "Done (logged) (3/4)"
    finally:
        for k, v in saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(tmp)


def main():
    tmp = tempfile.mkdtemp()
    try:
        state = os.path.join(tmp, "autopilot")
        os.makedirs(os.path.join(state, "log"))
        with open(os.path.join(state, "tasks.csv"), "w", encoding="utf-8") as f:
            f.write("id,stage,what,estimate,added\n")
            f.writelines(f"{t},Plan stage,does {t},,\n" for t in PLANNED)
        with open(os.path.join(state, "log", "run-log.md"), "w", encoding="utf-8") as f:
            f.write("| When | Task | What happened | Evidence |\n|---|---|---|---|\n"
                    "| Sat 10-17 07:54 | T5b | converted reports (48/48) | results/t5b.md |\n"
                    "| Sat 10-17 06:00 | T11 | done by hand outside a workflow | - |\n")
        # One extra journal with an agent still running.
        live = os.path.join(tmp, "live")
        os.makedirs(live)
        with open(os.path.join(live, "wf_live.json"), "w", encoding="utf-8") as f:
            json.dump({"workflowName": "s6", "startTime": "9999999999999", "workflowProgress": [
                {"type": "workflow_agent", "label": "T10:extra", "state": "running",
                 "startedAt": "1792300000000", "tokens": "1000"}]}, f)
        journals = [os.path.join(HERE, "fixtures", "journals"), live]

        out = build_table.build(state, journals, now=datetime(2026, 10, 18, 9, 0))
        text = open(out, encoding="utf-8").read()
        assert REAL_HEADER in text, "column header differs from the real run's table"

        t2 = row(text, "T2")
        assert t2[4] == "Done" and t2[7] == "89,847", t2
        assert t2[5] == build_table.day_time(1792229329151), t2  # Sat 10-17 05:28 on an Eastern-time box
        t9 = row(text, "T9")
        assert t9[7] == f"{109089 + 246389 + 101548 + 221561:,}" and "fix rounds: 1" in t9[9], t9
        assert row(text, "T5b")[4] == "Done (48/48)"
        assert row(text, "T10")[4] == "Running" and row(text, "T10")[6] == "-"
        t11 = row(text, "T11")
        assert t11[4] == "Done (logged)" and t11[6] == "Sat 10-17 06:00" and t11[7] == "don't know", t11
        commit = row(text, "commit")
        assert commit[9].startswith("ADDED") and commit[7] == f"{55461 + 59985 + 62345 + 59043:,}", commit
        assert "- T5b: plan.md section \"Task T5b\"; live log log/run-log.md; evidence results/t5b.md" in text

        # Rows never move or vanish: a rebuild without the live journal keeps every row in place.
        order1 = [l.split(" | ")[2] for l in text.splitlines() if l.startswith("| ") and l[2].isdigit()]
        text2 = open(build_table.build(state, journals[:1]), encoding="utf-8").read()
        order2 = [l.split(" | ")[2] for l in text2.splitlines() if l.startswith("| ") and l[2].isdigit()]
        assert order1 == order2 and order1[:len(PLANNED)] == PLANNED, (order1, order2)
        assert all(ord(c) < 128 for c in text), "PROGRESS.md must be ASCII"
        extra_cases()
        print("BUILD TABLE TEST PASS")
    finally:
        shutil.rmtree(tmp)


if __name__ == "__main__":
    main()
