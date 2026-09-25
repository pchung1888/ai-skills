"""Round-trip guard for pipe characters in beacon table cells.

Mutation-proven gap: the writers escaped pipes and no reader unescaped them, so a
single '|' in a detour Proof -- routine in shell output and PowerShell error text,
which is exactly what PROOF is documented to hold -- put Status one column right of
where close_detour_row wrote.  The detour stayed open forever and finalize returned
exit 7 permanently.  Removing the escaping left all 38 eval suites green, so this
file exists to make that impossible again.

Exit 0 = all round trips hold.  Exit 1 = a cell was corrupted.
"""

import sys
from pathlib import Path

LIB = Path(__file__).resolve().parent.parent / "lib"
GOAL_LIB = Path(__file__).resolve().parents[2] / "personal-goal" / "lib"
sys.path.insert(0, str(LIB))
sys.path.insert(0, str(GOAL_LIB))

from log_appender import (append_detour_row, close_detour_row, open_detours,
                          append_decision_row, split_cells)
from phase_table import update_row, get_source
from plan_parser import phase_rows

PIPED_PROOF = "grid.vb:74 throws | see log"
PIPED_TITLE = "export the grid | as CSV"
failures = []


def check(label, cond, detail=""):
    if cond:
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label} -- {detail}")
        failures.append(label)


def detour_round_trip():
    body = ("## Detours\n"
            "| id | Opened | Origin | Blocks | Proof | Already checked | Status |\n"
            "|---|---|---|---|---|---|---|\n\n## Next\n")
    body, det = append_detour_row(body, "pre-existing", "phase 1",
                                  PIPED_PROOF, "existing formatter")
    check("detour is open after write", open_detours(body) == [det],
          f"open_detours -> {open_detours(body)}")

    row = next(l for l in body.split("\n") if l.startswith("| " + det))
    cells = split_cells(row)
    check("row has exactly 7 cells", len(cells) == 7, f"got {len(cells)}: {row}")
    check("proof text survives the pipe", PIPED_PROOF in cells[4], repr(cells[4]))

    body = close_detour_row(body, det)
    check("detour is closed after close", open_detours(body) == [],
          f"still open: {open_detours(body)}")

    row = next(l for l in body.split("\n") if l.startswith("| " + det))
    cells = split_cells(row)
    check("status cell holds the close date", cells[-1].strip().startswith("closed:"),
          repr(cells[-1]))
    check("already-checked was not overwritten", "existing formatter" in cells[5],
          repr(cells[5]))


def phase_row_round_trip():
    rows = phase_rows([(1, PIPED_TITLE)])
    body = ("## Phase Status\n"
            "| Phase | Source | Title | Status | Commit | Subagent |\n"
            "|---|---|---|---|---|---|\n" + rows + "\n\n## Next\n")
    check("parsed phase carries no fake warrant", get_source(body, 1) == "PROPOSAL",
          repr(get_source(body, 1)))

    body = body.replace("| PROPOSAL |", "| ASK:export the grid |")
    body = update_row(body, 1, "OK Done", "abc1234", "bunny")
    row = next(l for l in body.split("\n") if l.startswith("| 1 "))
    cells = split_cells(row)
    check("row still has 6 columns after advance", len(cells) == 6,
          f"got {len(cells)}: {row}")
    check("title survives the pipe", PIPED_TITLE in cells[2], repr(cells[2]))
    check("status landed in the status column", cells[3].strip() == "OK Done",
          repr(cells[3]))
    check("commit landed in the commit column", cells[4].strip() == "abc1234",
          repr(cells[4]))


def decision_round_trip():
    body = ("## Decisions\n"
            "| id | Date | Decision | Why | Ruled out |\n"
            "|---|---|---|---|---|\n\n## Next\n")
    body, dec = append_decision_row(body, "use a | delimiter", "because it reads",
                                    "tabs | spaces")
    row = next(l for l in body.split("\n") if l.startswith("| " + dec))
    cells = split_cells(row)
    check("decision row has 5 cells", len(cells) == 5, f"got {len(cells)}: {row}")
    check("decision text survives the pipe", "use a | delimiter" in cells[2],
          repr(cells[2]))


if __name__ == "__main__":
    print("detour round trip:")
    detour_round_trip()
    print("phase row round trip:")
    phase_row_round_trip()
    print("decision round trip:")
    decision_round_trip()
    if failures:
        print(f"\n{len(failures)} round trip(s) corrupted: {', '.join(failures)}")
        sys.exit(1)
    print("\nall pipe round trips hold")
    sys.exit(0)
