#!/usr/bin/env python3
"""
Behavioral evals for vote_parser.py -- Phase 4 goal-skill-v2 (B4).

Tests edge cases:
  B4a -- nested JSON braces inside "why" string
  B4b -- escaped quotes inside a string value
  B4c -- trailing prose AFTER the final vote object (last valid wins)
  B4d -- stray earlier vote-shaped object (last valid must win)
  B4e -- no vote at all -> nonzero exit
  B4f -- invalid VOTE value -> nonzero exit
  B4g -- legacy alias SHIP -> normalised to PASS
  B4h -- legacy alias ABORT -> normalised to BLOCK

Exit 0 = all pass; 1 = failures.
"""

import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
LIB_DIR = SKILL_DIR / "lib"
sys.path.insert(0, str(LIB_DIR))

from vote_parser import find_last_valid_vote, extract_balanced_spans, validate_vote

fails = []


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def test_b4a_nested_braces_in_why():
    """B4a: nested JSON braces inside 'why' string must not confuse the parser."""
    text = (
        'Some preamble.\n'
        '{"VOTE": "PASS", "why": "score {excellent: {depth: 5}} meets bar"}\n'
        'End of review.'
    )
    result = find_last_valid_vote(text)
    _assert(result is not None, "B4a: parser returned None on nested braces in why string")
    _assert(result["VOTE"] == "PASS", f"B4a: expected PASS; got {result.get('VOTE')}")
    _assert("excellent" in result.get("why", ""),
            "B4a: 'why' field was mangled by nested-brace scan")


def test_b4b_escaped_quotes():
    """B4b: escaped double-quotes inside a string value must not end the string early."""
    text = r'{"VOTE": "FIX", "why": "use \"strict\" mode"}'
    result = find_last_valid_vote(text)
    _assert(result is not None, "B4b: parser returned None on escaped quotes")
    _assert(result["VOTE"] == "FIX", f"B4b: expected FIX; got {result.get('VOTE')}")


def test_b4c_trailing_prose_after_vote():
    """B4c: trailing prose after the final vote object is ignored; last vote wins."""
    text = (
        '{"VOTE": "PASS", "why": "all green"}\n'
        'No further issues to raise. Recommend shipping.'
    )
    result = find_last_valid_vote(text)
    _assert(result is not None, "B4c: parser returned None with trailing prose")
    _assert(result["VOTE"] == "PASS", f"B4c: expected PASS; got {result.get('VOTE')}")


def test_b4d_stray_earlier_vote_shape():
    """B4d: stray earlier vote-shaped object; the LAST valid vote must win."""
    text = (
        '{"VOTE": "BLOCK", "why": "early concern"}\n'
        'After further review:\n'
        '{"VOTE": "FIX", "why": "minor nit only"}\n'
    )
    result = find_last_valid_vote(text)
    _assert(result is not None, "B4d: parser returned None")
    _assert(result["VOTE"] == "FIX",
            f"B4d: last valid vote (FIX) did not win; got {result.get('VOTE')}")


def test_b4e_no_vote():
    """B4e: no vote object at all -> returns None."""
    text = "This is just some reviewer commentary with no vote JSON."
    result = find_last_valid_vote(text)
    _assert(result is None, "B4e: expected None when no vote present; got a result")


def test_b4f_invalid_vote_value():
    """B4f: VOTE value not in allowed set -> find_last_valid_vote returns None."""
    text = '{"VOTE": "MAYBE", "why": "unsure"}'
    result = find_last_valid_vote(text)
    _assert(result is None,
            f"B4f: expected None for invalid VOTE 'MAYBE'; got {result}")


def test_b4g_legacy_ship():
    """B4g: SHIP is a legacy alias -> normalised to PASS."""
    text = '{"VOTE": "SHIP", "why": "lgtm"}'
    result = find_last_valid_vote(text)
    _assert(result is not None, "B4g: parser returned None for SHIP alias")
    _assert(result["VOTE"] == "PASS",
            f"B4g: SHIP not normalised to PASS; got {result.get('VOTE')}")


def test_b4h_legacy_abort():
    """B4h: ABORT is a legacy alias -> normalised to BLOCK."""
    text = '{"VOTE": "ABORT", "why": "critical issue"}'
    result = find_last_valid_vote(text)
    _assert(result is not None, "B4h: parser returned None for ABORT alias")
    _assert(result["VOTE"] == "BLOCK",
            f"B4h: ABORT not normalised to BLOCK; got {result.get('VOTE')}")


def test_escalate_rejected_by_default():
    ok, _ = validate_vote("ESCALATE")
    _assert(ok is False, "ESCALATE should be rejected when fast_lane=False (default)")


def test_escalate_accepted_in_fast_lane():
    ok, norm = validate_vote("ESCALATE", fast_lane=True)
    _assert(ok is True and norm == "ESCALATE",
            f"ESCALATE should be valid in fast_lane mode; got ok={ok}, norm={norm}")


def test_find_last_vote_fast_lane_escalate():
    text = 'review text...\n{"VOTE":"ESCALATE","why":"risky"}'
    obj = find_last_valid_vote(text, fast_lane=True)
    _assert(obj is not None and obj["VOTE"] == "ESCALATE",
            f"fast_lane ESCALATE not extracted; got {obj}")


def test_find_last_vote_rejects_escalate_without_flag():
    text = '{"VOTE":"ESCALATE","why":"risky"}'
    _assert(find_last_valid_vote(text) is None,
            "ESCALATE without fast_lane=True should return None")


TESTS = [
    ("B4a_nested_braces_in_why", test_b4a_nested_braces_in_why),
    ("B4b_escaped_quotes", test_b4b_escaped_quotes),
    ("B4c_trailing_prose", test_b4c_trailing_prose_after_vote),
    ("B4d_stray_earlier_vote", test_b4d_stray_earlier_vote_shape),
    ("B4e_no_vote", test_b4e_no_vote),
    ("B4f_invalid_vote_value", test_b4f_invalid_vote_value),
    ("B4g_legacy_ship", test_b4g_legacy_ship),
    ("B4h_legacy_abort", test_b4h_legacy_abort),
    ("ESCALATE_rejected_by_default", test_escalate_rejected_by_default),
    ("ESCALATE_accepted_in_fast_lane", test_escalate_accepted_in_fast_lane),
    ("find_last_vote_fast_lane_escalate", test_find_last_vote_fast_lane_escalate),
    ("find_last_vote_rejects_escalate_without_flag", test_find_last_vote_rejects_escalate_without_flag),
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

print(f"\nvote_parser behavioral: {pass_count} passed, {fail_count} failed")
sys.exit(0 if fail_count == 0 else 1)
