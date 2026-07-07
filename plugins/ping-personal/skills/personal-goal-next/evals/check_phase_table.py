#!/usr/bin/env python3
"""Unit-test the personal-goal-next beacon-mutation core (phase_table.update_row)
without triggering advance.py's git commit. Reads evals/fixtures/beacon-sample.md.

Exit 0 = all guards hold; 1 = a guard regressed (details on stderr).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from phase_table import update_row  # noqa: E402

fixture = Path(__file__).resolve().parent / "fixtures" / "beacon-sample.md"
content = fixture.read_text(encoding="utf-8")

fails = []

# 1. A fresh (Pending) phase advances: new status + commit are recorded on its row.
out = update_row(content, 1, "PASS-DONE", "c0ffee1", "driver")
if "c0ffee1" not in out:
    fails.append("update_row did not record the commit when advancing phase 1")
if not any(ln.startswith("| 1 ") and "PASS-DONE" in ln for ln in out.split("\n")):
    fails.append("phase 1 row was not flipped to the new status")

# 2. Duplicate-advance guard: phase 2 is already Done -> must raise.
try:
    update_row(content, 2, "PASS-DONE", "x", "driver")
    fails.append("duplicate-advance on already-Done phase 2 was NOT rejected")
except RuntimeError:
    pass

# 3. Undeclared phase -> must raise (cannot advance a phase the beacon never declared).
try:
    update_row(content, 99, "PASS-DONE", "x", "driver")
    fails.append("advancing an undeclared phase 99 was NOT rejected")
except RuntimeError:
    pass

if fails:
    for f in fails:
        print("FAIL:", f, file=sys.stderr)
    sys.exit(1)
print("phase_table guards OK")
sys.exit(0)
