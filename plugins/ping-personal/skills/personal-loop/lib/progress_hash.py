#!/usr/bin/env python3
"""progress_hash.py -- tick-signature hashing + no-progress detection.

The signature folds in an optional progress_marker (e.g. goals_done or a count
of in-scope artifacts present) so that a campaign tick which makes REAL progress
gets a distinct signature even when its commit_sha is unchanged and its
accept_output text repeats. Without it, two 'Not done: 2 of 5' research ticks
collapse to one signature and the no-progress detector kills a live campaign.
"""
import argparse, hashlib, sys


def tick_signature(commit_sha: str, accept_output: str, error_text: str,
                   progress_marker: str = "") -> str:
    h = hashlib.sha256()
    for part in (commit_sha or "", accept_output or "", error_text or "",
                 str(progress_marker or "")):
        h.update(part.strip().encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()[:16]


def is_no_progress(signatures: list[str], k: int) -> bool:
    if k < 1 or len(signatures) < k:
        return False
    return len(set(signatures[-k:])) == 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sha", default="")
    ap.add_argument("--accept", default="")
    ap.add_argument("--error", default="")
    ap.add_argument("--progress", default="")
    a = ap.parse_args()
    print(tick_signature(a.sha, a.accept, a.error, a.progress))
    return 0


if __name__ == "__main__":
    sys.exit(main())
