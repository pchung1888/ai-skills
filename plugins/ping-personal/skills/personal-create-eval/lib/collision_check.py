#!/usr/bin/env python3
"""Report which skill descriptions overlap most (word-overlap score, 0.00-1.00).

Usage: python collision_check.py [--skills-dir DIR] [--top N]
Reads the `description:` line of every DIR/*/SKILL.md, skips skills with
`disable-model-invocation: true`, prints the N highest pairs. Always exits 0
(report only; the owner picks a cut-off later).
"""
import argparse
import itertools
import re
import sys
from pathlib import Path

STOP = set("this that with from have will when then them they your into only also each such than "
           "over under use used uses using skill skills trigger triggers and the for are not "
           "any all can its one two via per".split())


def words(text):
    return {w for w in re.findall(r"[a-z0-9][a-z0-9-]{2,}", text.lower()) if w not in STOP}


def load(skills_dir):
    found, skipped = {}, 0
    for p in sorted(Path(skills_dir).glob("*/SKILL.md")):
        m = re.match(r"---\r?\n(.*?)\r?\n---", p.read_text(encoding="utf-8"), re.S)
        fm = m.group(1) if m else ""
        if re.search(r"(?m)^disable-model-invocation:\s*true\s*$", fm):
            skipped += 1
            continue
        d = re.search(r"(?m)^description:\s*(.*)$", fm)
        found[p.parent.name] = words(d.group(1)) if d else set()
    return found, skipped


def rank(found):
    out = []
    for (a, wa), (b, wb) in itertools.combinations(found.items(), 2):
        union = wa | wb
        out.append((len(wa & wb) / len(union) if union else 0.0, a, b))
    return sorted(out, key=lambda t: (-t[0], t[1], t[2]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skills-dir", default=str(Path(__file__).resolve().parents[2]))
    ap.add_argument("--top", type=int, default=10)
    a = ap.parse_args()
    found, skipped = load(a.skills_dir)
    print(f"collision_check: {len(found)} skills scored, {skipped} skipped (disable-model-invocation)")
    for score, x, y in rank(found)[: a.top]:
        print(f"  {score:.2f}  {x}  <->  {y}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
