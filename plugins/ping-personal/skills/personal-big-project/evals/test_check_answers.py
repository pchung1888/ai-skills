"""Self-check for scripts/check_answers.py. Run: python evals/test_check_answers.py   Prints CHECK ANSWERS TEST PASS."""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "scripts", "check_answers.py")
REVIEW = ("# Review step J1\n\n| # | Severity | Finding | State |\n|---|---|---|---|\n"
          "| 1 | HIGH | a | open |\n| 2 | LOW | b | closed |\n| 3 | MEDIUM | c | open |\n")


def check(tmp, answers):
    with open(os.path.join(tmp, "a.md"), "w", encoding="utf-8") as f:
        f.write(answers)
    r = subprocess.run([sys.executable, SCRIPT, "--review", os.path.join(tmp, "J1.md"), "--answers",
                        os.path.join(tmp, "a.md")], capture_output=True, text=True)
    return r.returncode, r.stdout.strip().splitlines()[-1]


def main():
    tmp = tempfile.mkdtemp()
    try:
        with open(os.path.join(tmp, "J1.md"), "w", encoding="utf-8") as f:
            f.write(REVIEW)
        assert check(tmp, "1. accepted - fixed\nFinding #3: rejected, out of scope\n") == (0, "J1 ANSWERS PASS")
        # one accept word for the whole set no longer passes: finding 3 has no answer
        code, line = check(tmp, "All findings accepted.\n1. accepted\n")
        assert code == 1 and line.endswith("finding 3"), line
        # a number with no verdict word is not an answer; a closed finding needs none
        code, line = check(tmp, "1. accepted\n3. will look later\n")
        assert code == 1 and "3" in line, line
        print("CHECK ANSWERS TEST PASS")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
