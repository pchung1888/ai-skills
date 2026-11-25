"""Self-check for scripts/box_health.ps1 with fake probe files, plus one live smoke run.
Run: python evals/test_box_health.py   Prints BOX HEALTH TEST PASS."""
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "scripts", "box_health.ps1")
PWSH = shutil.which("pwsh")

BASE = {
    "diskFreeGB": {"C:": 100, "D:": 200},
    "availMB": 20000, "commitPct": 50, "totalHandles": 100000,
    "topProc": {"name": "svchost", "handles": 5000}, "nonpagedMB": 400,
    "procs": [{"name": "claude", "ageHours": 20}, {"name": "codex", "ageHours": 1}],
    "eventIds": [], "hooks": [],
}


@unittest.skipUnless(PWSH, "pwsh is not on PATH: install PowerShell 7 to run the box_health tests")
class BoxHealth(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)

    def run_script(self, fake=None, *extra):
        args = [PWSH, "-NoProfile", "-File", SCRIPT, *extra]
        if fake is not None:
            path = os.path.join(self.tmp, "fake.json")
            with open(path, "w") as f:
                json.dump(fake, f)
            args += ["-FakeJson", path]
        r = subprocess.run(args, capture_output=True, text=True, stdin=subprocess.DEVNULL)
        return r.returncode, r.stdout.strip().splitlines()

    def fixture(self, **over):
        d = copy.deepcopy(BASE)
        d.update(over)
        return d

    def test_all_pass(self):
        code, lines = self.run_script(self.fixture())
        self.assertEqual(code, 0, lines)
        self.assertEqual(lines[-1], "BOX OK")
        self.assertEqual(len([l for l in lines if l.startswith("PASS ")]), 7, lines)
        self.assertIn("claude=1", "\n".join(lines))  # claude is counted, not flagged

    def test_orphan_codex_warns_with_hint(self):
        code, lines = self.run_script(self.fixture(procs=[{"name": "codex", "ageHours": 30}]))
        self.assertEqual(code, 0, lines)
        self.assertTrue(any(l.startswith("WARN box-orphans") and "codex=1" in l for l in lines), lines)
        hint = [l for l in lines if l.startswith("HINT")]
        self.assertEqual(len(hint), 1, lines)
        self.assertIn("Get-Process codex", hint[0])
        self.assertEqual(lines[-1], "BOX WARN (1)")

    def test_claude_is_never_an_orphan(self):
        code, lines = self.run_script(self.fixture(procs=[{"name": "claude", "ageHours": 99}] * 20))
        self.assertEqual(lines[-1], "BOX OK", lines)

    def test_disk_below_min_fails(self):
        code, lines = self.run_script(self.fixture(diskFreeGB={"C:": 100, "D:": 2}))
        self.assertEqual(code, 1, lines)
        self.assertTrue(any(l.startswith("FAIL box-disk") for l in lines), lines)
        self.assertEqual(lines[-1], "BOX FAIL (1)")

    def test_hook_without_timeout_warns(self):
        code, lines = self.run_script(self.fixture(hooks=[{"plugin": "p", "event": "UserPromptSubmit"}]))
        self.assertTrue(any(l.startswith("WARN box-hooks p UserPromptSubmit") for l in lines), lines)

    def test_state_dir_reports_only_new(self):
        state = os.path.join(self.tmp, "run")
        _, first = self.run_script(self.fixture(nonpagedMB=3000), "-StateDir", state)
        self.assertIn("NEW box-pool", first)
        _, second = self.run_script(self.fixture(nonpagedMB=3000, eventIds=[4231]), "-StateDir", state)
        self.assertIn("NEW box-events", second)
        self.assertNotIn("NEW box-pool", second)
        with open(os.path.join(state, "log", "box-health.md")) as f:
            rows = f.read().splitlines()
        self.assertEqual(rows[0], "| When | Result | Warnings |")
        self.assertEqual(len(rows), 4, rows)  # header, separator, two runs
        #   a warning that clears for one tick and comes back is not new again (one flapped 3 times in a run)
        self.run_script(self.fixture(), "-StateDir", state)
        _, back = self.run_script(self.fixture(nonpagedMB=3000), "-StateDir", state)
        self.assertNotIn("NEW box-pool", back)

    def test_json(self):
        code, lines = self.run_script(self.fixture(nonpagedMB=3000), "-Json")
        data = json.loads("\n".join(lines))
        self.assertEqual(data["result"], "BOX WARN (1)")
        self.assertEqual([c["name"] for c in data["checks"]][0], "box-disk")
        self.assertEqual({"name", "status", "detail"}, set(data["checks"][0]))

    def test_live_smoke(self):
        code, lines = self.run_script()
        self.assertTrue(lines and lines[-1].startswith("BOX "), lines)


if __name__ == "__main__":
    result = unittest.main(exit=False, verbosity=0).result
    if result.wasSuccessful():
        print("BOX HEALTH TEST PASS")
    else:
        sys.exit(1)
