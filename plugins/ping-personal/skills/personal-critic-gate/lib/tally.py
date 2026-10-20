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

Exits 0 and prints one verdict JSON object; its "reviewed" field reads
"Reviewed: <full sha>" (--sha, resolved by git) or "Reviewed: n/a (uncommitted)".
--final makes --sha mandatory. --expect-head (needs --sha; --repo <path>, default cwd) adds
"stale": true/false (--sha vs HEAD of that repo) and exits 2 when stale. Exits 1 if --sha does not resolve or starts with "-".
Exits 1 on input error.
"""

import json
import sys
import argparse
import subprocess

PRIORITY = ["BLOCK", "FIX", "PASS"]
VALID_VOTES = {"PASS", "FIX", "BLOCK", "ABSTAIN"}


def tally_votes(vote_objects: list[dict], stay_paused: bool = False, sha: str = "") -> dict:
    """
    Compute the panel verdict from a list of vote dicts.
    Each dict must have a "VOTE" key.
    Returns a result dict with keys: verdict, counts, notes.
    """
    reviewed = f"Reviewed: {sha}" if sha else "Reviewed: n/a (uncommitted)"
    if stay_paused:
        return {
            "verdict": "PAUSED",
            "reviewed": reviewed,
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
        "reviewed": reviewed,
        "counts": {k: v for k, v in counts.items() if v > 0},
        "effective_votes": effective_votes,
        "notes": notes,
    }


def resolve_sha(sha: str, repo: str = None) -> str:
    """Return the full commit sha for `sha`, or raise ValueError. Runs git in `repo` (default: cwd)."""
    if sha.startswith("-"):
        raise ValueError(f"--sha must not start with '-': {sha!r}")
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--verify", "--end-of-options", sha + "^{commit}"],
            capture_output=True, text=True, timeout=30, cwd=repo,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError(f"cannot run git to resolve --sha: {exc}")
    full = out.stdout.strip()
    if out.returncode != 0 or len(full) < 40:
        raise ValueError(f"--sha does not resolve to a commit here: {sha!r}")
    return full


def head_sha(repo: str = None) -> str:
    """Return the full sha of HEAD in `repo` (default: cwd), or raise ValueError."""
    return resolve_sha("HEAD", repo)


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
    parser.add_argument(
        "--sha",
        default="",
        help="Commit the panel reviewed; printed as 'Reviewed: <sha>'. "
        "Omit for planning-time blocks (prints 'Reviewed: n/a (uncommitted)').",
    )
    parser.add_argument(
        "--final",
        action="store_true",
        help="Final review: --sha is required (an empty sha is an error).",
    )
    parser.add_argument(
        "--expect-head",
        action="store_true",
        help="Requires --sha. Adds \"stale\": true when --sha is not HEAD of --repo; exit 2 if stale.",
    )
    parser.add_argument(
        "--repo",
        default=None,
        help="Repo path for --sha and --expect-head (default: current directory).",
    )
    args = parser.parse_args()

    stale = None
    try:
        if args.expect_head and not args.sha:
            raise ValueError("--expect-head needs --sha <commit>")
        if args.sha:
            args.sha = resolve_sha(args.sha, args.repo)
            if args.expect_head:
                stale = args.sha != head_sha(args.repo)
        elif args.final:
            raise ValueError("a final review needs --sha <commit>")
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

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

    result = tally_votes(vote_objects, stay_paused=args.stay_paused, sha=args.sha)
    if stale is not None:
        result["stale"] = stale
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 2 if stale else 0


if __name__ == "__main__":
    sys.exit(main())
