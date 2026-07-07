#!/usr/bin/env python3
"""Deterministic domain classifier for the personal-lesson master router.

Why this exists (Blog 2 -- "helper scripts so Claude spends cognitive effort on
composition rather than boilerplate reconstruction"): the routing rule in
SKILL.md Step 1 was a keyword-count spec the model executed BY HAND on every
call, and the eval had no input->domain test. This script executes that exact
spec deterministically and is unit-testable.

Source of truth: the baseline keyword table is parsed FROM ../SKILL.md (the same
table a human reads), so there is no second copy to drift. An optional
.claude/lessons-keywords.md override (same table format) EXTENDS the baseline.

Algorithm (matches SKILL.md Step 1):
  - hit count for a domain = number of DISTINCT keywords from that domain's list
    that appear (case-insensitive SUBSTRING) in the lesson text. A keyword
    appearing multiple times still counts once.
  - target = domain with the highest hit count.
  - tie-break order: data -> parser -> ui -> tooling.
  - zero hits across all domains -> personal-lesson-tooling.

KNOWN limitation (documented, accepted trade): substring matching can over-match
short keywords -- `ui` matches inside "build", `git` inside "digital". This is
the SKILL.md-documented behavior; the deterministic script reproduces it exactly
(it cannot apply the fuzzy semantic judgment the model used to). See the Gotchas
section in SKILL.md. Tightening this (word boundaries) was tried and rejected
because it then misses plurals/inflections (`transaction` vs "transactions"),
which is a worse failure for this keyword set. Routing is low-harm and
recoverable, so the documented over-match is accepted.

Usage:
  python classify.py --text "lesson text here"
  echo "lesson text" | python classify.py
  python classify.py --text "..." --explain          # also print per-domain hits to stderr
  python classify.py --text "..." --keywords-file path/to/lessons-keywords.md
"""
import argparse
import sys
from pathlib import Path

# Tie-break priority (SKILL.md Step 1: "data -> parser -> ui -> tooling").
# Zero-hit fallback is the last entry (tooling), consistent with SKILL.md.
PRIORITY = [
    "personal-lesson-data",
    "personal-lesson-parser",
    "personal-lesson-ui",
    "personal-lesson-tooling",
]

DOMAINS = set(PRIORITY)


def parse_keyword_table(md_text):
    """Extract {domain: set(lowercased keywords)} from markdown table rows.

    The FIRST cell must be exactly one of the 4 domains (backticks optional), so
    prose or other tables elsewhere in the file cannot pollute the keyword sets.
    Keywords are read by stripping backticks from the second cell and splitting
    on commas -- so backtick-wrapped (baseline), bare (documented override), and
    mixed cells all parse uniformly:
      | `personal-lesson-ui` | `React`, `tsx`, ... |
      | personal-lesson-ui   | React, tsx, ...     |
    """
    table = {}
    for line in md_text.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        domain = cells[0].strip().strip("`").strip()
        if domain not in DOMAINS:
            continue
        keywords = {t.strip().lower() for t in cells[1].replace("`", "").split(",")}
        keywords.discard("")
        if keywords:
            table.setdefault(domain, set()).update(keywords)
    return table


def hit_counts(text, table):
    """Distinct case-insensitive substring hits per domain. See the module
    docstring + SKILL.md Gotchas for the known short-keyword over-match."""
    text_l = text.lower()
    return {domain: sum(1 for kw in kws if kw in text_l) for domain, kws in table.items()}


def classify(counts):
    """Pick the domain by max hit count, tie-broken by PRIORITY; zero -> tooling."""
    if not counts or max(counts.values(), default=0) == 0:
        return "personal-lesson-tooling"
    top = max(counts.values())
    winners = {d for d, c in counts.items() if c == top}
    for domain in PRIORITY:
        if domain in winners:
            return domain
    # Any domain not in PRIORITY (should not happen) -- deterministic fallback.
    return sorted(winners)[0]


def main(argv=None):
    ap = argparse.ArgumentParser(description="Classify a lesson into a domain skill.")
    ap.add_argument("--text", help="Lesson text. If omitted, read from stdin.")
    ap.add_argument("--skill-md", help="Path to the router SKILL.md (default: ../SKILL.md).")
    ap.add_argument("--keywords-file", help="Optional override table (.claude/lessons-keywords.md).")
    ap.add_argument("--explain", action="store_true", help="Print per-domain hit counts to stderr.")
    args = ap.parse_args(argv)

    skill_md = Path(args.skill_md) if args.skill_md else Path(__file__).resolve().parent.parent / "SKILL.md"
    if not skill_md.is_file():
        print(f"classify.py: SKILL.md not found at {skill_md}", file=sys.stderr)
        return 2
    table = parse_keyword_table(skill_md.read_text(encoding="utf-8"))
    if not table:
        print("classify.py: no keyword table parsed from SKILL.md", file=sys.stderr)
        return 2

    # Optional project override: explicit flag, else auto-detect CWD/.claude/lessons-keywords.md.
    override = Path(args.keywords_file) if args.keywords_file else Path.cwd() / ".claude" / "lessons-keywords.md"
    if override.is_file():
        for domain, kws in parse_keyword_table(override.read_text(encoding="utf-8")).items():
            table.setdefault(domain, set()).update(kws)

    text = args.text if args.text is not None else sys.stdin.read()
    counts = hit_counts(text, table)
    if args.explain:
        for domain in PRIORITY:
            print(f"{domain}: {counts.get(domain, 0)}", file=sys.stderr)
    print(classify(counts))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
