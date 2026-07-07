#!/usr/bin/env python3
"""campaign.py -- parse/advance the campaign beacon (outer-loop spine)."""
import argparse, sys

_HEADER_TOKENS = {"goal", "state", "beacon"}

def parse_children(text: str) -> list[dict]:
    children = []
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) < 3:
            continue
        if "---" in cells[0] or cells[0].lower() in _HEADER_TOKENS:
            continue
        children.append({"goal": cells[0], "state": cells[1], "beacon": cells[2]})
    return children

def next_pending_goal(children: list[dict]) -> str | None:
    for c in children:
        if c.get("state", "").lower() != "done":
            return c["goal"]
    return None

def goal_exists(children: list[dict], slug: str) -> bool:
    """Guard against the silent-no-op infinite re-fire: marking a typo'd slug
    done changes nothing, so next_pending keeps returning the same child and an
    unattended loop re-runs it forever. The driver MUST verify this is True
    before calling mark_goal_done."""
    return any(c.get("goal") == slug for c in children)

def mark_goal_done(text: str, goal_slug: str) -> str:
    out = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            if cells and cells[0] == goal_slug and len(cells) >= 3:
                cells[1] = "done"
                out.append("| " + " | ".join(cells) + " |")
                continue
        out.append(line)
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--next", required=True)
    a = ap.parse_args()
    with open(a.next, encoding="utf-8") as fh:
        children = parse_children(fh.read())
    print(next_pending_goal(children) or "")
    return 0

if __name__ == "__main__":
    sys.exit(main())
