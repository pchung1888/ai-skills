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
    # --state-dir goes first: send passes everything after "--" to the command it runs.
    return subprocess.run([sys.executable, os.path.join(SCRIPTS, "log_row.py"), "--state-dir", state, *args],
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

        # push: a branch on inputs.json "protectedBranches" (the target of an open review request) is
        # refused before anything is written, and a push must name its branch once any branch is protected.
        with open(os.path.join(state, "inputs.json"), "w") as f:
            json.dump({"repoPath": "..", "caps": {"mail": 3, "push": 5}, "protectedBranches": ["feature/759"]}, f)
        before = len(statefiles.table_rows(os.path.join(state, "log", "side-effects.md")))
        r = log_row(state, "effect", "--kind", "push", "--ref", "feature/759", "--note", "x")
        assert r.returncode == 2 and "protected" in r.stdout, r.stdout
        r = log_row(state, "effect", "--kind", "push", "--ref", "refs/heads/feature/759", "--note", "x")
        assert r.returncode == 2 and "protected" in r.stdout, r.stdout
        r = log_row(state, "effect", "--kind", "push", "--note", "no ref")
        assert r.returncode == 2 and "--ref" in r.stdout, r.stdout
        assert len(statefiles.table_rows(os.path.join(state, "log", "side-effects.md"))) == before
        r = log_row(state, "effect", "--kind", "push", "--ref", "topic/759", "--note", "fix branch")
        assert r.returncode == 0 and "LOGGED push 1 of 5" in r.stdout, r.stdout
        # send: logs first, then runs the command; past the cap it refuses and never runs it.
        caps_state = os.path.join(tmp, "caps")
        os.makedirs(caps_state)
        with open(os.path.join(caps_state, "inputs.json"), "w") as f:
            json.dump({"caps": {"mail": 5}}, f)
        marker = os.path.join(tmp, "sent.txt")
        send = [sys.executable, "-c", "import sys; open(sys.argv[1], 'a').write('x')", marker]
        r = log_row(caps_state, "send", "--kind", "mail", "--count", "3", "--note", "3 test mails", "--key", "T5-1", "--", *send)
        assert r.returncode == 0 and "LOGGED mail 3 of 5" in r.stdout and open(marker).read() == "x", (r.stdout, r.stderr)
        rows = statefiles.table_rows(os.path.join(caps_state, "log", "side-effects.md"))
        assert [x[2] for x in rows] == ["3"], rows  # the row exists, written before the command ran
        r = log_row(caps_state, "send", "--kind", "mail", "--count", "3", "--note", "too many", "--", *send)
        assert r.returncode == 2 and "CAP REACHED" in r.stdout and open(marker).read() == "x", r.stdout  # not run
        # A retried key does not run the command again unless --retry says the earlier try did not happen.
        r = log_row(caps_state, "send", "--kind", "mail", "--count", "3", "--note", "again", "--key", "T5-1", "--", *send)
        assert r.returncode == 3 and open(marker).read() == "x", r.stdout
        r = log_row(caps_state, "send", "--kind", "mail", "--count", "3", "--note", "again", "--key", "T5-1", "--retry", "--", *send)
        assert r.returncode == 0 and open(marker).read() == "xx", r.stdout
        # The command's own failure exit code comes back.
        r = log_row(caps_state, "send", "--kind", "mail", "--count", "1", "--note", "fails", "--", sys.executable, "-c", "raise SystemExit(5)")
        assert r.returncode == 5, (r.returncode, r.stdout)
        r = log_row(caps_state, "send", "--kind", "mail", "--note", "no command")
        assert r.returncode == 2 and "command" in r.stdout, r.stdout
        # usage: one line per kind; WARN at 80% of the cap, FULL at the cap.
        r = log_row(caps_state, "usage")
        assert r.returncode == 0 and "WARN mail 4 of 5" in r.stdout, r.stdout
        # raise-cap: the owner's answer to the phone question; logged as a decision; never below what is used.
        r = log_row(caps_state, "raise-cap", "--kind", "mail", "--to", "3", "--note", "owner said 3")
        assert r.returncode == 2 and "below" in r.stdout, r.stdout
        r = log_row(caps_state, "raise-cap", "--kind", "mail", "--to", "10", "--note", "owner said raise mail to 10")
        assert r.returncode == 0 and statefiles.read_json_safe(os.path.join(caps_state, "inputs.json"))["caps"]["mail"] == 10, r.stdout
        decisions = statefiles.table_rows(os.path.join(caps_state, "log", "decisions.md"))
        assert decisions and "mail cap 5 -> 10" in decisions[-1][1] and "owner said" in decisions[-1][3], decisions
        assert "OK mail 4 of 10" in log_row(caps_state, "usage").stdout

        with open(os.path.join(state, "inputs.json"), "w") as f:
            json.dump({"repoPath": "..", "caps": {"mail": 3}}, f)

        # status: one real-clock row per STATUS.md Now rewrite, so the scorecard can measure how current it stayed.
        assert log_row(state, "status", "--note", "stage 2 running").returncode == 0
        srows = statefiles.table_rows(os.path.join(state, "log", "status-log.md"))
        assert len(srows) == 1 and check_run.DAY_TIME.match(srows[0][0]) and srows[0][1] == "stage 2 running", srows

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
