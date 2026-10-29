"""Self-check for scripts/log_row.py: rows come out in the shape check_run.py reads, a side effect with no
cap or past its cap is refused before anything is written, a retried action is counted once, and baseline
lines pass check_run's baselines check. Run: python evals/test_log_row.py   Prints LOG ROW TEST PASS."""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "..", "scripts")
sys.path.insert(0, SCRIPTS)
import check_run  # noqa: E402
import statefiles  # noqa: E402


def log_row(state, *args):
    return subprocess.run([sys.executable, os.path.join(SCRIPTS, "log_row.py"), *args, "--state-dir", state],
                          capture_output=True, text=True)


def main():
    tmp = tempfile.mkdtemp()
    try:
        state = os.path.join(tmp, "autopilot")
        os.makedirs(state)
        with open(os.path.join(state, "inputs.json"), "w") as f:
            json.dump({"repoPath": "..", "caps": {"mail": 3}}, f)

        # run: a header, then one row with a real-clock time; a pipe in the text stays in its cell.
        assert log_row(state, "run", "--task", "T3", "--what", "passed: a | b").returncode == 0
        assert log_row(state, "run", "--task", "stage", "--what", "failed: x").returncode == 0
        rows = statefiles.table_rows(os.path.join(state, "log", "run-log.md"))
        assert [r[1] for r in rows] == ["T3", "stage"] and rows[0][2] == "passed: a | b", rows
        assert check_run.check_log_times(state) == "", check_run.check_log_times(state)

        # effect: unknown kind and over-cap are refused, and nothing is written.
        r = log_row(state, "effect", "--kind", "push", "--note", "x")
        assert r.returncode == 2 and "allowed kinds: mail" in r.stdout, r.stdout
        assert log_row(state, "effect", "--kind", "mail", "--count", "2", "--note", "two", "--key", "T3-1").returncode == 0
        r = log_row(state, "effect", "--kind", "mail", "--count", "2", "--note", "too many")
        assert r.returncode == 2 and "cap 3" in r.stdout, r.stdout
        # A retry of the same action (same key) is not counted twice; a new action still fits.
        r = log_row(state, "effect", "--kind", "mail", "--count", "2", "--note", "retry", "--key", "T3-1")
        assert r.returncode == 0 and "ALREADY LOGGED" in r.stdout, r.stdout
        assert log_row(state, "effect", "--kind", "mail", "--note", "one more", "--key", "T4-1").returncode == 0
        inputs = {"caps": {"mail": 3}}
        assert check_run.check_side_effects(state, inputs) == "", check_run.check_side_effects(state, inputs)
        assert len(statefiles.table_rows(os.path.join(state, "log", "side-effects.md"))) == 2

        # baseline: lines check_run accepts; a changed file fails; --none is accepted; a missing file is refused.
        with open(os.path.join(tmp, "keep.txt"), "w") as f:
            f.write("same")
        assert log_row(state, "baseline", "keep.txt").returncode == 0
        assert log_row(state, "baseline", "--none").returncode == 0
        assert check_run.check_baselines(state, {"repoPath": ".."}) == ""
        assert log_row(state, "baseline", "nope.txt").returncode == 2
        with open(os.path.join(tmp, "keep.txt"), "w") as f:
            f.write("changed")
        assert "keep.txt" in check_run.check_baselines(state, {"repoPath": ".."})
        print("LOG ROW TEST PASS")
    finally:
        shutil.rmtree(tmp)


if __name__ == "__main__":
    main()
