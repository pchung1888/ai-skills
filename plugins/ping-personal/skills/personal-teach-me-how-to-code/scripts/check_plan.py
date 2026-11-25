"""Fail a reading plan that leaves part of a planned file out of every step.

The plan is a Markdown table with the columns Step | File | Lines | Topic.
Lines is "all", one range such as "41-57", or several ranges such as "1-10, 11-30".
File paths are relative to --root, the code folder being taught.
Blank lines at the end of a file need no step.

Usage: python check_plan.py <plan.md> --root <code folder>
Exit 0 prints PLAN PASS. Exit 1 lists each gap, missing file or bad range.
"""
import argparse
import pathlib
import re
import sys


def read_rows(plan_text):
    """Yield (step, file, lines) from every table row whose header has File and Lines."""
    cols = None
    for line in plan_text.splitlines():
        if not line.strip().startswith("|"):
            cols = None
            continue
        cells = [c.strip().strip("`") for c in line.strip().strip("|").split("|")]
        if cols is None:
            low = [c.lower() for c in cells]
            if "file" in low and "lines" in low:
                cols = (low.index("step") if "step" in low else 0, low.index("file"), low.index("lines"))
            continue
        if set("".join(cells)) <= set("-: "):
            continue  # the |---|---| divider row
        yield cells[cols[0]], cells[cols[1]], cells[cols[2]]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("plan")
    ap.add_argument("--root", required=True)
    a = ap.parse_args()
    root = pathlib.Path(a.root)
    covered, problems = {}, []

    for step, rel, lines in read_rows(pathlib.Path(a.plan).read_text(encoding="utf-8")):
        path = root / rel
        if not path.is_file():
            problems.append(f"step {step}: {rel} not found under {root}")
            continue
        text = path.read_text(encoding="utf-8", errors="replace").splitlines()
        while text and not text[-1].strip():
            text.pop()
        n = len(text)
        seen = covered.setdefault(rel, (n, set()))[1]
        if lines.lower() == "all":
            seen.update(range(1, n + 1))
            continue
        for part in lines.split(","):
            m = re.fullmatch(r"\s*(\d+)\s*(?:-\s*(\d+))?\s*", part)
            if not m:
                problems.append(f"step {step}: {rel} has an unreadable range '{part.strip()}'")
                continue
            lo, hi = int(m.group(1)), int(m.group(2) or m.group(1))
            if hi > n:
                problems.append(f"step {step}: {rel} range {lo}-{hi} goes past the end (line {n})")
            seen.update(range(lo, min(hi, n) + 1))

    for rel, (n, seen) in sorted(covered.items()):
        gap_start = None
        for i in range(1, n + 2):
            if i <= n and i not in seen:
                gap_start = gap_start or i
            elif gap_start:
                problems.append(f"{rel}: lines {gap_start}-{i - 1} are in no step")
                gap_start = None

    if not covered and not problems:
        problems.append("no table with File and Lines columns found")
    if problems:
        print("\n".join(problems))
        print(f"PLAN FAIL ({len(problems)} problems)")
        return 1
    print(f"PLAN PASS ({len(covered)} files, every line in a step)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
