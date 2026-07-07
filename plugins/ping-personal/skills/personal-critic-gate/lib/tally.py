"""
tally.py -- 5-seat panel tally for personal-critic-gate v0.9.0.

Takes 5 seat votes (JSON lines on stdin, or --votes arg), outputs verdict
PASS/FIX/BLOCK by majority 3-of-5.

Usage:
    echo '{"VOTE":"PASS"}' | python tally.py  # stdin JSON lines, one per seat
    python tally.py --votes '{"VOTE":"PASS"}' '{"VOTE":"FIX"}' '{"VOTE":"FIX"}' '{"VOTE":"PASS"}' '{"VOTE":"FIX"}'
    python tally.py --stay-paused  # always PAUSED regardless of votes

Tally rules:
    - BLOCK majority (3+) -> BLOCK
    - FIX majority (3+)   -> FIX
    - PASS majority (3+)  -> PASS
    - No majority (no value reaches 3) -> FIX (safe default)
    - BLOCK always beats FIX beats PASS (priority order) when tied counts.
    - ABSTAIN votes are NOT counted toward any outcome and reduce the
      effective panel size for majority purposes.
    - If --stay-paused flag is set: verdict = PAUSED regardless of vote counts.

Tie/insufficient handling:
    - A BLOCK from any single voter does NOT veto alone; 3-of-5 majority is
      required for BLOCK to win.
    - If fewer than 3 valid (non-ABSTAIN) votes are cast, verdict = FIX
      (insufficient panel, safe default).
    - If the highest vote count is 2 (no majority), verdict = FIX.
    - "Tie" between BLOCK and FIX at 2-2 -> FIX is chosen (BLOCK needs 3).
    - "Tie" between BLOCK and PASS at 2-2 -> BLOCK wins (priority: BLOCK > FIX > PASS).
      Actually in 5-seat, 2-2 means one ABSTAIN; revert to FIX safe default
      because neither reached 3.

Priority in absence of strict majority: BLOCK > FIX > PASS.
Rationale: the gate is a safety device; when uncertain, pick the more cautious verdict.

Exits 0 and prints verdict JSON.
Exits 1 on input error.
"""

import json
import sys
import argparse

PRIORITY = ["BLOCK", "FIX", "PASS"]
VALID_VOTES = {"PASS", "FIX", "BLOCK", "ABSTAIN"}


def tally_votes(vote_objects: list[dict], stay_paused: bool = False) -> dict:
    """
    Compute the panel verdict from a list of vote dicts.
    Each dict must have a "VOTE" key.
    Returns a result dict with keys: verdict, counts, notes.
    """
    if stay_paused:
        return {
            "verdict": "PAUSED",
            "counts": {},
            "notes": "stay-paused flag forced PAUSED verdict",
        }

    counts = {"PASS": 0, "FIX": 0, "BLOCK": 0, "ABSTAIN": 0, "INVALID": 0}
    notes = []

    for i, obj in enumerate(vote_objects):
        seat = i + 1
        vote_raw = obj.get("VOTE", "")
        vote_val = str(vote_raw).strip().upper() if vote_raw else ""
        if vote_val == "ESCALATE":
            raise ValueError(
                f"seat {seat}: ESCALATE is a fast-lane-only vote and MUST NOT reach "
                "the 5-seat tally. This is a programming error."
            )
        if vote_val in VALID_VOTES:
            counts[vote_val] += 1
        else:
            counts["INVALID"] += 1
            notes.append(f"seat {seat}: invalid VOTE value '{vote_raw}' -- counted as abstain")
            counts["ABSTAIN"] += 1

    effective_votes = counts["PASS"] + counts["FIX"] + counts["BLOCK"]

    if effective_votes < 3:
        notes.append(
            f"insufficient panel: only {effective_votes} non-abstain votes "
            "(need 3); defaulting to FIX (safe default)"
        )
        verdict = "FIX"
    else:
        # Check majority in priority order (BLOCK beats FIX beats PASS).
        verdict = None
        for candidate in PRIORITY:
            if counts[candidate] >= 3:
                verdict = candidate
                break
        if verdict is None:
            # No candidate reached 3 -- no majority.
            notes.append(
                "no majority (no value reached 3-of-5); defaulting to FIX (safe default)"
            )
            verdict = "FIX"

    return {
        "verdict": verdict,
        "counts": {k: v for k, v in counts.items() if v > 0},
        "effective_votes": effective_votes,
        "notes": notes,
    }


def parse_vote_line(line: str, seat_num: int) -> dict:
    """Parse a single JSON line representing one vote."""
    line = line.strip()
    if not line:
        return {"VOTE": "ABSTAIN", "_note": f"seat {seat_num}: empty line treated as ABSTAIN"}
    try:
        obj = json.loads(line)
        if not isinstance(obj, dict):
            raise ValueError("not a JSON object")
        return obj
    except (json.JSONDecodeError, ValueError) as exc:
        return {
            "VOTE": "ABSTAIN",
            "_note": f"seat {seat_num}: parse error '{exc}' -- treated as ABSTAIN",
        }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Tally 5 seat votes for the critic-gate panel."
    )
    parser.add_argument(
        "--votes",
        nargs="*",
        help="Vote JSON objects as positional args (one per seat). "
        "If omitted, reads JSON lines from stdin.",
    )
    parser.add_argument(
        "--stay-paused",
        action="store_true",
        help="Force PAUSED verdict regardless of votes (Stay-Paused List hit).",
    )
    args = parser.parse_args()

    vote_objects = []

    if args.votes is not None:
        for i, raw in enumerate(args.votes):
            vote_objects.append(parse_vote_line(raw, i + 1))
    else:
        lines = sys.stdin.read().strip().split("\n")
        for i, line in enumerate(lines):
            vote_objects.append(parse_vote_line(line, i + 1))

    if len(vote_objects) == 0:
        print("ERROR: no votes provided", file=sys.stderr)
        return 1

    result = tally_votes(vote_objects, stay_paused=args.stay_paused)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
