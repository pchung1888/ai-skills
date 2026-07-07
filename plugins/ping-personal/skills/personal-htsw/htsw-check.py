#!/usr/bin/env python3
"""htsw-check.py — validator for htsw rendering output.

Cross-platform replacement for htsw-check.ps1. Runs on macOS, Linux, and Windows
with no extra packages — Python 3 stdlib only. UTF-8 enforced for input files.

Usage:
  python3 htsw-check.py --input-file <path-to-rendering.md>
  python3 htsw-check.py --input-string "<rendering content>"

Exit codes:
  0  rendering passes the icon, TL;DR, and length contracts
  1  rendering fails one or more contract checks (details on stderr)

What it checks (per SKILL.md):
  pr mode (4 tiers: GOOD 🌮 / PASS 🟢 / WARNING ⚠ / BAD 🔴):
    - First-line citation present and well-formed
    - Tier title (## heading) present in first 15 lines, non-generic
    - TL;DR section present right after tier title with 2-4 icon bullets
    - HOW-THIS-WORKS section present (recognized header variation) with ≥ 20 words
    - Deeper-dive section ("Where to slow down" or variation) when trigger fires
      (≥ 5 diff --git headers, or .dll/.cache/.pdb/.exe/.bin marker, or 'Bin N -> M' line)
    - At least one icon somewhere in the rendering
    - Ticket-vs-PR alignment section has icons (if present)
    - Diff block has inline icon markers (if present)
    - Evidence-and-suggestion contract: every ⚠ / 🔴 in 'Watch out for' /
      'Where to look' / 'Edge cases' / 'Regressions' / 'Spec gaps' body
      sections must contain BOTH an evidence marker (file:line in backticks,
      RFC reference, quoted source, SQL/HTTP observation, or
      "the source doesn't say" qualifier) AND a suggestion-arrow
      (→ fix: / → suggestion: / → optional: / → next: / → ask:).
    - Length ≤ 600 words

  qa mode (post-test — bug writeup):
    - Tier title contains 🔴
    - TL;DR section present with 2-4 icon bullets, no 🌮
    - HOW-THIS-WORKS section present
    - Evidence-and-suggestion contract on body-section bullets
    - Jira-vs-code reality-check table present
    - Tables have Status column
    - At least one 🔴 somewhere
    - No 🌮 anywhere (Mode 3 unavailable post-test)
    - Length ≤ 700 words

  qa mode (pre-test — test design; 3 tiers: GOOD 🌮 / PASS 🟢 / WARNING ⚠):
    - Tier title present, non-generic
    - TL;DR section present with 2-4 icon bullets
    - HOW-THIS-WORKS section present
    - Evidence-and-suggestion contract on body-section bullets
    - Test-case table has Status column
    - At least one 🟢
    - Length ≤ 700 words

  boss mode:
    - NO status icons (icon-free contract)
    - NO 🌮
    - No banned words (schema / validation / atomicity / hook / wrapper / JSONL / etc.)
    - Length ≤ 400 words
"""
import argparse
import re
import sys
from pathlib import Path

# Force stdout/stderr to UTF-8 so em-dashes and icons render on Windows consoles
# (default cp1252) without mojibake. macOS/Linux already default to UTF-8.
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, 'reconfigure'):
        try:
            stream.reconfigure(encoding='utf-8')
        except (AttributeError, ValueError):
            pass


def load_content(args):
    if args.input_file:
        path = Path(args.input_file)
        if not path.is_file():
            print(f"[htsw-check] FAIL: input file not found: {args.input_file}", file=sys.stderr)
            sys.exit(1)
        return path.read_text(encoding='utf-8')
    return args.input_string


def detect_purpose(content):
    first_line = content.split('\n', 1)[0].strip()
    m = re.match(r'_Explaining:\s+.+?\s+·\s+purpose:\s+(pr|qa|boss|walk|baby|code-explain)_', first_line)
    if not m:
        print(
            "[htsw-check] FAIL: first line missing citation format "
            "'_Explaining: <source> · purpose: <pr|qa|boss|walk|baby|code-explain>_'",
            file=sys.stderr,
        )
        print(f"[htsw-check] saw: {first_line}", file=sys.stderr)
        sys.exit(1)
    return m.group(1)


def count_words(content):
    return len([w for w in re.split(r'\s+', content) if w])


def find_tier_title(content):
    """Return the first ## heading text within 15 lines after the citation, or None."""
    parts = content.split('\n', 1)
    if len(parts) < 2:
        return None
    for line in parts[1].split('\n')[:15]:
        m = re.match(r'^##\s+(.+?)\s*$', line)
        if m:
            return m.group(1).strip()
    return None


def find_tldr_block(content):
    """Return the TL;DR section body (text after the bold label, up to the next
    H2/H3 heading or the next top-of-line bold-section label).
    """
    pat = re.compile(
        r'\*\*TL;DR[^*\n]*\*\*\s*\n+(.+?)(?=\n##\s|\n###\s|\n\*\*[A-Z][^*\n]*\*\*[:\s]|\Z)',
        re.DOTALL,
    )
    m = pat.search(content)
    return m.group(1) if m else None


# Allowed DEEPER-DIVE section header phrases (case-insensitive).
# When the deeper-dive trigger fires (≥ 5 files changed in the diff block, or
# binary/generated-file marker present) the rendering MUST include one of these.
DEEPER_DIVE_HEADER_PHRASES = [
    r"where to slow down",
    r"reviewer attention map",
    r"read these first",
    r"the load-bearing files",
    r"where to focus",
    r"heat map",
    r"don'?t skim these",
]
DEEPER_DIVE_HEADER_PATTERN = re.compile(
    r"(?im)^###\s+(" + "|".join(DEEPER_DIVE_HEADER_PHRASES) + r")\s*$"
)


def deeper_dive_trigger_fires(content):
    """Return (fires: bool, reason: str). Trigger fires if the rendering shows
    a diff with ≥ 5 'diff --git' headers, OR any binary/generated-file marker
    (.dll / .cache / .pdb / .exe / 'Bin ' '-> Bin ' pattern from git --stat).
    Falls back to counting rows in 'Impact at a glance' table if no diff block.
    """
    diff_match = re.search(r'```diff(.+?)```', content, re.DOTALL)
    if diff_match:
        diff_body = diff_match.group(1)
        file_headers = re.findall(r'(?m)^diff --git\s', diff_body)
        if len(file_headers) >= 5:
            return (True, f">= 5 files in diff block ({len(file_headers)})")
        # Also count 'diff --git'-less file headers like '--- a/' '+++ b/' pairs.
        plus_minus = len(re.findall(r'(?m)^\+\+\+\s+b/', diff_body))
        if plus_minus >= 5:
            return (True, f">= 5 file headers (+++ b/) in diff block ({plus_minus})")
    if re.search(r'\.(dll|cache|pdb|exe|bin)\b', content, re.IGNORECASE):
        return (True, "binary/generated file marker present (.dll/.cache/.pdb/.exe/.bin)")
    if re.search(r'\bBin\s+\d+\s*->\s*\d+', content):
        return (True, "git-stat binary line ('Bin N -> M') present")
    # Fall back to Impact-at-a-glance row count.
    iaag_match = re.search(
        r'(?is)impact\s+at\s+a\s+glance.*?(\n##\s|\n\*\*[A-Z]|\Z)', content
    )
    if iaag_match:
        block = iaag_match.group(0)
        rows = re.findall(r'(?m)^\|\s*`[^|]+\|', block)
        if len(rows) >= 5:
            return (True, f">= 5 rows in Impact-at-a-glance ({len(rows)})")
    return (False, "")


# Allowed HOW-THIS-SHIT-WORKS section header phrases (case-insensitive).
# Union of variations from references/pr.md and references/qa.md.
HTSW_HEADER_PHRASES = [
    r"how this shit works",
    r"what this actually does",
    r"what this is supposed to do",
    r"what'?s actually happening",
    r"what'?s really happening",
    r"what'?s broken about it",
    r"what the user sees",
    r"in plain english",
    r"the flow",
    r"the intended flow",
    r"the real flow",
    r"how it should behave",
    r"how it all fits together",
    r"behind the scenes",
    r"under the hood",
    r"the mechanics",
    r"the expected mechanics",
    r"the mechanics of the bug",
    r"the plumbing",
]
# S2: HTSW_HEADER_PATTERN now accepts an optional emoji prefix before the
# recognized phrase. Walk mode allows ⚙ (per SKILL.md line 206/517); baby mode
# allows 📦 or 🏷️ (per SKILL.md line 260). Consolidating into one shared pattern
# removes the need for a parallel BABY_HTSW_HEADER_PATTERN.
#
# Note on 🏷️: U+1F3F7 LABEL is usually followed by U+FE0F VARIATION SELECTOR-16
# to request emoji presentation. We match both orderings and the bare codepoint.
_HTSW_ICON_PREFIX = r"(?:(?:⚙|📦|🏷️?|🏷️)\s+)"
HTSW_HEADER_PATTERN = re.compile(
    r"(?im)^###\s+" + _HTSW_ICON_PREFIX + r"?(" + "|".join(HTSW_HEADER_PHRASES) + r")\s*$"
)


def find_htsw_section(content):
    """Return (heading_text, body) for the first HOW-THIS-WORKS section,
    or (None, None) if no recognized HTSW heading is found.

    Accepts optional emoji prefix (⚙ for walk, 📦 or 🏷️ for baby) before
    the recognized phrase. The captured group is the phrase only (no prefix).
    """
    m = HTSW_HEADER_PATTERN.search(content)
    if not m:
        return (None, None)
    heading = m.group(1)
    # Body runs from end of heading to the next H2/H3/section divider
    after = content[m.end():]
    body_m = re.match(
        r"\s*\n+(.+?)(?=\n##\s|\n###\s|\n\*\*[A-Z][^*\n]*\*\*[:\s]|\n---|\Z)",
        after,
        re.DOTALL,
    )
    body = body_m.group(1).strip() if body_m else ""
    return (heading, body)


# Baby mode uses the same HTSW_HEADER_PATTERN (S2 consolidation).
# find_htsw_section_baby is kept as a thin wrapper for backward compatibility
# with check_baby() callers.
def find_htsw_section_baby(content):
    """Wrapper around find_htsw_section for baby-mode callers.

    Now delegates to the shared HTSW_HEADER_PATTERN which accepts 📦, 🏷️,
    and ⚙ prefixes (S2 consolidation). Returns (heading_text, body) or (None, None).
    """
    return find_htsw_section(content)


# Body sections that must satisfy the evidence-and-suggestion contract for
# every ⚠ / 🔴 bullet. Diff blocks, tables, and the TL;DR are exempt.
EVIDENCE_SECTION_LABELS = [
    r"Watch out for",
    r"Where to look",
    r"Where to look first",
    r"Edge cases worth probing",
    r"Edge cases",
    r"Regressions to watch",
    r"Regressions",
    r"Spec gaps",
]
EVIDENCE_SECTION_PATTERN = re.compile(
    r"\*\*(" + "|".join(EVIDENCE_SECTION_LABELS) + r")[^*]*\*\*\s*\n+(.+?)"
    r"(?=\n##\s|\n###\s|\n\*\*[A-Z][^*\n]*\*\*[:\s]|\n---|\Z)",
    re.DOTALL,
)

# Evidence markers — at least ONE must appear in each ⚠ / 🔴 bullet body.
EVIDENCE_PATTERN = re.compile(
    r"`[^`]+`"                              # backtick-wrapped code/path/SQL
    r"|RFC\s+\d+"                           # RFC reference
    r"|MDN[:\s]"                            # MDN reference
    r"|MSRB\s+Rule"                         # MSRB rule
    r"|searched\b"                          # explicit negative search
    r"|found nothing|no match|no such file" # explicit not-found
    r"|doesn'?t\s+(say|mention|contain)"    # source-doesn't-say qualifier
    r"|not present"                         # explicit not-found
    r"|\sshows\s|\sreturns\s"               # SQL/HTTP observation verbs
    r"|Evidence:",                          # explicit Evidence: prefix
    re.IGNORECASE,
)

# Suggestion-arrow markers — at least ONE must appear in each ⚠ / 🔴 bullet body.
# Five arrows total (severity-ordered):
#   fix       → must-do before merge (blocker)
#   suggestion → should-do before merge (strongly recommended)
#   optional  → nice-to-have, fine to defer (non-blocking)
#   next      → follow-up after merge (separate ticket / future PR)
#   ask       → question for PM / dev / stakeholder
SUGGESTION_PATTERN = re.compile(
    r"→\s*(fix|suggestion|optional|next|ask)\s*:",
    re.IGNORECASE,
)


def check_evidence_and_suggestion(content):
    """For each body section (Watch out for / Where to look / Edge cases / etc.),
    every ⚠ or 🔴 bullet must contain BOTH an evidence marker and a suggestion-arrow.
    Returns a list of finding strings.
    """
    findings = []
    for sec_m in EVIDENCE_SECTION_PATTERN.finditer(content):
        section_name = sec_m.group(1)
        body = sec_m.group(2)
        # Split body into bullets by the leading "- 🔴" or "- ⚠" markers.
        # Use a positive lookahead split so we keep each bullet's text.
        bullets = re.split(r"(?m)^(?=- [🔴⚠🟢])", body)
        for bullet in bullets:
            bullet = bullet.strip()
            if not (bullet.startswith("- 🔴") or bullet.startswith("- ⚠")):
                continue
            icon = "🔴" if "🔴" in bullet[:6] else "⚠"
            has_evidence = bool(EVIDENCE_PATTERN.search(bullet))
            has_suggestion = bool(SUGGESTION_PATTERN.search(bullet))
            # Preview is first 70 chars stripped of leading "- 🔴 " for readability.
            preview = re.sub(r"\s+", " ", bullet[:120]).strip()
            if not has_evidence:
                findings.append(
                    f"evidence marker missing on {icon} bullet in '{section_name}' "
                    f"(file:line, RFC, quoted source, SQL/HTTP observation, or "
                    f"\"the source doesn't say\" required) — {preview[:80]}…"
                )
            if not has_suggestion:
                findings.append(
                    f"suggestion-arrow missing on {icon} bullet in '{section_name}' "
                    f"(→ fix: / → suggestion: / → optional: / → next: / → ask: required) — "
                    f"{preview[:80]}…"
                )
    return findings


def check_pr(content, word_count):
    findings = []

    title = find_tier_title(content)
    if title is None:
        findings.append(
            "FAIL (pr): no tier title (## heading) in the first 15 lines after the citation. "
            "See pr.md tier-title library."
        )
    else:
        generic = {'review', 'pr review', 'pr review brief', 'summary', 'overview',
                   'brief', 'introduction', 'intro'}
        if title.lower() in generic:
            findings.append(
                f"FAIL (pr): tier title '{title}' is generic. Pick from the pr.md tier-title library."
            )

    tldr = find_tldr_block(content)
    if tldr is None:
        findings.append(
            "FAIL (pr): no TL;DR section. Every PR rendering MUST open with "
            "'**TL;DR — <action verb>:**' bullets right after the tier title."
        )
    else:
        if not re.search(r'🔴|⚠|🟢', tldr):
            findings.append("FAIL (pr): TL;DR block contains no status icons.")
        bullets = re.findall(r'(?m)^\s*-\s+', tldr)
        n = len(bullets)
        if n < 2:
            findings.append(f"FAIL (pr): TL;DR has {n} bullet(s); contract requires 2-4.")
        elif n > 4:
            findings.append(f"FAIL (pr): TL;DR has {n} bullets; contract caps at 4. Tighten.")

    if not re.search(r'🔴|⚠|🟢', content):
        findings.append("FAIL (pr): no status icons (🔴/⚠/🟢) anywhere in the rendering.")

    if re.search(r'(?i)ticket-?vs-?pr\s+alignment', content):
        block_match = re.search(
            r'(?is)ticket-?vs-?pr\s+alignment.*?(?=\n##\s|\n###\s|\n\*\*[A-Z][^*]*\*\*[:\s]|\Z)',
            content,
        )
        if block_match and not re.search(r'🔴|⚠|🟢', block_match.group(0)):
            findings.append("FAIL (pr): Ticket-vs-PR alignment section has no status icons.")

    diff_match = re.search(r'```diff(.+?)```', content, re.DOTALL)
    if diff_match:
        if not re.search(r'🔴|⚠|🟢', diff_match.group(1)):
            findings.append(
                "FAIL (pr): diff block has no inline icon markers. "
                "Add ← 🔴/⚠/🟢 annotations to the lines that matter."
            )
    else:
        findings.append("WARN (pr): no ```diff block found. Most PR renderings should include one.")

    htsw_heading, htsw_body = find_htsw_section(content)
    if htsw_heading is None:
        findings.append(
            "FAIL (pr): no HOW-THIS-WORKS section. Every PR rendering MUST include a "
            "'### How this shit works' (or recognized variation) section explaining what "
            "the diff actually does in plain English."
        )
    elif not htsw_body or len(htsw_body.split()) < 20:
        findings.append(
            f"FAIL (pr): HOW-THIS-WORKS section '### {htsw_heading}' is too short. "
            "Need 2-4 sentences (~20+ words) explaining what the diff does in plain English."
        )

    trigger_fires, trigger_reason = deeper_dive_trigger_fires(content)
    if trigger_fires:
        dd_match = DEEPER_DIVE_HEADER_PATTERN.search(content)
        if not dd_match:
            findings.append(
                f"FAIL (pr): deeper-dive trigger fires ({trigger_reason}) but no "
                "'### Where to slow down' (or recognized variation) section found. "
                "Large diffs require a reviewer attention map — see pr.md §5."
            )

    evidence_findings = check_evidence_and_suggestion(content)
    for f in evidence_findings:
        findings.append(f"FAIL (pr): {f}")

    if word_count > 600:
        findings.append(f"FAIL (pr): rendering is {word_count} words; pr target ≤ 600. Tighten.")

    return findings


def check_qa(content, word_count):
    findings = []
    variant = 'post-test' if re.search(r'(?i)jira\s+vs\.?\s+code|reality\s+check', content) else 'pre-test'

    title = find_tier_title(content)
    if title is None:
        findings.append(f"FAIL (qa {variant}): no tier title (## heading) in the first 15 lines.")
    else:
        generic = {'qa review', 'qa brief', 'test plan', 'summary', 'overview',
                   'brief', 'introduction', 'intro'}
        if title.lower() in generic:
            findings.append(
                f"FAIL (qa {variant}): tier title '{title}' is generic. "
                "Pick from the qa.md tier-title library."
            )
        if variant == 'post-test' and '🔴' not in title:
            findings.append(
                f"FAIL (qa post-test): tier title '{title}' does not contain 🔴. "
                "Post-test titles must open with 🔴 (this is a bug writeup)."
            )

    tldr = find_tldr_block(content)
    if tldr is None:
        findings.append(
            f"FAIL (qa {variant}): no TL;DR section. QA renderings MUST open with "
            "'**TL;DR — <action verb>:**' bullets right after the tier title."
        )
    else:
        if not re.search(r'🔴|⚠|🟢', tldr):
            findings.append(f"FAIL (qa {variant}): TL;DR block has no status icons.")
        bullets = re.findall(r'(?m)^\s*-\s+', tldr)
        n = len(bullets)
        if n < 2:
            findings.append(f"FAIL (qa {variant}): TL;DR has {n} bullet(s); contract requires 2-4.")
        elif n > 4:
            findings.append(f"FAIL (qa {variant}): TL;DR has {n} bullets; contract caps at 4.")
        if variant == 'post-test' and '🌮' in tldr:
            findings.append("FAIL (qa post-test): 🌮 in TL;DR; Mode 3 unavailable in post-test.")

    has_red = '🔴' in content
    has_warn = '⚠' in content
    has_green = '🟢' in content
    if not (has_red or has_warn or has_green):
        findings.append(f"FAIL (qa {variant}): no status icons (🔴/⚠/🟢) anywhere.")

    tables = re.findall(r'\|[^\n]+\|\s*\n\|[\s\|:-]+\|\s*\n', content)
    if tables and not any(re.search(r'\bStatus\b', t) for t in tables):
        findings.append(
            f"FAIL (qa {variant}): tables present but no Status column. "
            "Jira-vs-code or test-case tables MUST have a Status column."
        )

    if variant == 'post-test':
        if not has_red:
            findings.append("FAIL (qa post-test): no 🔴 icon. Bug writeups must mark at least one violation.")
        if '🌮' in content:
            findings.append("FAIL (qa post-test): 🌮 found. Mode 3 (celebration) is unavailable post-test.")
    else:
        if not has_green:
            findings.append("FAIL (qa pre-test): no 🟢 icon. At least one test case must cover an AC.")

    htsw_heading, htsw_body = find_htsw_section(content)
    if htsw_heading is None:
        findings.append(
            f"FAIL (qa {variant}): no HOW-THIS-WORKS section. Every QA rendering MUST include "
            "a '### How this shit works' (or recognized variation) section explaining what "
            "the feature does (pre-test) or what's broken (post-test) in plain English."
        )
    elif not htsw_body or len(htsw_body.split()) < 20:
        findings.append(
            f"FAIL (qa {variant}): HOW-THIS-WORKS section '### {htsw_heading}' is too short. "
            "Need 2-4 sentences (~20+ words) of plain-English explanation."
        )

    evidence_findings = check_evidence_and_suggestion(content)
    for f in evidence_findings:
        findings.append(f"FAIL (qa {variant}): {f}")

    if word_count > 700:
        findings.append(f"FAIL (qa): rendering is {word_count} words; qa target ≤ 700. Tighten.")

    return findings


def check_walk(content, word_count, is_persisted=False):
    """Walk mode — the explainer / how-it-works mode. Default when no mode is
    given. Light-touch validation because walk has no verdict; the contract is:
    (a) first-line citation present (checked by detect_purpose),
    (b) some kind of section title in the first 15 lines, not generic,
    (c) a HOW-THIS-WORKS section present (this is the load-bearing artifact
        in walk mode),
    (d) NO PR/QA tier-title icons in the title (no 🌮/🔴 etc. as a verdict),
    (e) NO action-verb verdict labels (`**TL;DR — block this:**` etc.),
    (f) length under target (700 inline / 1200 persisted).
    """
    findings = []

    title = find_tier_title(content)
    if title is None:
        findings.append(
            "FAIL (walk): no section title (## heading) in the first 15 lines after the citation. "
            "Walk mode still needs a title — pick a descriptive one (see walk.md title library)."
        )
    else:
        generic = {'review', 'pr review', 'pr review brief', 'summary', 'overview',
                   'brief', 'introduction', 'intro', 'walk-through', 'explainer'}
        if title.lower() in generic:
            findings.append(
                f"FAIL (walk): title '{title}' is generic. Pick a descriptive one — "
                "see walk.md title library."
            )
        # Walk mode title must NOT carry a verdict icon as a tier-title pattern.
        # The user can still mention 🔴 inside the title text if they're explaining
        # something genuinely broken, but the *opening* shouldn't read like a PR/QA
        # tier verdict.
        if re.match(r'^[🌮]', title):
            findings.append(
                f"FAIL (walk): title '{title}' opens with 🌮 — that's a GOOD-tier "
                "PR/QA verdict pattern. Walk mode doesn't pass verdicts; the title "
                "should describe the subject, not grade it."
            )

    # Walk mode forbids the action-verb TL;DR label pattern from PR/QA, but
    # allows a 'TL;DR — the core idea:' or 'TL;DR — short version:' style label.
    forbidden_tldr = re.search(
        r'\*\*TL;DR\s*[—\-]\s*(block this|ship it|hard nope|address these|file it|send it back|escalate|merge it)',
        content,
        re.IGNORECASE,
    )
    if forbidden_tldr:
        findings.append(
            f"FAIL (walk): TL;DR uses a verdict action-verb "
            f"('{forbidden_tldr.group(1)}') — that's PR/QA pattern. Walk-mode "
            "TL;DR labels should be descriptive ('the core idea', 'short version', "
            "'in one breath')."
        )

    # HOW-THIS-WORKS section is the load-bearing artifact in walk mode.
    htsw_heading, htsw_body = find_htsw_section(content)
    if htsw_heading is None:
        findings.append(
            "FAIL (walk): no HOW-THIS-WORKS section. Walk mode REQUIRES a "
            "'### How this shit works' (or recognized variation) section "
            "as the main explainer paragraph."
        )
    elif not htsw_body or len(htsw_body.split()) < 30:
        findings.append(
            f"FAIL (walk): HOW-THIS-WORKS section '### {htsw_heading}' is too short. "
            "Walk mode's main section needs 3-5 sentences (~30+ words) of plain-English "
            "explanation."
        )

    # Verdict icons appearing in the title or as section-leading bullets are a
    # smell — walk mode should not look like PR/QA. They CAN appear inline as
    # navigation/punctuation, just not as the structural tier system.
    if re.search(r'(?m)^##\s+(?:🔴|⚠|🟢)\s', content):
        findings.append(
            "FAIL (walk): an H2 heading starts with a verdict icon (🔴/⚠/🟢). "
            "Walk mode titles should describe the subject, not assign a verdict. "
            "Use these icons inline if you must, not as section openers."
        )

    cap = 1200 if is_persisted else 700
    cap_label = "persisted" if is_persisted else "inline"
    if word_count > cap:
        findings.append(
            f"FAIL (walk): rendering is {word_count} words; walk {cap_label} "
            f"target ≤ {cap}. Tighten."
        )

    # Per-### -section soft warning (advisory; does NOT fail the check).
    # Catches "one bloated section in an otherwise OK doc" — the pathology
    # the relaxed total cap doesn't catch on its own.
    emit_section_warnings(content)

    return findings


def check_baby(content, word_count, is_persisted=False):
    """Baby mode -- story-first analogy-alongside-jargon explainer (v0.3.0).

    v0.3.0 contract (D6 pivot from cast-first to story-first):

    KEPT from v0.2.0:
      - Citation line (handled by detect_purpose before this is called)
      - Title not generic, no verdict-icon H2 opener
      - No verdict action-verb TL;DR label
      - HOW-WORKS section present (baby-aware pattern accepts 📦/🏷️ prefix)
      - Banned sanitization words: easy / simple / just / basic / don't worry
      - Banned baby-talk words: sweetie / honey / ok kiddo / buddy / lil'
      - Length cap: 1800 inline / 3000 persisted
      - Per-section 400-word soft warning

    CHANGED:
      - Cast table location: heading must appear in the LAST 30% of the rendering
        (byte offset >= 0.65 * total length). v0.2.0 allowed it anywhere.
      - Term-occurrence rule: every Cast term must appear in the story body BEFORE
        the Cast table at least once (inline-intro proves the term was introduced).
        The old >=2x rule is dropped.

    DROPPED:
      - CAST_EXTENSION_PATTERN regex / "Cast extension note:" text-marker logic.
        Replaced by D5 Status column: inherited rows are exempt from inline-intro check.

    ADDED:
      - D9 audience-declaration check: `_For: <body>_` within first 5 lines after citation.
      - Story-rhythm block check: fenced code block (no lang tag) with >=5 pipe-only
        connector lines AND >=5 lines containing a parenthetical (...) analogy gloss.
      - Inline-character-intro check: first occurrence of each Cast term in body-before-cast
        must be bold-shaped (`**term**` or `**phrase (term)**`) followed within ~120 chars
        by a parenthetical or dash gloss. Inherited rows (Status column = "inherited") exempt.
      - Label-only WARN (soft, stderr only, does NOT fail): for each Cast analogy cell,
        if the cell contains no verb-indicator, emit a WARN.
    """
    findings = []
    cast_term_occurrences = {}  # populated for INFO output; keyed by term

    # --- Title check (same as walk) ---
    title = find_tier_title(content)
    if title is None:
        findings.append(
            "FAIL (baby): no section title (## heading) in the first 15 lines after the citation. "
            "Baby mode needs a descriptive title -- see baby.md title library."
        )
    else:
        generic = {'review', 'pr review', 'pr review brief', 'summary', 'overview',
                   'brief', 'introduction', 'intro', 'walk-through', 'explainer', 'explanation'}
        if title.lower() in generic:
            findings.append(
                f"FAIL (baby): title '{title}' is generic. Pick a descriptive one -- "
                "see baby.md title library."
            )
        if re.match(r'^[🌮]', title):
            findings.append(
                f"FAIL (baby): title '{title}' opens with 🌮 -- that's a GOOD-tier "
                "PR/QA verdict pattern. Baby mode doesn't pass verdicts."
            )

    # --- Verdict action-verb TL;DR check (same as walk) ---
    forbidden_tldr = re.search(
        r'\*\*TL;DR\s*[—\-]\s*(block this|ship it|hard nope|address these|file it|send it back|escalate|merge it)',
        content,
        re.IGNORECASE,
    )
    if forbidden_tldr:
        findings.append(
            f"FAIL (baby): TL;DR uses a verdict action-verb "
            f"('{forbidden_tldr.group(1)}') -- that's PR/QA pattern. Baby-mode "
            "TL;DR labels should be descriptive ('the core idea', 'short version', "
            "'in one breath')."
        )

    # --- Verdict icons as H2 section openers ---
    if re.search(r'(?m)^##\s+(?:🔴|⚠|🟢)\s', content):
        findings.append(
            "FAIL (baby): an H2 heading starts with a verdict icon (🔴/⚠/🟢). "
            "Baby mode titles should describe the subject, not assign a verdict."
        )

    # --- D9: audience-declaration check ---
    # Find the citation line (first line), then look for `_For: <body>_` within 5 lines.
    lines = content.split('\n')
    # Citation is line 0; check lines 1-5 (up to 5 lines after citation).
    FOR_LINE_PATTERN = re.compile(r'^_For:\s+(.+?)_\s*$')
    for_line_found = False
    for line in lines[1:6]:
        m = FOR_LINE_PATTERN.match(line.strip())
        if m and m.group(1).strip():
            for_line_found = True
            break
    if not for_line_found:
        findings.append(
            "FAIL (baby): no '_For: <audience persona>_' line found within the first 5 lines "
            "after the citation. v0.3.0 requires an audience declaration immediately after "
            "the citation line. Shape: '_For: junior front-end dev -- knows JS, never written React_'"
        )

    # --- (f) HOW-WORKS section (uses baby-aware pattern with emoji prefix support) ---
    htsw_heading, htsw_body = find_htsw_section_baby(content)
    if htsw_heading is None:
        findings.append(
            "FAIL (baby): no HOW-THIS-WORKS section. Baby mode REQUIRES a "
            "'### How this shit works' (or recognized variation, optionally prefixed "
            "with 📦 or 🏷️) section as the main explainer."
        )
    elif not htsw_body or len(htsw_body.split()) < 30:
        findings.append(
            f"FAIL (baby): HOW-THIS-WORKS section '### {htsw_heading}' is too short. "
            "Baby mode's main section needs 3-5 sentences (~30+ words) explaining "
            "the system in both vocabularies."
        )

    # --- Story-rhythm block check (D6 ADD) ---
    # A qualifying block is a fenced code block (no language tag) with:
    #   - >= 5 lines that are ONLY whitespace + '|' (pipe-only connector lines)
    #   - >= 5 lines that contain a parenthetical (...)  analogy gloss
    STORY_BLOCK_PATTERN = re.compile(r'```\s*\n((?:[^`]|`(?!``))+?)\n```', re.DOTALL)
    PIPE_CONNECTOR = re.compile(r'^\s*\|\s*$', re.MULTILINE)
    PAREN_ANALOGY_LINE = re.compile(r'^.+\([^)]{5,}\).*$', re.MULTILINE)

    story_block_found = False
    for sb_m in STORY_BLOCK_PATTERN.finditer(content):
        block_text = sb_m.group(1)
        pipe_count = len(PIPE_CONNECTOR.findall(block_text))
        paren_count = len(PAREN_ANALOGY_LINE.findall(block_text))
        if pipe_count >= 5 and paren_count >= 5:
            story_block_found = True
            # Emit the block's approximate line number in the original content to INFO.
            block_start_line = content[:sb_m.start()].count('\n') + 1
            block_end_line = block_start_line + block_text.count('\n') + 2
            print(
                f"[htsw-check] INFO (baby): story-rhythm block found at lines "
                f"~{block_start_line}-{block_end_line} "
                f"({pipe_count} pipe connectors, {paren_count} paren-analogy lines).",
                file=sys.stderr,
            )
            break

    if not story_block_found:
        findings.append(
            "FAIL (baby): no story-rhythm block found. v0.3.0 requires a fenced code block "
            "(no language tag) with >= 5 pipe-only connector lines AND >= 5 lines containing "
            "a parenthetical analogy gloss like '(errand boy goes to the back room)'. "
            "This block is the vertical scene the reader watches."
        )

    # --- (a+b) Cast of characters table -- position + inline-intro checks ---
    # v0.3.0: Cast heading must appear in the LAST 30% of the rendering
    # (byte offset >= 0.65 * total length).
    total_len = len(content)
    cast_match = re.search(r'(?im)^###\s+Cast of characters\s*$', content)
    if not cast_match:
        findings.append(
            "FAIL (baby): no '### Cast of characters' section found. "
            "Baby mode REQUIRES a Cast recap table mapping jargon | analogy | role, "
            "placed in the last ~30% of the rendering."
        )
    else:
        cast_heading_offset = cast_match.start()
        if cast_heading_offset < 0.65 * total_len:
            pct = int(100 * cast_heading_offset / total_len)
            findings.append(
                f"FAIL (baby): '### Cast of characters' heading is at {pct}% of the rendering "
                f"(byte offset {cast_heading_offset} of {total_len}); "
                "v0.3.0 requires it in the LAST ~30% (offset >= 65%). "
                "Move the Cast table to the end -- it's a recap, not an upfront roster."
            )

        # The story body is everything BEFORE the Cast heading.
        story_body = content[:cast_heading_offset]

        # Parse Cast table rows. Support 3-col (jargon|analogy|role) AND
        # 4-col (jargon|analogy|role|status) tables -- D5 Status column.
        table_start = cast_match.end()
        table_region = content[table_start:]

        # Collect rows: capture up to 4 pipe-delimited columns.
        # Col 0 = jargon, Col 1 = analogy, Col 2 = role, Col 3 = status (optional).
        table_rows_raw = re.findall(
            r'(?m)^\|\s*(`[^|]+`|[^|]+)\|([^|]*)\|([^|]*)\|?([^|\n]*)?\|?\s*$',
            table_region
        )
        # Filter out separator rows and header rows.
        SKIP_TERMS = {'jargon', 'term', ''}

        def is_separator(cell):
            return bool(re.match(r'^[\s\-:]+$', cell.strip()))

        data_rows = []
        for r in table_rows_raw:
            col0 = r[0].strip()
            if is_separator(col0):
                continue
            if col0.lower() in SKIP_TERMS:
                continue
            data_rows.append(r)

        if len(data_rows) < 3:
            findings.append(
                f"FAIL (baby): Cast of characters table has {len(data_rows)} data row(s); "
                "contract requires >= 3 rows (each mapping jargon | analogy | role)."
            )

        # --- D5: Status column parsing ---
        # If the 4th column (index 3) of any row contains "inherited" or "new",
        # treat this as a Status-column table. Rows with "inherited" status are
        # exempt from the inline-intro check (they were introduced in a prior rendering).
        def is_status_col(val):
            v = val.strip().lower()
            return v in ('inherited', 'new', 'status', '')

        # Determine if this Cast table has a meaningful Status column.
        has_status_col = any(
            r[3].strip().lower() in ('inherited', 'new')
            for r in data_rows
        )

        # --- (b) inline-intro check: every Cast term must appear in story_body
        # in a bold-shaped sentence before the Cast table.
        # Two valid intro shapes:
        #   Shape A: **term** or **`term`** followed within 120 chars by ( or -- (no newline/period)
        #   Shape B: **phrase (`term`)** -- term is inside the bold span itself
        #
        # Inherited rows (Status col = "inherited") are exempt.

        for row_idx, row in enumerate(data_rows):
            raw_term = row[0].strip()
            term = raw_term.replace('`', '').strip()
            if not term or is_separator(term):
                continue

            analogy_cell = row[1].strip()

            # Determine if this row is inherited (D5 Status column).
            status_val = row[3].strip().lower() if has_status_col else ''
            is_inherited = (status_val == 'inherited')

            escaped_term = re.escape(term)

            # Count occurrences in story body (before Cast table).
            occurrences_in_story = len(re.findall(escaped_term, story_body))
            cast_term_occurrences[term] = occurrences_in_story

            if is_inherited:
                # Inherited rows: must appear >= 1x in story body (not necessarily bold-intro).
                if occurrences_in_story < 1:
                    findings.append(
                        f"FAIL (baby): inherited Cast term '{term}' has 0 occurrences "
                        "in the story body before the Cast table. Even inherited terms must "
                        "appear at least once (the story continues with them)."
                    )
                continue  # no inline-intro requirement for inherited rows

            # New rows: must appear at least once in story body before Cast table.
            if occurrences_in_story < 1:
                findings.append(
                    f"FAIL (baby): Cast term '{term}' never appears in the story body "
                    "before the Cast table. v0.3.0 requires every term to be introduced "
                    "inline as a character BEFORE the recap table."
                )
                continue

            # Check that the FIRST occurrence in story_body is a bold-shaped intro.
            # Shape A: **<anything containing term>** then within 120 chars a gloss opener
            #   gloss opener = ( or -- (two hyphens)  [em-dashes banned by style rules]
            # Shape B: the bold span itself contains the term wrapped in parens or backticks:
            #   **phrase (`term`)** or **phrase (term)**
            #
            # Implementation: find the first occurrence of the term in story_body,
            # then check if there is a bold marker (**) within a reasonable window before it
            # AND the bold span is followed by a gloss within 120 chars after the closing **.
            #
            # We look for two patterns; either suffices.

            # Pattern A: \*\*[^*]*?<term>[^*]*?\*\* followed by [^\n.]{0,120}?(\(|--)
            INTRO_A = re.compile(
                r'\*\*[^*\n]*?' + escaped_term + r'[^*\n]*?\*\*[^\n.]{0,120}?(?:\(|--)',
            )
            # Pattern B: \*\*[^*]*?\(<term>\)[^*]*?\*\* or term inside parens inside bold
            INTRO_B = re.compile(
                r'\*\*[^*\n]*?\(' + escaped_term + r'[^)]*\)[^*\n]*?\*\*',
            )

            intro_found = bool(INTRO_A.search(story_body)) or bool(INTRO_B.search(story_body))

            if not intro_found:
                findings.append(
                    f"FAIL (baby): Cast term '{term}' is not introduced inline with a bold "
                    "subject-position intro before the Cast table. v0.3.0 requires the first "
                    "mention to be bold-shaped: '**The errand boy (`useEffect`)**' or "
                    "'**`term`** (analogy -- role)' followed by a parenthetical or -- gloss "
                    "within ~120 chars. Check that the term's first appearance is a sentence "
                    "subject with an action verb, not an embedded parenthetical."
                )

            # --- Label-only WARN (D6 soft check, stderr only, does NOT fail) ---
            # Heuristic: analogy cell is label-only if it contains no verb-indicator token
            # after the first noun-ish word. Indicators: word ending -s/-es/-ing/-ed,
            # or the words 'who'/'that'/'which'.
            VERB_INDICATOR = re.compile(
                r'\b(?:who|that|which)\b'
                r'|[a-zA-Z]+(?:s|es|ing|ed)\b',
                re.IGNORECASE,
            )
            if analogy_cell and not VERB_INDICATOR.search(analogy_cell):
                print(
                    f"[htsw-check] WARN (baby): analogy '{analogy_cell}' for term '{term}' "
                    "may be label-only -- consider adding an action verb "
                    "(e.g. 'clerk who walks each row' not just 'clerk').",
                    file=sys.stderr,
                )

    # --- (c) Banned sanitization words ---
    sanitization_bans = [
        (r'\beasy\b', 'easy'),
        (r'\bsimple\b', 'simple'),
        (r'\bjust\b', 'just'),
        (r'\bbasic\b', 'basic'),
        (r"\bdon'?t\s+worry\b", "don't worry"),
    ]
    for pattern, label in sanitization_bans:
        if re.search(pattern, content, re.IGNORECASE):
            findings.append(
                f"FAIL (baby): banned sanitization word '{label}' found. "
                "These words signal analogy-replacing-thinking. Remove or rephrase."
            )

    # --- (d) Banned baby-talk words ---
    babytalk_bans = [
        (r'\bsweetie\b', 'sweetie'),
        (r'\bhoney\b', 'honey'),
        (r'\bok\s+kiddo\b', 'ok kiddo'),
        (r'\bbuddy\b', 'buddy'),
        (r"\blil['\s]", "lil'"),
    ]
    for pattern, label in babytalk_bans:
        if re.search(pattern, content, re.IGNORECASE):
            findings.append(
                f"FAIL (baby): banned baby-talk word '{label}' found. "
                "Baby mode is mentor voice, not kindergarten voice."
            )

    # --- (e) Length cap ---
    cap = 3000 if is_persisted else 1800
    cap_label = "persisted" if is_persisted else "inline"
    if word_count > cap:
        findings.append(
            f"FAIL (baby): rendering is {word_count} words; baby {cap_label} "
            f"target <= {cap}. Tighten."
        )

    # Per-section soft warning (advisory; does NOT fail the check).
    # Baby mode uses a higher per-section threshold (400 vs walk's 300) because
    # baby prose is inherently denser: each sentence carries both jargon and analogy.
    emit_section_warnings(content, mode='baby')

    # Emit per-term story-body occurrence counts to stderr (informational; always emitted).
    if cast_term_occurrences:
        counts_str = ', '.join(
            f"{t}: {c}" for t, c in cast_term_occurrences.items()
        )
        print(
            f"[htsw-check] INFO (baby): Cast term story-body occurrences -- {counts_str}",
            file=sys.stderr,
        )

    return findings


def emit_section_warnings(content, mode='walk', threshold=None):
    """Per-mode advisory: warn if any ### section exceeds the mode threshold.

    Emitted to stderr only -- does NOT add to the findings list, so it does NOT
    fail the validator. Compensates for the relaxed total cap on persisted docs:
    "one bloated section hiding in an otherwise OK doc" is exactly what the
    higher overall cap can't catch on its own.

    mode thresholds (F3/S1):
      walk -- 300 words per ### section
      baby -- 400 words per ### section (baby prose is inherently denser)
    """
    _mode_thresholds = {'walk': 300, 'baby': 400}
    if threshold is None:
        threshold = _mode_thresholds.get(mode, 300)
    h3_pattern = re.compile(r'(?m)^(###\s+.+?)$')
    matches = list(h3_pattern.finditer(content))
    if not matches:
        return
    for i, m in enumerate(matches):
        header = m.group(1).strip()
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        body = content[body_start:body_end]
        # Section ends at the next H2 too, in case the doc has a top-level H2 break.
        h2_in_body = re.search(r'(?m)^##\s+', body)
        if h2_in_body:
            body = body[:h2_in_body.start()]
        words = count_words(body)
        if words > threshold:
            print(
                f"[htsw-check] WARN ({mode}): section '{header}' is {words} words -- "
                f"consider tightening (soft target <= {threshold} per ### section).",
                file=sys.stderr,
            )


def emit_flowchart_warnings(content, is_persisted=False):
    """Detect mermaid blocks and emit portability + syntax-breaker warnings to stderr.

    Does NOT fail the validator — these are advisory warnings. Fills the gap
    between the structural eval (citation/title/TL;DR/length) and a factual
    critic: the syntax-level concerns that are mechanically detectable but
    currently invisible to both layers.
    """
    mermaid_blocks = list(re.finditer(
        r'```mermaid\s*\n(.*?)```',
        content,
        re.DOTALL | re.IGNORECASE,
    ))
    if not mermaid_blocks:
        return

    if is_persisted:
        print(
            "[htsw-check] WARN: mermaid block(s) in persisted doc — mermaid renders "
            "only in mermaid-aware viewers (GitHub, GitLab, VS Code with extension, "
            "Confluence with plugin). For broader portability prefer ASCII flowchart "
            "(box-drawing chars in a plain code block). See SKILL.md § 'Diagram syntax'.",
            file=sys.stderr,
        )

    for i, m in enumerate(mermaid_blocks, 1):
        block = m.group(1)

        # Check 1: HTML tags other than <br/> anywhere in the block
        html_tags = re.findall(
            r'<(?!br\s*/?>)\s*([a-zA-Z][a-zA-Z0-9]*)(?:\s+[^>]*)?\s*/?>',
            block,
        )
        # Filter out closing tags (</tag>) — they'd be paired with their opener anyway
        html_tags = [t for t in html_tags if t]
        if html_tags:
            unique = sorted({t.lower() for t in html_tags})
            print(
                f"[htsw-check] WARN: mermaid block #{i} contains HTML tag(s): "
                f"{', '.join('<' + t + '>' for t in unique)}. Only <br/> is universally "
                "supported in mermaid labels — Confluence's plugin will fail on the rest.",
                file=sys.stderr,
            )

        # Check 2: HTML inside edge labels (between | ... |). Edge-label parser
        # is stricter than node-label parser, so even tags that *might* survive
        # in node labels will break here.
        edge_pat = re.compile(r'\|([^|]*)\|')
        for edge_match in edge_pat.finditer(block):
            edge_label = edge_match.group(1)
            if re.search(r'<[a-zA-Z]', edge_label):
                print(
                    f"[htsw-check] WARN: mermaid block #{i} edge label "
                    f"|{edge_label.strip()}| contains HTML. Move complex annotations "
                    "into the destination node text — the edge-label parser is stricter.",
                    file=sys.stderr,
                )
                break  # one warning per block is enough signal

        # Check 3: '#' inside edge labels. Mermaid uses '#' as a comment char
        # at statement level; the lexer can get confused even inside | ... |.
        for edge_match in edge_pat.finditer(block):
            edge_label = edge_match.group(1)
            if '#' in edge_label:
                print(
                    f"[htsw-check] WARN: mermaid block #{i} edge label "
                    f"|{edge_label.strip()}| uses '#'. Mermaid treats '#' as a comment "
                    "char; replace with '-' or spell out 'number'.",
                    file=sys.stderr,
                )
                break


def check_boss(content, word_count):
    findings = []
    if re.search(r'🔴|⚠|🟢', content):
        findings.append("FAIL (boss): status icons (🔴/⚠/🟢) found. Boss output is icon-free by contract.")
    if '🌮' in content:
        findings.append("FAIL (boss): 🌮 found. Boss output is professional only — no taco.")

    banned = ['schema', 'validation', 'atomicity', 'hook', 'wrapper', 'JSONL', 'PowerShell', 'regex']
    for word in banned:
        if re.search(rf'(?i)\b{word}\b', content):
            findings.append(f"FAIL (boss): banned word '{word}' found. Boss vocabulary excludes this term.")

    if word_count > 400:
        findings.append(f"FAIL (boss): rendering is {word_count} words; boss target ≤ 400. Tighten.")
    return findings


def check_code_explain(content, word_count, is_persisted=False):
    """code-explain mode -- the deep, file-by-file + line-by-line code walkthrough.

    A heavier sibling of walk. It shares walk's skeleton (descriptive title, descriptive
    TL;DR, HOW-THIS-WORKS section, no verdict icons) but ADDS three code-explain-specific
    requirements that distinguish a teaching walkthrough from a quick explainer:
      (a) a WHY-first framing (the reason the change exists, stated before the mechanics),
      (b) a file-by-file map (what changed where), and
      (c) at least one fenced code block (line-by-line needs the real lines quoted).
    Length cap is generous because line-by-line of real code legitimately runs long.
    """
    findings = []

    # --- shared with walk: descriptive title, not generic, no verdict-icon opener ---
    title = find_tier_title(content)
    if title is None:
        findings.append(
            "FAIL (code-explain): no ## title in the first 15 lines after the citation. "
            "Name the change/subject -- see code-explain.md title guidance."
        )
    else:
        generic = {'review', 'pr review', 'summary', 'overview', 'brief', 'introduction',
                   'intro', 'walk-through', 'explainer', 'code explanation', 'code walkthrough',
                   'code explaination'}
        if title.lower() in generic:
            findings.append(
                f"FAIL (code-explain): title '{title}' is generic. Name the actual "
                "change/subject -- see code-explain.md."
            )
        if re.match(r'^[🌮]', title):
            findings.append(
                f"FAIL (code-explain): title '{title}' opens with 🌮 -- a PR/QA verdict "
                "pattern. code-explain describes the change, it doesn't grade it."
            )

    # --- shared with walk: TL;DR present, descriptive label (not a verdict action-verb) ---
    if find_tldr_block(content) is None:
        findings.append(
            "FAIL (code-explain): no TL;DR block. Open with '**TL;DR -- the core idea:**' "
            "(or 'short version' / 'why this exists') + 2-4 navigation-icon bullets."
        )
    forbidden_tldr = re.search(
        r'\*\*TL;DR\s*[—\-]\s*(block this|ship it|hard nope|address these|file it|send it back|escalate|merge it)',
        content,
        re.IGNORECASE,
    )
    if forbidden_tldr:
        findings.append(
            f"FAIL (code-explain): TL;DR uses a verdict action-verb "
            f"('{forbidden_tldr.group(1)}') -- that's a PR/QA pattern. Use a descriptive "
            "label ('the core idea', 'short version', 'why this exists')."
        )

    # --- shared with walk: HOW-THIS-WORKS section is required ---
    htsw_heading, htsw_body = find_htsw_section(content)
    if htsw_heading is None:
        findings.append(
            "FAIL (code-explain): no HOW-THIS-WORKS section. Add a "
            "'### How this shit works' (or recognized variation) explainer paragraph."
        )
    elif not htsw_body or len(htsw_body.split()) < 30:
        findings.append(
            f"FAIL (code-explain): HOW-THIS-WORKS section '### {htsw_heading}' is too "
            "short (need ~30+ words of plain-English explanation)."
        )

    # --- code-explain-specific (a): WHY-first framing ---
    if not re.search(
        r'(?im)(why we (do|did) it|the problem|the whole reason|what changed|why this exists|why it exists)',
        content,
    ):
        findings.append(
            "FAIL (code-explain): no WHY framing. code-explain leads with the reason for "
            "the change -- add a 'Why we did it' / 'The problem' section, or a 'what changed' "
            "title framing."
        )

    # --- code-explain-specific (b): file-by-file map ---
    has_file_map = re.search(r'(?im)(file-by-file|file map|files changed|files touched)', content) \
        or re.search(r'(?im)^#{2,4}\s+File\b', content)
    if not has_file_map:
        findings.append(
            "FAIL (code-explain): no file-by-file map. Add a 'File-by-file map' table or "
            "per-file '## File N' sections so the reader knows what changed where."
        )

    # --- code-explain-specific (c): at least one fenced code block (line-by-line evidence) ---
    if len(re.findall(r'(?m)^```', content)) < 2:
        findings.append(
            "FAIL (code-explain): no fenced code block. code-explain is code-heavy -- quote "
            "the real lines you're explaining in a ``` block."
        )

    # --- shared with walk: no verdict-icon H2 opener ---
    if re.search(r'(?m)^##\s+(?:🔴|⚠|🟢)\s', content):
        findings.append(
            "FAIL (code-explain): an H2 heading opens with a verdict icon (🔴/⚠/🟢). "
            "code-explain describes the change; it doesn't grade it."
        )

    # --- length: generous dual cap (line-by-line of real code runs long) ---
    cap = 4000 if is_persisted else 3000
    cap_label = "persisted" if is_persisted else "inline"
    if word_count > cap:
        findings.append(
            f"FAIL (code-explain): rendering is {word_count} words; code-explain "
            f"{cap_label} target <= {cap}. Tighten, or split into per-file sections."
        )

    # Per-### -section soft warning (advisory; higher threshold than walk because a
    # line-by-line per-file section legitimately carries more words).
    emit_section_warnings(content, threshold=600)

    return findings


def validate_one(content, is_persisted=False):
    """Validate a single rendering string. Returns (purpose, word_count, findings).

    `is_persisted` affects walk mode (700 -> 1200) and code-explain mode
    (3000 -> 4000). PR/QA/boss have their own fixed caps that don't change
    with persistence.
    """
    purpose = detect_purpose(content)
    word_count = count_words(content)
    if purpose == 'pr':
        findings = check_pr(content, word_count)
    elif purpose == 'qa':
        findings = check_qa(content, word_count)
    elif purpose == 'walk':
        findings = check_walk(content, word_count, is_persisted)
    elif purpose == 'baby':
        findings = check_baby(content, word_count, is_persisted)
    elif purpose == 'code-explain':
        findings = check_code_explain(content, word_count, is_persisted)
    else:
        findings = check_boss(content, word_count)

    # Flowchart warnings apply to ALL modes (mermaid can appear in PR/QA/walk
    # renderings; boss shouldn't have mermaid but warn anyway for consistency).
    emit_flowchart_warnings(content, is_persisted)

    return (purpose, word_count, findings)


def split_examples(content):
    """Split a multi-example file (like references/examples/walk-examples.md) into
    individual renderings. Each rendering starts at an `_Explaining: ... · purpose: <mode>_`
    citation line and runs until the next such line (or end of file).

    Returns a list of (block_index, citation_line, full_block_text) tuples.
    Returns empty list if no citation lines found.
    """
    pattern = re.compile(
        r'(?m)^_Explaining:\s+.+?\s+·\s+purpose:\s+(?:pr|qa|boss|walk|baby|code-explain)_\s*$'
    )
    matches = list(pattern.finditer(content))
    if not matches:
        return []
    blocks = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        block = content[start:end].rstrip()
        citation = m.group(0)
        blocks.append((i + 1, citation, block))
    return blocks


def validate_examples_file(path):
    """Validate every rendering inside a multi-example file. Print per-example
    PASS/FAIL. Return 0 if all pass, 1 if any fail.
    """
    p = Path(path)
    if not p.is_file():
        print(f"[htsw-check] FAIL: examples file not found: {path}", file=sys.stderr)
        return 1
    content = p.read_text(encoding='utf-8')
    blocks = split_examples(content)
    if not blocks:
        print(
            f"[htsw-check] FAIL: no `_Explaining: ... · purpose: <mode>_` "
            f"citation lines found in {path}",
            file=sys.stderr,
        )
        return 1
    print(f"[htsw-check] examples file: {path}")
    print(f"[htsw-check] found {len(blocks)} example(s)")
    any_failed = False
    for idx, citation, block in blocks:
        # detect_purpose() will sys.exit(1) on a non-citation first line — we
        # need to be defensive because the block's first line IS the citation.
        try:
            # Example blocks inside a multi-example file are persisted by
            # definition — the file is a saved doc, not an inline chat answer.
            purpose, word_count, findings = validate_one(block, is_persisted=True)
        except SystemExit:
            any_failed = True
            print(f"[htsw-check] Example {idx}: FAIL (could not parse)", file=sys.stderr)
            continue
        if findings:
            any_failed = True
            print(
                f"[htsw-check] Example {idx} ({purpose}, {word_count} words): "
                f"FAIL — {len(findings)} finding(s)",
                file=sys.stderr,
            )
            for f in findings:
                print(f"    [htsw-check]   {f}", file=sys.stderr)
        else:
            print(
                f"[htsw-check] Example {idx} ({purpose}, {word_count} words): PASS"
            )
    if any_failed:
        print(
            f"[htsw-check] examples summary: {len(blocks)} total — at least one FAILED",
            file=sys.stderr,
        )
        return 1
    print(f"[htsw-check] examples summary: {len(blocks)} total — all PASSED")
    return 0


def main():
    parser = argparse.ArgumentParser(description='htsw rendering validator (cross-platform).')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--input-file', help='Path to a markdown rendering to validate.')
    group.add_argument('--input-string', help='Inline string to validate.')
    group.add_argument(
        '--examples-file',
        help='Path to a multi-example markdown file (references/examples/*.md). '
             'Validates every rendering inside. Splits on `_Explaining:` citation '
             'lines. Exit 0 only if every example passes.',
    )
    parser.add_argument(
        '--persisted',
        action='store_true',
        help='Treat the rendering as a persisted doc (walk-mode cap: 1200 words). '
             'Default: persisted=True when --input-file or --examples-file is used; '
             'persisted=False when --input-string is used. This flag forces persisted=True.',
    )
    args = parser.parse_args()

    if args.examples_file:
        sys.exit(validate_examples_file(args.examples_file))

    # Persistence inference: --input-file implies persisted (the rendering was
    # saved to a doc); --input-string implies inline (typed/piped chat answer).
    # The --persisted flag is an explicit override (forces True).
    is_persisted = bool(args.persisted) or bool(args.input_file)

    content = load_content(args)
    purpose, word_count, findings = validate_one(content, is_persisted)

    if not findings:
        print(f"[htsw-check] PASS: {purpose} rendering meets the contract (word count: {word_count}).")
        sys.exit(0)
    print(f"[htsw-check] FAIL: {len(findings)} finding(s):", file=sys.stderr)
    for f in findings:
        print(f"  [htsw-check] {f}", file=sys.stderr)
    sys.exit(1)


if __name__ == '__main__':
    main()
