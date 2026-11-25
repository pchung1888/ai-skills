"""Self-check for scripts/run_check.py: a passing check, one failing command, RED proof (file exists and every
command fails), RED that already passes, RED with a missing file, a timeout, and a malformed checks JSON.
Run: python evals/test_run_check.py   Prints RUN CHECK TEST PASS."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
RUN = os.path.join(HERE, "..", "scripts", "run_check.py")


def py(code):
    """A shell command that runs one line of Python (no double quotes inside code)."""
    return f'"{sys.executable}" -c "{code}"'


OK = py("print('all fine')")
BAD = py("import sys; print('boom'); sys.exit(3)")


def run(tmp, doc):
    """(exit code, output lines) of run_check.py on a checks JSON built from doc."""
    path = os.path.join(tmp, "checks.json")
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc if isinstance(doc, str) else json.dumps(doc))
    done = subprocess.run([sys.executable, RUN, path], capture_output=True, text=True, encoding="utf-8")
    return done.returncode, done.stdout.splitlines()


def main():
    tmp = tempfile.mkdtemp()
    try:
        test_file = os.path.join(tmp, "test_x.py")
        open(test_file, "w").write("x\n")

        code, out = run(tmp, {"task": "T3", "commands": [OK, OK]})
        assert code == 0 and out == ["[1/2] exit 0: all fine", "[2/2] exit 0: all fine", "T3 CHECK PASS"], out

        code, out = run(tmp, {"task": "T3", "commands": [OK, BAD, OK]})
        assert code == 1 and out[1] == "[2/3] exit 3: boom" and out[-1] == "T3 CHECK FAIL (1 of 3 failed)", out
        assert out[2].startswith("[3/3]"), "later commands still run, so the report shows every failure"

        # RED proof: the test file exists and every command fails.
        code, out = run(tmp, {"task": "S3-1", "commands": [BAD, BAD], "expect": "fail", "file": test_file})
        assert code == 0 and out[-1] == "S3-1 RED PASS", out
        # file is a glob relative to cwd, "**" included.
        code, out = run(tmp, {"task": "S3-1", "commands": [BAD], "expect": "fail", "file": "**/test_*.py", "cwd": tmp})
        assert code == 0 and out[-1] == "S3-1 RED PASS", out
        # RED with no file given still needs a failing command.
        code, out = run(tmp, {"task": "S3-1", "commands": [BAD], "expect": "fail"})
        assert code == 0 and out[-1] == "S3-1 RED PASS", out
        # A command that already passes cannot prove the code is missing.
        code, out = run(tmp, {"task": "S3-1", "commands": [BAD, OK], "expect": "fail", "file": test_file})
        assert code == 1 and out[-1] == "S3-1 RED FAIL: command 2 already passes, so it cannot prove the code it targets", out
        # A missing test file is RED FAIL and no command runs.
        code, out = run(tmp, {"task": "S3-1", "commands": [BAD], "expect": "fail", "file": os.path.join(tmp, "nope_*.py")})
        assert code == 1 and out[-1].startswith("S3-1 RED FAIL: test file missing") and not any(l.startswith("[") for l in out), out

        # A timeout is a failing command; a RED check never accepts it as "fails".
        slow = py("import time; time.sleep(30)")
        started = time.time()
        code, out = run(tmp, {"task": "T9", "commands": [slow], "timeoutSec": 1})
        assert code == 1 and out[0] == "[1/1] exit 124: timeout after 1 s" and out[-1] == "T9 CHECK FAIL (1 of 1 failed)", out
        code, out = run(tmp, {"task": "T9", "commands": [slow], "expect": "fail", "timeoutSec": 1})
        assert code == 1 and out[-1] == "T9 RED FAIL: command 1 timed out", out
        assert time.time() - started < 25, "the timeout must kill the whole process tree, not wait for it"

        # A checks JSON that cannot be read or is malformed exits 2 and says so.
        code, out = run(tmp, "{not json")
        assert code == 2 and out[0].startswith("RUN_CHECK FAIL: cannot read"), out
        for bad in ({"task": "T1", "commands": []}, {"task": "T1", "commands": [OK], "expect": "maybe"},
                    {"commands": [OK]}, {"task": "T1", "commands": [OK], "timeoutSec": 0}):
            code, out = run(tmp, bad)
            assert code == 2 and out[0].startswith("RUN_CHECK FAIL: checks JSON needs"), (bad, out)
        print("RUN CHECK TEST PASS")
    finally:
        shutil.rmtree(tmp)


if __name__ == "__main__":
    main()
