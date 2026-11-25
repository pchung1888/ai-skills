"""Tests for scripts/check_plan.py, the reading-plan coverage check.

Run: python -m unittest evals/test_check_plan.py  (from the skill folder)
"""
import pathlib
import subprocess
import sys
import tempfile
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "check_plan.py"

PLAN_HEAD = "| Step | File | Lines | Topic |\n|---|---|---|---|\n"


def run(root, plan_rows):
    plan = pathlib.Path(root) / "plan.md"
    plan.write_text("# Plan\n\n" + PLAN_HEAD + plan_rows, encoding="ascii")
    p = subprocess.run([sys.executable, str(SCRIPT), str(plan), "--root", str(root)],
                       capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


class CheckPlan(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = pathlib.Path(self.tmp.name)
        (root / "src").mkdir()
        # 30 code lines plus two trailing blank lines, which need no step.
        (root / "src" / "Page.tsx").write_text("".join(f"line {i}\n" for i in range(1, 31)) + "\n\n")
        (root / "small.json").write_text("{\n}\n")
        self.root = root

    def tearDown(self):
        self.tmp.cleanup()

    def test_full_coverage_passes(self):
        code, out = run(self.root, "| 1 | small.json | all | config |\n"
                                   "| 2a | src/Page.tsx | 1-10 | setup |\n"
                                   "| 2b | src/Page.tsx | 11-30 | screen |\n")
        self.assertEqual(code, 0, out)
        self.assertIn("PLAN PASS", out)

    def test_skipped_section_fails_and_names_the_gap(self):
        code, out = run(self.root, "| 2a | src/Page.tsx | 1-10 | setup |\n"
                                   "| 2c | src/Page.tsx | 21-30 | buttons |\n")
        self.assertEqual(code, 1, out)
        self.assertIn("src/Page.tsx", out)
        self.assertIn("11-20", out)

    def test_missing_file_fails(self):
        code, out = run(self.root, "| 1 | src/Nope.tsx | all | ghost |\n")
        self.assertEqual(code, 1, out)
        self.assertIn("not found", out)

    def test_range_past_end_fails(self):
        code, out = run(self.root, "| 1 | small.json | 1-9 | config |\n")
        self.assertEqual(code, 1, out)
        self.assertIn("past the end", out)

    def test_multiple_ranges_in_one_cell(self):
        code, out = run(self.root, "| 2 | src/Page.tsx | 1-10, 11-30 | all of it |\n")
        self.assertEqual(code, 0, out)


if __name__ == "__main__":
    unittest.main()
