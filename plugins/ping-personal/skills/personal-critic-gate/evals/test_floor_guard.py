#!/usr/bin/env python3
"""Behavioral evals for lib/floor_guard.py: one test per signal and per exclusion.
Each test builds a throwaway git repo, commits `before`, edits to `after`, runs floor_guard --base HEAD.
Exit 0 = all pass; 1 = failures."""
import subprocess, sys, tempfile
from pathlib import Path

GUARD = Path(__file__).resolve().parent.parent / "lib" / "floor_guard.py"


def run(path, before, after, base="HEAD"):
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        g = lambda *a: subprocess.run(["git", "-C", str(d), "-c", "user.name=t", "-c", "user.email=t@t", *a], check=True, capture_output=True)
        g("init", "-q")
        f = d / path
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(before, encoding="utf-8", newline="\n")
        g("add", "-A"); g("commit", "-qm", "base")
        if after is None:
            f.unlink()
        else:
            f.write_text(after, encoding="utf-8", newline="\n")
        p = subprocess.run([sys.executable, str(GUARD), f"--base={base}"], cwd=d, capture_output=True, text=True, encoding="utf-8")
        assert not (d / "pwned.txt").exists(), "argument injection wrote a file"
        return p.returncode, p.stdout


def hit(path, before, after, sig):
    rc, out = run(path, before, after)
    assert rc == 1, f"expected exit 1, got {rc}: {out}"
    assert f"{path}:" in out and sig in out, out
    assert out.strip().splitlines()[-1] == "FLOOR FAIL 1", out


def miss(path, before, after):
    rc, out = run(path, before, after)
    assert rc == 0 and out.strip().splitlines()[-1] == "FLOOR PASS", out


def t_deleted_test():
    hit("test_a.py", "def test_x():\n    pass\n\ndef test_y():\n    z = 1\n", "def test_y():\n    z = 1\n", "deleted test")
def t_skip():
    hit("test_a.py", "def test_x():\n    z = 1\n", "@pytest.mark.skip\ndef test_x():\n    z = 1\n", "skip/xfail added")
def t_threshold():
    hit("eval.ps1", "if ($score -ge 90) { ok }\n", "if ($score -ge 70) { ok }\n", "threshold lowered")
def t_suppress():
    hit("a.py", "x = 1\n", "x = 1  # noqa\n", "lint/type suppression added")
def t_stub():
    hit("a.ts", "run();\n", "try { run(); } catch (e) {}\n", "empty catch or stub added")
def t_assert_removed():
    hit("test_a.py", "def test_x():\n    assert f() == 1\n    z = 2\n", "def test_x():\n    z = 2\n", "assertion removed")
def t_clean():
    miss("test_a.py", "def test_x():\n    assert f() == 1\n", "def test_x():\n    assert f() == 1\n    assert g() == 2\n")
def t_raised_threshold_ok():
    miss("eval.ps1", "if ($score -ge 70) { ok }\n", "if ($score -ge 90) { ok }\n")
def t_skip_markdown():
    miss("notes.md", "x\n", "x\n@pytest.mark.skip and noqa and ts-ignore in prose\n")
GUARD_DIR = "plugins/ping-personal/skills/personal-critic-gate/"
def t_skip_own_source():
    miss(GUARD_DIR + "lib/floor_guard.py", "x = 1\n", "x = 1  # noqa\n")
def t_skip_own_test():
    miss(GUARD_DIR + "evals/test_floor_guard.py", "def test_x():\n    assert 1\n", "")
def t_same_name_elsewhere_not_exempt():
    hit("other/lib/floor_guard.py", "x = 1\n", "x = 1  # noqa\n", "lint/type suppression added")
def t_skip_fixtures():
    miss("evals/fixtures/case.py", "x = 1\n", "x = 1  # noqa\n")
def t_skip_tests_fixtures():
    miss("tests/fixtures/case.py", "x = 1\n", "x = 1  # noqa\n")
def t_fixtures_elsewhere_not_exempt():
    hit("src/fixtures/case.py", "x = 1\n", "x = 1  # noqa\n", "lint/type suppression added")
def t_base_dash_rejected():
    rc, out = run("a.py", "x = 1\n", "x = 2\n", base="--output=pwned.txt")
    assert rc == 1 and out.strip().splitlines()[-1].startswith("FLOOR FAIL"), out
def t_base_unresolvable_fails_closed():
    rc, out = run("a.py", "x = 1\n", "x = 2\n", base="no-such-ref")
    assert rc == 1 and out.strip().splitlines()[-1].startswith("FLOOR FAIL"), out
def t_deleted_test_file():
    hit("test_a.py", "x = 1\n", None, "deleted test")
def t_quoted_path():
    hit("t\u00e9st_a.py", "x = 1\n", "x = 1  # noqa\n", "lint/type suppression added")
def t_path_with_space():
    hit("test a.py", "x = 1\n", "x = 1  # noqa\n", "lint/type suppression added")
def t_unresolvable_path_fails():
    import importlib.util
    spec = importlib.util.spec_from_file_location("fg", GUARD); fg = importlib.util.module_from_spec(spec); spec.loader.exec_module(fg)
    try:
        fg.scan("diff --git garbage\n--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n+x = 1  # noqa\n")
    except ValueError:
        return
    raise AssertionError("scan did not reject a hunk with no resolvable path")

def t_select_object_skip_not_a_hit():
    miss("eval.ps1", "$a = 1\n", "$a = 1\n$b = $x | Select-Object -Skip 2\n")
def t_pester_skip_is_a_hit():
    hit("a.Tests.ps1", "$a = 1\n", "$a = 1\nIt 'x' -Skip { 1 }\n", "skip/xfail added")
def t_noqa_e402_not_a_hit():
    miss("a.py", "x = 1\n", "import b  # noqa: E402\n")
def t_bare_noqa_still_a_hit():
    hit("a.py", "x = 1\n", "import b  # noqa" + chr(10), "lint/type suppression added")
def t_noqa_other_code_still_a_hit():
    hit("a.py", "x = 1\n", "import b  # noqa: F401\n", "lint/type suppression added")


TESTS = [v for k, v in sorted(globals().items()) if k.startswith("t_")]
bad = 0
for t in TESTS:
    try:
        t(); print(f"PASS {t.__name__}")
    except Exception as e:
        bad += 1; print(f"FAIL {t.__name__}: {e}", file=sys.stderr)
print(f"\nfloor_guard behavioral: {len(TESTS)-bad} passed, {bad} failed")
sys.exit(1 if bad else 0)
