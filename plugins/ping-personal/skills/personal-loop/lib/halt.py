#!/usr/bin/env python3
"""halt.py -- safety-halt circuit-breaker primitives for unattended loops.

A documented safety mechanism that is not backed by real code must never be
cited as present. This module makes the secrets/fence HALT breaker real: it
renders the sentinel the campaign beacon child-goal state carries, writes the
status file to .claude/tmp, and detects a prior block so an unattended
--resume refuses to re-run a blocked goal without --force-resume (otherwise
Task Scheduler re-fires the same blocked goal every interval forever).
"""
import argparse, os, sys

SENTINEL_PREFIX = "BLOCKED:"


def sentinel(kind: str) -> str:
    return f"{SENTINEL_PREFIX} {kind}"


def is_blocked(state_text: str) -> bool:
    return SENTINEL_PREFIX in (state_text or "")


def status_markdown(kind: str, detail: str, timestamp: str) -> str:
    return (
        f"# Loop HALT -- {kind}\n\n"
        f"- when: {timestamp}\n"
        f"- kind: {kind}\n"
        f"- detail: {detail}\n\n"
        f"This goal is BLOCKED. Resume only after manual remediation:\n\n"
        f"    /personal-loop --resume <slug> --force-resume\n"
    )


def write_halt(out_dir: str, kind: str, detail: str, timestamp: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    safe_ts = str(timestamp).replace(":", "").replace(" ", "-")
    path = os.path.join(out_dir, f"secret-halt-{safe_ts}.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(status_markdown(kind, detail, timestamp))
    return path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", required=True)
    ap.add_argument("--detail", default="")
    ap.add_argument("--timestamp", required=True)
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args()
    print(write_halt(a.out_dir, a.kind, a.detail, a.timestamp))
    return 0


if __name__ == "__main__":
    sys.exit(main())
