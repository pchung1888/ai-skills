"""Check that a revise task answered every open finding of a review step, by finding number. A check that
accepted any one "accepted" or "rejected" word once let a reviser answer an older set of findings.

  python check_answers.py --review <state-dir>/reviews/J1.md --answers <state-dir>/answers-J1.md

The review file is the table run_state.py writes ("| # | Severity | Finding | State |"). The answers file
needs, for each open finding number N, a line that starts with N (optionally "#N", "N.", "Finding N" or
"| N |") and contains "accepted" or "rejected". Example line: 3. rejected - the old page has no such button.
Last line: "<review id> ANSWERS PASS", or "ANSWERS FAIL: ..." with exit 1.
"""
import argparse
import os
import re
import sys


def open_numbers(review_text):
    """Numbers of the open findings in a reviews/<id>.md table."""
    out = []
    for line in review_text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 4 and cells[0].isdigit() and cells[-1] == "open":
            out.append(int(cells[0]))
    return out


def answered(answers_text):
    """Finding numbers that have an accepted or rejected answer line."""
    found = set()
    for line in answers_text.splitlines():
        m = re.match(r"^\W*(?:finding\s*)?#?(\d+)\b", line, re.I)
        if m and re.search(r"\b(accepted|rejected)\b", line, re.I):
            found.add(int(m.group(1)))
    return found


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--review", required=True, help="Example: docs/proj-123/autopilot/reviews/J1.md")
    ap.add_argument("--answers", required=True, help="Example: docs/proj-123/autopilot/answers-J1.md")
    a = ap.parse_args()
    try:
        review = open(a.review, encoding="utf-8-sig").read()
        answers = open(a.answers, encoding="utf-8-sig").read()
    except OSError as e:
        print(f"ANSWERS FAIL: {e}")
        return 1
    missing = [n for n in open_numbers(review) if n not in answered(answers)]
    if missing:
        print(f"ANSWERS FAIL: no accepted or rejected line for finding {', '.join(map(str, missing))}")
        return 1
    print(f"{os.path.splitext(os.path.basename(a.review))[0]} ANSWERS PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
