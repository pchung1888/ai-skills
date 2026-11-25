"""Self-check for scripts/timeline.py: events from every log come out oldest first with their source,
WAIT ticks and BOX OK rows are left out, a rebuild replaces only the marked section, and a hand-written
note outside it survives. Run: python evals/test_timeline.py   Prints TIMELINE TEST PASS."""
import os
import shutil
import sys
import tempfile
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import statefiles  # noqa: E402
import timeline  # noqa: E402


def table(path, header, rows):
    with open(path, "w", encoding="utf-8") as f:
        f.write(header + "\n" + "|---" * (header.count("|") - 1) + "|\n")
        f.writelines("| " + " | ".join(r) + " |\n" for r in rows)


def main():
    tmp = tempfile.mkdtemp()
    try:
        log = os.path.join(tmp, "log")
        os.makedirs(log)
        os.makedirs(os.path.join(tmp, "reports"))
        table(os.path.join(log, "run-log.md"), "| When | Task | What happened | Evidence |",
              [["Tue 11-10 23:14", "F3", "passed: OK", "-"], ["Wed 11-11 01:00", "S4", "failed: x", "-"], ["later", "S5", "?", "-"]])
        table(os.path.join(log, "decisions.md"), "| When | Decision | Options | Why | Cost |",
              [["Tue 11-10 23:20", "wrap RED checks", "a or b", "verifier", "0"]])
        table(os.path.join(log, "owner-feedback.md"), "| When | Class | Skill | Missed what | Like | Quote |",
              [["Wed 11-11 08:20", "fix", "big-project", "stale table", "", "why old?"]])
        table(os.path.join(log, "quota-log.md"), "| When | 5h | 7d | Reset | Action |",
              [["Tue 11-10 23:15", "10%", "5%", "x", "WAIT"], ["Tue 11-10 23:45", "12%", "5%", "x", "LAUNCH"]])
        table(os.path.join(log, "box-health.md"), "| When | Result | Warnings |",
              [["Tue 11-10 23:15", "BOX OK", ""], ["Wed 11-11 03:45", "BOX WARN (1)", "box-orphans"]])
        open(os.path.join(tmp, "reports", "2026-11-11-0846.md"), "w").write("# Report\n")
        path = os.path.join(tmp, "TIMELINE.md")
        open(path, "w").write("# Audit\n\nHand-written note that must survive.\n")

        timeline.build(tmp, now=datetime(2026, 11, 11, 9, 0))
        text = statefiles.read_text(path)
        assert "Hand-written note that must survive." in text
        rows = statefiles.text_rows(text.split(timeline.BEGIN, 1)[1])
        whens = [r[0] for r in rows]
        assert whens == sorted(whens, key=statefiles.day_key), whens
        assert [r[0] for r in rows] == ["Tue 11-10 23:14", "Tue 11-10 23:20", "Tue 11-10 23:45", "Wed 11-11 01:00",
                                        "Wed 11-11 03:45", "Wed 11-11 08:20", "Wed 11-11 08:46"], whens
        assert rows[1][3] == "log/decisions.md row 1" and rows[6][2] == "report saved", rows
        assert not any("WAIT" in r[2] or "BOX OK" in r[2] for r in rows), rows
        assert "1 rows without a time" in text

        # A rebuild after a new row replaces the section, never appends a second one.
        table(os.path.join(log, "status-log.md"), "| When | What |", [["Wed 11-11 09:05", "s7 launched"]])
        timeline.build(tmp)
        text = statefiles.read_text(path)
        assert text.count(timeline.BEGIN) == 1 and "status: s7 launched" in text
        print("TIMELINE TEST PASS")
    finally:
        shutil.rmtree(tmp)


if __name__ == "__main__":
    main()
