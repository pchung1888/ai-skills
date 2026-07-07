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
