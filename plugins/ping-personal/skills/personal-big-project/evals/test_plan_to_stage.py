"""Self-check for scripts/plan_to_stage.py: a plan with four tasks (a commit task, a RED row, a list check, a
range need) becomes a stage spec with the right pairing, plan.md and tasks.csv get the task sections and rows once,
a re-run adds nothing, --spec-only writes only the spec, and a bad table fails before anything is written.
Run: python evals/test_plan_to_stage.py   Prints PLAN TO STAGE TEST PASS."""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "scripts", "plan_to_stage.py")

PLAN = """# Plan

## Stage s0-old

| id | agent | what | check | estimateK |
|---|---|---|---|---|
| S0-1 | bunny | an earlier stage | `python z.py` | 10 |

## Stage s1-demo

Some intro text.

| id | agent | what | needs | resources | commits | check | passLine | estimateK | redFile |
|---|---|---|---|---|---|---|---|---|---|
| S1-1 | bunny | write parser, fast | - | - | y | `python -m pytest tests/test_a.py -q` | `S1-1 PASS` | 30 | |
| S1-2 | ping-personal:vex | red test | | SQL Server | n | `python t.py` | fails before | 20 | tests/**/t.py |
| S1-3 | vex | two part check | - | IIS, disk | n | `python a.py`<br>`python b.py` | passed | 10 | |
| S1-4 | bunny | wire it up | S1-1..S1-3 | - | yes | `python w.py` | | 25.5 | |

## Task S1-1 - write parser

Write the parser.

## Task S1-2 - red test

Write the test first.

## Task S1-3 - two part check

Do the two things.

### Detail

A sub-heading stays inside the task.

## Task S1-4 - wire it up

Connect them.

## Stage s2-next

| id | agent | what | check | estimateK |
|---|---|---|---|---|
| S2-1 | bunny | next | `python n.py` | 10 |
"""


def run(args):
    return subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True, encoding="utf-8")


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def main():
    tmp = tempfile.mkdtemp()
    try:
        plan = os.path.join(tmp, "plan.src.md")
        with open(plan, "w", encoding="utf-8") as f:
            f.write(PLAN)
        state = os.path.join(tmp, "autopilot")
        os.makedirs(state)
        with open(os.path.join(state, "plan.md"), "w", encoding="utf-8", newline="\n") as f:
            f.write("# Run plan\n\n## Task S0-1 - an earlier stage\n\nold text\n")
        with open(os.path.join(state, "tasks.csv"), "w", encoding="utf-8", newline="\n") as f:
            f.write("id,stage,what,estimate,added\nS0-1,s0-old,an earlier stage,10,")  # no trailing newline on purpose
        base = ["--state-dir", state, "--plan", plan, "--stage", "s1-demo"]

        # Baseline first: a committing stage with no baseline captured and no baseline task is refused, writing nothing.
        r = run(base)
        assert r.returncode != 0 and "no baseline is captured yet" in r.stderr, r.stdout + r.stderr
        assert not os.path.exists(os.path.join(state, "stages")), "a refused stage writes no spec"
        with open(plan, "w", encoding="utf-8") as f:
            f.write(PLAN.replace("Write the parser.", "Write the parser. Run log_row.py baseline --none first."))
        r = run(["--state-dir", os.path.join(tmp, "with-task"), "--plan", plan, "--stage", "s1-demo", "--spec-only"])
        assert r.returncode == 0, r.stdout + r.stderr
        r = run(["--state-dir", os.path.join(tmp, "with-task"), "--plan", plan, "--stage", "s1-demo"])
        assert r.returncode == 0, "a baseline task in the stage satisfies the rule: " + r.stdout + r.stderr
        with open(plan, "w", encoding="utf-8") as f:
            f.write(PLAN)
        with open(os.path.join(state, "baseline-hashes.txt"), "w", encoding="utf-8", newline="\n") as f:
            f.write("none\n")

        r = run(base + ["--review", "S1-4"])
        assert r.returncode == 0, r.stdout + r.stderr
        assert "steps: ['S1-1', ['S1-2', 'S1-3'], 'S1-4']" in r.stdout, r.stdout
        spec = json.loads(read(os.path.join(state, "stages", "s1-demo.json")))
        assert spec["name"] == "s1-demo" and spec["summary"] == "s1-demo from plan.src.md", spec
        assert spec["review"] == "S1-4" and spec["reviewer"] == "ping-personal:iris", spec
        s1, pair, s4 = spec["steps"]
        assert isinstance(pair, list) and [t["id"] for t in pair] == ["S1-2", "S1-3"], spec["steps"]  # S1-1 commits, so it runs alone
        assert s1["id"] == "S1-1" and s1["agent"] == "ping-personal:bunny" and s1["commits"] is True, s1
        assert s1["check"] == "python -m pytest tests/test_a.py -q" and s1["passLine"] == "S1-1 PASS" and s1["phase"] == "s1-demo", s1
        red, two = pair
        assert red["agent"] == "ping-personal:vex" and red["expect"] == "fail" and red["redFile"] == "tests/**/t.py", red
        assert "passLine" not in red and red["resources"] == ["SQL Server"] and "needs" not in red, red
        assert two["check"] == ["python a.py", "python b.py"] and "passLine" not in two, two  # "passed" has no PASS: dropped
        assert two["resources"] == ["IIS", "disk"] and two["estimateK"] == 10, two
        assert s4["needs"] == ["S1-1", "S1-2", "S1-3"] and s4["commits"] is True and s4["estimateK"] == 25.5, s4

        plan_md = read(os.path.join(state, "plan.md"))
        assert plan_md.startswith("# Run plan\n\n## Task S0-1 - an earlier stage\n\nold text\n"), plan_md
        assert "# Stage s1-demo (copied from plan.src.md at " in plan_md, plan_md
        assert "\n## Task S1-1 - write parser, fast\n\nWrite the parser.\n" in plan_md, plan_md
        assert "## Task S1-3 - two part check\n\nDo the two things.\n\n### Detail\n\nA sub-heading stays inside the task.\n" in plan_md, plan_md
        assert "Connect them." in plan_md and "Stage s2-next" not in plan_md and "S2-1" not in plan_md, plan_md
        rows = read(os.path.join(state, "tasks.csv")).splitlines()
        assert rows == ["id,stage,what,estimate,added", "S0-1,s0-old,an earlier stage,10,",
                        "S1-1,s1-demo,write parser; fast,30,", "S1-2,s1-demo,red test,20,",
                        "S1-3,s1-demo,two part check,10,", "S1-4,s1-demo,wire it up,25.5,"], rows

        # Idempotent: a second run appends nothing and says what it skipped.
        before = (plan_md, read(os.path.join(state, "tasks.csv")))
        r = run(base)
        assert r.returncode == 0 and "skipped:" in r.stdout and "S1-1 (already in plan.md)" in r.stdout \
            and "S1-1 (already in tasks.csv)" in r.stdout, r.stdout
        assert (read(os.path.join(state, "plan.md")), read(os.path.join(state, "tasks.csv"))) == before
        assert "review" not in json.loads(read(os.path.join(state, "stages", "s1-demo.json"))), "no --review, no review"

        # An id an earlier stage already used is refused before anything is written; --spec-only (a retry) may reuse it.
        reuse = os.path.join(tmp, "plan.reuse.md")
        with open(reuse, "w", encoding="utf-8") as f:
            f.write(PLAN + "\n## Stage s3-fix\n\n| id | agent | what | check | estimateK |\n|---|---|---|---|---|\n"
                      "| S1-2 | bunny | fix again | `python f.py` | 10 |\n\n## Task S1-2 - fix again\n\nFix.\n")
        before = (read(os.path.join(state, "plan.md")), read(os.path.join(state, "tasks.csv")))
        r = run(["--state-dir", state, "--plan", reuse, "--stage", "s3-fix"])
        assert r.returncode != 0 and "S1-2 (used in s1-demo)" in r.stderr, r.stdout + r.stderr
        assert (read(os.path.join(state, "plan.md")), read(os.path.join(state, "tasks.csv"))) == before
        assert not os.path.exists(os.path.join(state, "stages", "s3-fix.json")), "a refused stage writes no spec"
        r = run(["--state-dir", state, "--plan", reuse, "--stage", "s3-fix", "--spec-only"])
        assert r.returncode == 0, "a retry spec may reuse ids: " + r.stdout + r.stderr

        # --spec-only writes the spec and leaves plan.md and tasks.csv alone (here they do not exist).
        only = os.path.join(tmp, "only")
        r = run(["--state-dir", only, "--plan", plan, "--stage", "s1-demo", "--spec-only"])
        assert r.returncode == 0, r.stdout + r.stderr
        assert os.listdir(only) == ["stages"] and os.listdir(os.path.join(only, "stages")) == ["s1-demo.json"], os.listdir(only)

        # A bad table fails before anything is written: generate.py's size limit, then a missing column and stage.
        bad_state = os.path.join(tmp, "bad")
        for label, text, needle in (
                ("too big", PLAN.replace("| 30 |", "| 500 |"), "GENERATE FAIL"),
                ("no check column", PLAN.replace("| check | passLine |", "| verify | passLine |"), "PLAN_TO_STAGE FAIL: stage s1-demo table has no 'check' column"),
                ("no task heading", PLAN.replace("## Task S1-2 - red test", "## Other"), "no '## Task S1-2' heading"),
                ("bad estimate", PLAN.replace("| 30 |", "| lots |"), "estimateK 'lots'")):
            with open(plan, "w", encoding="utf-8") as f:
                f.write(text)
            r = run(["--state-dir", bad_state, "--plan", plan, "--stage", "s1-demo"])
            assert r.returncode != 0 and needle in r.stderr, (label, r.stdout, r.stderr)
            assert not os.path.exists(bad_state), f"{label}: nothing may be written on a failed validation"
        # kind and model columns: a review row becomes a review step (no check), a model cell is kept.
        judged = os.path.join(tmp, "plan.judge.md")
        with open(judged, "w", encoding="utf-8") as f:
            f.write("## Stage s4-judge\n\n| id | agent | what | kind | model | check | estimateK |\n|---|---|---|---|---|---|---|\n"
                    "| J1 | ms-mario | judge the plan | review | advisor | - | 30 |\n| F1 | bunny | fix | | inherit | `python f.py` | 10 |\n\n"
                    "## Task J1 - judge\n\nJudge it.\n\n## Task F1 - fix\n\nFix it.\n")
        jstate = os.path.join(tmp, "judged")
        os.makedirs(jstate)
        with open(os.path.join(jstate, "inputs.json"), "w", encoding="utf-8") as f:
            json.dump({"advisorModel": "fable"}, f)
        r = run(["--state-dir", jstate, "--plan", judged, "--stage", "s4-judge", "--spec-only"])
        assert r.returncode == 0, r.stdout + r.stderr
        j1, f1 = [t for s in json.loads(read(os.path.join(jstate, "stages", "s4-judge.json")))["steps"]
                  for t in (s if isinstance(s, list) else [s])]
        assert j1["kind"] == "review" and j1["model"] == "advisor" and "check" not in j1, j1
        assert f1["model"] == "inherit" and "kind" not in f1, f1
        r = run(["--state-dir", bad_state, "--plan", plan, "--stage", "nope"])
        assert r.returncode != 0 and "no '## Stage nope' heading" in r.stderr, r.stderr
        print("PLAN TO STAGE TEST PASS")
    finally:
        shutil.rmtree(tmp)


if __name__ == "__main__":
    main()
