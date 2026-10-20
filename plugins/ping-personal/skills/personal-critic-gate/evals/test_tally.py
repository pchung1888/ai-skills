#!/usr/bin/env python3
"""
Behavioral evals for tally.py -- Phase 4 goal-skill-v2 (B5).

Tests:
  B5a -- 3-of-5 FIX wins (3 FIX 2 PASS -> FIX)
  B5b -- 4 PASS 1 BLOCK -> PASS wins (4 >= 3)
  B5c -- BLOCK majority (3+ BLOCK) -> BLOCK
  B5d -- no majority (2-2-1) -> FIX safe default
  B5e -- --stay-paused -> PAUSED regardless of votes
  B5f -- fewer than 3 effective votes -> FIX (insufficient panel)
  B5g -- 5 votes including iris substitution (normal 5-seat case)
  B5h -- INVALID vote value counted as ABSTAIN, reduces effective pool

Exit 0 = all pass; 1 = failures.
"""

import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
LIB_DIR = SKILL_DIR / "lib"
sys.path.insert(0, str(LIB_DIR))

from tally import tally_votes

fails = []


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _v(vote: str) -> dict:
    return {"VOTE": vote}


def test_b5a_fix_majority():
    """B5a: 3 FIX 2 PASS -> FIX wins."""
    votes = [_v("FIX"), _v("FIX"), _v("FIX"), _v("PASS"), _v("PASS")]
    result = tally_votes(votes)
    _assert(result["verdict"] == "FIX", f"B5a: expected FIX; got {result['verdict']}")


def test_b5b_pass_majority():
    """B5b: 4 PASS 1 BLOCK -> PASS (4 >= 3 majority)."""
    votes = [_v("PASS"), _v("PASS"), _v("PASS"), _v("PASS"), _v("BLOCK")]
    result = tally_votes(votes)
    _assert(result["verdict"] == "PASS", f"B5b: expected PASS; got {result['verdict']}")


def test_b5c_block_majority():
    """B5c: 3 BLOCK -> BLOCK wins."""
    votes = [_v("BLOCK"), _v("BLOCK"), _v("BLOCK"), _v("PASS"), _v("FIX")]
    result = tally_votes(votes)
    _assert(result["verdict"] == "BLOCK", f"B5c: expected BLOCK; got {result['verdict']}")


def test_b5d_no_majority():
    """B5d: no majority (2 FIX, 2 PASS, 1 BLOCK) -> FIX safe default."""
    votes = [_v("FIX"), _v("FIX"), _v("PASS"), _v("PASS"), _v("BLOCK")]
    result = tally_votes(votes)
    _assert(result["verdict"] == "FIX",
            f"B5d: expected FIX (no-majority safe default); got {result['verdict']}")


def test_b5e_stay_paused():
    """B5e: --stay-paused flag -> PAUSED regardless of votes."""
    votes = [_v("PASS"), _v("PASS"), _v("PASS"), _v("PASS"), _v("PASS")]
    result = tally_votes(votes, stay_paused=True)
    _assert(result["verdict"] == "PAUSED",
            f"B5e: expected PAUSED with stay_paused=True; got {result['verdict']}")


def test_b5f_insufficient_panel():
    """B5f: fewer than 3 effective (non-abstain) votes -> FIX (insufficient panel)."""
    votes = [_v("PASS"), _v("ABSTAIN"), _v("ABSTAIN"), _v("ABSTAIN"), _v("ABSTAIN")]
    result = tally_votes(votes)
    _assert(result["verdict"] == "FIX",
            f"B5f: expected FIX (insufficient panel); got {result['verdict']}")
    notes_text = " ".join(result.get("notes", []))
    _assert("insufficient" in notes_text.lower(),
            "B5f: expected 'insufficient' in notes")


def test_b5g_five_seat_normal():
    """B5g: normal 5-seat case including an iris seat (Seat 5)."""
    # Simulate ms-mario, amanda, rhea, vex/maggie (seat4), iris (seat5)
    votes = [_v("PASS"), _v("PASS"), _v("FIX"), _v("PASS"), _v("PASS")]
    result = tally_votes(votes)
    _assert(result["verdict"] == "PASS",
            f"B5g: expected PASS (4 PASS, 1 FIX); got {result['verdict']}")
    _assert(result.get("effective_votes") == 5,
            f"B5g: expected 5 effective votes; got {result.get('effective_votes')}")


def test_b5h_invalid_counted_as_abstain():
    """B5h: invalid VOTE value counted as ABSTAIN, reducing effective pool."""
    # 2 PASS, 2 BLOCK, 1 invalid -> effective=4, no majority at 3; FIX default
    votes = [_v("PASS"), _v("PASS"), _v("BLOCK"), _v("BLOCK"), {"VOTE": "JUNK"}]
    result = tally_votes(votes)
    # JUNK -> ABSTAIN -> effective=4. PASS=2, BLOCK=2. No majority. FIX.
    _assert(result["verdict"] == "FIX",
            f"B5h: expected FIX (invalid->abstain, no majority); got {result['verdict']}")
    notes_text = " ".join(result.get("notes", []))
    _assert("invalid" in notes_text.lower() or "abstain" in notes_text.lower(),
            "B5h: expected note about invalid vote treated as abstain")


def test_escalate_raises_in_tally():
    """ESCALATE must never silently become ABSTAIN in the 5-seat panel."""
    raised = False
    try:
        tally_votes([{"VOTE": "ESCALATE"}])
    except (ValueError, SystemExit):
        raised = True
    _assert(raised, "ESCALATE must raise ValueError in the 5-seat tally, not silently become ABSTAIN")


def _run_tally(extra, votes):
    import subprocess
    return subprocess.run([sys.executable, str(LIB_DIR / "tally.py")] + extra + ["--votes"] + votes,
                          capture_output=True, text=True, cwd=str(SKILL_DIR))


def _head():
    import subprocess
    return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                          cwd=str(SKILL_DIR)).stdout.strip()


def test_reviewed_sha():
    """--sha resolves to the full sha; PASS, FIX and PAUSED all carry it; stdout is one JSON object."""
    import json
    head = _head()
    pv = ['{"VOTE":"PASS"}'] * 5
    fv = ['{"VOTE":"FIX"}'] * 3 + ['{"VOTE":"PASS"}'] * 2
    for want, extra, votes in [("PASS", [], pv), ("FIX", [], fv), ("PAUSED", ["--stay-paused"], pv)]:
        r = _run_tally(["--sha", head[:10], "--final"] + extra, votes)
        _assert(r.returncode == 0, f"{want}: exit {r.returncode}: {r.stderr}")
        out = json.loads(r.stdout)
        _assert(out["verdict"] == want, f"expected {want}; got {out['verdict']}")
        _assert(out["reviewed"] == f"Reviewed: {head}", f"{want}: reviewed field {out['reviewed']}")
    _assert(tally_votes([_v("PASS")] * 5, sha="x")["reviewed"] == "Reviewed: x", "dict field")


def test_reviewed_sha_refusals():
    """Bad, option-like or empty (final) sha is an error; planning-time with no sha prints n/a."""
    import json
    pv = ['{"VOTE":"PASS"}'] * 5
    for bad in (["--sha", "deadbeefnotacommit"], ["--sha=-x"], ["--final"], ["--final", "--sha", ""]):
        r = _run_tally(bad, pv)
        _assert(r.returncode == 1 and r.stdout == "", f"{bad}: expected exit 1, empty stdout; got {r.returncode}")
    r = _run_tally([], pv)
    _assert(json.loads(r.stdout)["reviewed"] == "Reviewed: n/a (uncommitted)", "missing n/a")


def test_expect_head():
    """--expect-head: same repo fresh, same repo stale, a second repo, and no --sha is refused."""
    import json, subprocess, tempfile
    pv = ['{"VOTE":"PASS"}'] * 5
    head = _head()
    r = _run_tally(["--sha", head, "--final", "--expect-head"], pv)
    _assert(r.returncode == 0 and json.loads(r.stdout)["stale"] is False, f"fresh: {r.returncode} {r.stdout}")
    with tempfile.TemporaryDirectory() as d:
        def git(*a):
            return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a],
                                  capture_output=True, text=True, cwd=d).stdout.strip()
        git("init", "-q")
        git("commit", "-q", "--allow-empty", "-m", "one")
        old = git("rev-parse", "HEAD")
        r = _run_tally(["--sha", old, "--expect-head", "--repo", d], pv)
        _assert(r.returncode == 0 and json.loads(r.stdout)["stale"] is False, f"repo2 fresh: {r.returncode}")
        git("commit", "-q", "--allow-empty", "-m", "two")
        r = _run_tally(["--sha", old, "--expect-head", "--repo", d], pv)
        _assert(r.returncode == 2 and json.loads(r.stdout)["stale"] is True, f"stale: {r.returncode} {r.stdout}")
    r = _run_tally(["--expect-head"], pv)
    _assert(r.returncode == 1 and r.stdout == "", f"no --sha: {r.returncode}")


TESTS = [
    ("B5a_fix_majority", test_b5a_fix_majority),
    ("B5b_pass_majority", test_b5b_pass_majority),
    ("B5c_block_majority", test_b5c_block_majority),
    ("B5d_no_majority", test_b5d_no_majority),
    ("B5e_stay_paused", test_b5e_stay_paused),
    ("B5f_insufficient_panel", test_b5f_insufficient_panel),
    ("B5g_five_seat_normal", test_b5g_five_seat_normal),
    ("B5h_invalid_counted_as_abstain", test_b5h_invalid_counted_as_abstain),
    ("ESCALATE_raises_in_tally", test_escalate_raises_in_tally),
    ("reviewed_sha", test_reviewed_sha),
    ("reviewed_sha_refusals", test_reviewed_sha_refusals),
    ("expect_head", test_expect_head),
]

pass_count = 0
fail_count = 0
for name, fn in TESTS:
    try:
        fn()
        print(f"PASS {name}")
        pass_count += 1
    except Exception as exc:
        print(f"FAIL {name}: {exc}", file=sys.stderr)
        fail_count += 1

print(f"\ntally behavioral: {pass_count} passed, {fail_count} failed")
sys.exit(0 if fail_count == 0 else 1)
