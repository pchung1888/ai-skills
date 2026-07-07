"""
vote_parser.py -- quote-aware balanced-scan extraction of the LAST valid vote JSON.

Usage:
    python vote_parser.py < textfile
    python vote_parser.py --text "...reviewer output..."
    echo "..." | python vote_parser.py

Exits 0 on success, prints extracted JSON to stdout.
Exits 1 on parse failure (no valid vote found).

Valid VOTE values (diff/plan artifacts): PASS, FIX, BLOCK
  (legacy aliases SHIP -> PASS, ABORT -> BLOCK are accepted and normalised)
Valid VOTE values (planning-time artifacts): any OPTIONS label or ABSTAIN

Design: implements the "quote-aware BALANCED {..} scan" specified in
personal-critic-gate SKILL.md v0.9.0. Walk the text tracking brace depth AND
string state; skip braces inside double-quoted string values, and track
backslash escapes so an escaped quote (\\") does not prematurely end a string.
Collect every top-level balanced {..} span, then take the LAST span that
parses as JSON and carries a top-level "VOTE" key whose value is in the
allowed set.
"""

import json
import sys
import argparse

# Canonical VOTE values for diff/plan artifacts.
CANONICAL_VOTES = {"PASS", "FIX", "BLOCK"}

# Legacy aliases accepted for backward compatibility.
LEGACY_ALIAS = {
    "SHIP": "PASS",
    "ABORT": "BLOCK",
}

# ABSTAIN is accepted as a special value for planning-time artifacts.
SPECIAL_VOTES = {"ABSTAIN"}

# ESCALATE is FAST-LANE-ONLY -- a single reviewer requesting the full panel.
# NEVER valid in the 5-seat tally (which stays PASS/FIX/BLOCK).
# Raises ValueError if it reaches tally_votes().
FAST_LANE_VOTES = {"ESCALATE"}


def extract_balanced_spans(text: str) -> list[str]:
    """
    Return every top-level balanced {..} span in text.
    Quote-aware: braces inside double-quoted strings are skipped.
    Backslash-escape aware: \\\" does not end a string.
    """
    spans = []
    depth = 0
    in_string = False
    escaped = False
    start = -1

    i = 0
    while i < len(text):
        ch = text[i]

        if escaped:
            escaped = False
            i += 1
            continue

        if ch == "\\" and in_string:
            escaped = True
            i += 1
            continue

        if ch == '"':
            in_string = not in_string
            i += 1
            continue

        if not in_string:
            if ch == "{":
                if depth == 0:
                    start = i
                depth += 1
            elif ch == "}":
                if depth > 0:
                    depth -= 1
                    if depth == 0 and start != -1:
                        spans.append(text[start : i + 1])
                        start = -1
        i += 1

    return spans


def validate_vote(vote_value: str, fast_lane: bool = False) -> tuple[bool, str]:
    """
    Validate and normalise a VOTE value.
    Returns (is_valid, normalised_value).
    Legacy aliases SHIP/ABORT are mapped to PASS/BLOCK.
    ABSTAIN is accepted as-is.
    ESCALATE is accepted only when fast_lane=True; rejected otherwise.
    Custom OPTIONS labels (for planning-time) are accepted as-is when
    allow_custom=True -- callers that know they are in planning-time mode
    should pass allow_custom=True.
    """
    if not vote_value or not isinstance(vote_value, str):
        return False, ""
    v = vote_value.strip().upper()
    if v in CANONICAL_VOTES:
        return True, v
    if v in LEGACY_ALIAS:
        return True, LEGACY_ALIAS[v]
    if v in SPECIAL_VOTES:
        return True, v
    if fast_lane and v in FAST_LANE_VOTES:
        return True, v
    # Unknown value -- fail strict validation.
    # Callers handling planning-time OPTIONS labels may post-process themselves.
    return False, v


def find_last_valid_vote(
    text: str,
    allow_custom_labels: bool = False,
    fast_lane: bool = False,
) -> dict | None:
    """
    Extract the LAST balanced {..} span in text that:
      1. Parses as valid JSON.
      2. Has a top-level "VOTE" key.
      3. Has a VOTE value in the allowed set (or allow_custom_labels=True).

    When fast_lane=True, ESCALATE is also accepted as a valid VOTE value.
    Returns the parsed dict with VOTE normalised, or None on failure.
    """
    spans = extract_balanced_spans(text)
    # Walk in reverse -- last valid span wins.
    for span in reversed(spans):
        try:
            obj = json.loads(span)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        vote_raw = obj.get("VOTE")
        if vote_raw is None:
            continue
        is_valid, normalised = validate_vote(str(vote_raw), fast_lane=fast_lane)
        if is_valid:
            obj["VOTE"] = normalised
            return obj
        if allow_custom_labels and vote_raw:
            # Accept as-is for planning-time OPTIONS labels.
            return obj
    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract the last valid VOTE JSON from reviewer text."
    )
    parser.add_argument(
        "--text",
        help="Reviewer text inline (alternative to stdin)",
        default=None,
    )
    parser.add_argument(
        "--allow-custom-labels",
        action="store_true",
        help="Accept non-canonical VOTE values (planning-time OPTIONS labels)",
    )
    parser.add_argument(
        "--fast-lane",
        action="store_true",
        help="Enable fast-lane mode: accept ESCALATE as a valid VOTE value",
    )
    args = parser.parse_args()

    if args.text is not None:
        text = args.text
    else:
        text = sys.stdin.read()

    result = find_last_valid_vote(
        text,
        allow_custom_labels=args.allow_custom_labels,
        fast_lane=args.fast_lane,
    )
    if result is None:
        print("ERROR: no valid vote JSON found in input", file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
