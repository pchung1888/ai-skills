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
        # --what-file: text with shell characters comes from a file, never from a command line.
        nasty = 'passed: $(rm -rf x) `id` "q" ; | & <a>'
        what = os.path.join(tmp, "verify-T4.txt")
        with open(what, "w", encoding="utf-8") as f:
            f.write(nasty + "\n")
        assert log_row(state, "run", "--task", "T4", "--what-file", what).returncode == 0
        rows = statefiles.table_rows(os.path.join(state, "log", "run-log.md"))
        assert rows[-1][1] == "T4" and rows[-1][2] == nasty, rows[-1]
        r = log_row(state, "run", "--task", "T4", "--what-file", os.path.join(tmp, "missing.txt"))
        assert r.returncode == 2 and "what-file" in r.stdout, r.stdout

        # effect: unknown kind and over-cap are refused, and nothing is written.
        r = log_row(state, "effect", "--kind", "push", "--note", "x")
        assert r.returncode == 2 and "allowed kinds: mail" in r.stdout, r.stdout
        assert log_row(state, "effect", "--kind", "mail", "--count", "2", "--note", "two", "--key", "T3-1").returncode == 0
        r = log_row(state, "effect", "--kind", "mail", "--count", "2", "--note", "too many")
        assert r.returncode == 2 and "cap 3" in r.stdout, r.stdout
        # A retry of the same action (same key) is not counted twice and exits 3, not 0; a new action still fits.
        for n in (1, 2):
            r = log_row(state, "effect", "--kind", "mail", "--count", "2", "--note", "retry", "--key", "T3-1")
            assert r.returncode == 3 and f"ALREADY LOGGED: T3-1 (retry {n} of 2" in r.stdout, r.stdout
        # Past MAX_REPLAYS retries the key is refused, so a reused key cannot repeat an action without limit.
        r = log_row(state, "effect", "--kind", "mail", "--note", "again", "--key", "T3-1")
        assert r.returncode == 2 and "already retried 2 times" in r.stdout, r.stdout
        assert log_row(state, "effect", "--kind", "mail", "--note", "one more", "--key", "T4-1").returncode == 0
        inputs = {"caps": {"mail": 3}}
        assert check_run.check_side_effects(state, inputs) == "", check_run.check_side_effects(state, inputs)
        effects = statefiles.table_rows(os.path.join(state, "log", "side-effects.md"))
        assert [r[2] for r in effects] == ["2", "0", "0", "1"], effects  # retries are logged with count 0

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
