"""Checks the recommender's JSON for /personal-next before the owner sees any option.

Usage: python validate.py <file.json>   (or JSON on stdin)
Exit 0 = usable, prints "OK <n> candidates"; exit 1 = unusable, prints each problem.
"""
import json
import re
import sys

FIELDS = ("id", "label", "meaning", "consequence", "cost", "risk", "reversible", "combinable", "confidence")
BANNED_LABEL = re.compile(r"^\s*(option|choice)\s+[a-z0-9]\b", re.I)


def problems(doc):
    out = []
    if not isinstance(doc, dict):
        return ["top level is not a JSON object"]
    cands = doc.get("candidates")
    if not isinstance(cands, list) or not 2 <= len(cands) <= 4:
        return ["candidates must be a list of 2 to 4 (AskUserQuestion shows 4 options at most)"]
    ids = []
    for i, c in enumerate(cands, 1):
        if not isinstance(c, dict):
            out.append(f"candidate {i} is not an object")
            continue
        missing = [f for f in FIELDS if f not in c]
        if missing:
            out.append(f"candidate {i} missing: {', '.join(missing)}")
        label = str(c.get("label", ""))
        if not label.strip() or len(label.split()) > 5:
            out.append(f"candidate {i} label must be 1 to 5 words: {label!r}")
        if BANNED_LABEL.match(label):
            out.append(f"candidate {i} label is a bare letter/number name: {label!r}")
        ids.append(c.get("id"))
    if len(set(map(str, ids))) != len(ids):
        out.append("candidate ids are not unique")
    top = doc.get("top_pick")
    if top is not None and top not in ids:
        out.append(f"top_pick {top!r} is not one of the candidate ids")
    if not json.dumps(doc, ensure_ascii=False).isascii():
        out.append("non-ASCII text (use plain hyphens, quotes and arrows)")
    return out


def main():
    raw = open(sys.argv[1], encoding="utf-8").read() if len(sys.argv) > 1 else sys.stdin.read()
    try:
        doc = json.loads(raw)
    except ValueError as e:
        print(f"not JSON: {e}")
        return 1
    bad = problems(doc)
    for p in bad:
        print(p)
    if bad:
        return 1
    print(f"OK {len(doc['candidates'])} candidates")
    return 0


if __name__ == "__main__":
    sys.exit(main())
