"""Unit test for lib/collision_check.py: ranking, skip rule, exit 0."""
import subprocess
import sys
import tempfile
from pathlib import Path

LIB = Path(__file__).resolve().parents[1] / "lib" / "collision_check.py"
sys.path.insert(0, str(LIB.parent))
import collision_check as cc  # noqa: E402


def mk(root, name, desc, extra=""):
    d = Path(root) / name
    d.mkdir()
    (d / "SKILL.md").write_text(f"---\nname: {name}\n{extra}description: {desc}\n---\nbody\n", encoding="utf-8")


with tempfile.TemporaryDirectory() as t:
    mk(t, "a", "summarize youtube video captions with timestamps")
    mk(t, "b", "summarize youtube video captions quickly")
    mk(t, "c", "deploy database migration scripts safely")
    mk(t, "hidden", "summarize youtube video captions with timestamps", "disable-model-invocation: true\n")
    found, skipped = cc.load(t)
    assert skipped == 1 and "hidden" not in found, (skipped, list(found))
    r = cc.rank(found)
    assert (r[0][1], r[0][2]) == ("a", "b"), r
    assert r[0][0] > r[1][0] >= r[2][0], r
    p = subprocess.run([sys.executable, str(LIB), "--skills-dir", t, "--top", "1"], capture_output=True, text=True)
    assert p.returncode == 0 and "a  <->  b" in p.stdout and "1 skipped" in p.stdout, p.stdout
print("test_collision_check PASS")
