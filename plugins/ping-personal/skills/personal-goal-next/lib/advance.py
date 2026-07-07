import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from atomic_write import atomic_write
from phase_table import update_row
from checkpoint import update_checkpoint
from log_appender import append_cost_row, append_activity_row, append_failure_row

STATUS_MAP = {"PASS": "OK Done", "FAIL": "ERROR Failed", "BLOCKED": "BLOCKED Blocked"}


def _parse_token_budget(content):
    """Return token_budget_total from YAML frontmatter as int, or 0 (unlimited) if absent/zero.

    Missing field or value '0' both return 0 (unlimited).  This preserves backward
    compatibility: legacy beacons without the field are treated as unlimited.
    """
    fm_match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
    if not fm_match:
        return 0
    for line in fm_match.group(1).splitlines():
        m = re.match(r'^token_budget_total:\s*(\d+)\s*$', line)
        if m:
            return int(m.group(1))
    return 0


def _sum_cost_log_tokens(content):
    """Sum the Tokens column of all data rows in the Subagent Token Cost Log.

    The Cost Log header row has columns:
        | # | Phase | Subagent type | Task description | Tokens | Duration | Outcome | Notes |
    Token count is column index 4 (0-based after stripping outer pipes).
    We skip the header row (starts with '| #') and separator rows ('|---').
    """
    marker = "## Subagent Token Cost Log"
    next_marker = "\n## "
    idx = content.find(marker)
    if idx < 0:
        return 0
    nxt = content.find(next_marker, idx + len(marker))
    section = content[idx:nxt] if nxt > 0 else content[idx:]
    total = 0
    for line in section.splitlines():
        if not line.startswith("| "):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        # Skip header (first cell is '#') and separator rows
        if not cells or cells[0] == "#" or cells[0].startswith("--"):
            continue
        if len(cells) >= 5:
            try:
                total += int(cells[4])
            except ValueError:
                pass
    return total


def _update_cost_rollup(content, new_token_total):
    """Replace the Rollup line in the Cost Log with updated totals.

    Expected format (from template):
        Rollup: total=N | phases=N | median/phase=N

    We recompute total and phases from the Cost Log data rows.
    median/phase is computed from per-phase token sums (integer median).
    If no Rollup line exists (legacy beacon), we insert one after the heading.
    """
    marker = "## Subagent Token Cost Log"
    next_marker = "\n## "
    idx = content.find(marker)
    if idx < 0:
        return content
    nxt = content.find(next_marker, idx + len(marker))
    section = content[idx:nxt] if nxt > 0 else content[idx:]

    # Gather per-phase token sums from data rows
    phase_tokens = {}
    for line in section.splitlines():
        if not line.startswith("| "):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if not cells or cells[0] == "#" or cells[0].startswith("--"):
            continue
        if len(cells) >= 5:
            try:
                ph = int(cells[1])
                tk = int(cells[4])
                phase_tokens[ph] = phase_tokens.get(ph, 0) + tk
            except ValueError:
                pass

    total = sum(phase_tokens.values())
    phases = len(phase_tokens)
    if phases == 0:
        median = 0
    else:
        vals = sorted(phase_tokens.values())
        mid = len(vals) // 2
        median = vals[mid] if len(vals) % 2 == 1 else (vals[mid - 1] + vals[mid]) // 2

    rollup_line = f"Rollup: total={total} | phases={phases} | median/phase={median}"

    # Replace existing Rollup line or insert after the heading line
    rollup_re = re.compile(r'^Rollup:.*$', re.MULTILINE)
    section_abs_start = idx
    section_abs_end = nxt if nxt > 0 else len(content)
    section_text = content[section_abs_start:section_abs_end]

    if rollup_re.search(section_text):
        new_section = rollup_re.sub(rollup_line, section_text, count=1)
    else:
        # Insert after heading line
        heading_end = section_text.find("\n") + 1
        new_section = section_text[:heading_end] + "\n" + rollup_line + "\n" + section_text[heading_end:]

    return content[:section_abs_start] + new_section + content[section_abs_end:]


def _parse_max_retries(content):
    """Return the integer value of max_retries from YAML frontmatter, or None if absent.

    Design choice: read from frontmatter (between the first '---' pair) so we do
    not accidentally match the same text appearing in prose sections.  Returns None
    (not 0, not 2) when the field is absent -- callers treat None as "no cap" so
    legacy in-flight beacons are fully unaffected.
    """
    fm_match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
    if not fm_match:
        return None
    for line in fm_match.group(1).splitlines():
        m = re.match(r'^max_retries:\s*(\d+)\s*$', line)
        if m:
            return int(m.group(1))
    return None


def _count_fail_rows(content, phase_n):
    """Count FAIL rows for phase_n in the Failure Log.

    We use the Failure Log (not Cost Log) because the Failure Log records FAIL
    outcomes with explicit 'what_failed' notes that we also need for no-progress
    detection.  The Cost Log records every call including PASSes; filtering it
    by outcome column is more fragile (column position can shift).

    A Failure Log row has the form:
        | <n> | <phase> | <subagent> | <what_failed> | <recovery> | <lesson> |
    We match rows where the phase cell equals phase_n (exact string match after
    strip), which handles phase 1 vs phase 10 safely.
    """
    marker = "## Failure Log"
    next_marker = "\n## "
    idx = content.find(marker)
    if idx < 0:
        return 0
    nxt = content.find(next_marker, idx + len(marker))
    section = content[idx:nxt] if nxt > 0 else content[idx:]
    count = 0
    for line in section.splitlines():
        if not line.startswith("| "):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) >= 2 and cells[1] == str(phase_n):
            count += 1
    return count


def _get_last_fail_note(content, phase_n):
    """Return the 'what_failed' text from the last Failure Log row for phase_n, or None."""
    marker = "## Failure Log"
    next_marker = "\n## "
    idx = content.find(marker)
    if idx < 0:
        return None
    nxt = content.find(next_marker, idx + len(marker))
    section = content[idx:nxt] if nxt > 0 else content[idx:]
    last_note = None
    for line in section.splitlines():
        if not line.startswith("| "):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) >= 4 and cells[1] == str(phase_n):
            last_note = cells[3]  # column index 3 = what_failed
    return last_note


def _token_overlap(a, b):
    """Jaccard similarity over normalized token sets.

    Normalise: lowercase, split on any non-alphanumeric run, drop empty tokens.
    Returns float in [0.0, 1.0].
    """
    def tokenize(s):
        return set(t for t in re.split(r'[^a-z0-9]+', s.lower()) if t)
    ta, tb = tokenize(a), tokenize(b)
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)

TOKEN_WARN_LOW = 0        # warn when <= this
TOKEN_WARN_HIGH = 500000  # warn when > this
TOKEN_REFUSE = 10000000   # refuse when > this


def _glob_collision(beacon_path, slug):
    """Return list of all *<slug>*-audit-tracker.md files under docs/ (excl. the canonical one)."""
    root = Path(beacon_path).resolve().parent
    # Walk up to find a docs/ sibling
    for candidate in [root, root.parent, root.parent.parent]:
        docs = candidate / "docs"
        if docs.is_dir():
            matches = list(docs.rglob(f"*{slug}*-audit-tracker.md"))
            return [str(m) for m in matches if m.resolve() != Path(beacon_path).resolve()]
    return []


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--beacon", required=True)
    p.add_argument("--phase", type=int)
    p.add_argument("--outcome", choices=["PASS", "FAIL", "BLOCKED"])
    p.add_argument("--tokens", type=int, required=True)
    p.add_argument("--duration", type=int, required=True)
    p.add_argument("--commit")
    p.add_argument("--subagent", required=True)
    p.add_argument("--notes", default="")
    p.add_argument("--abort", metavar="REASON",
                   help="Mark current phase BLOCKED with ABORT:<reason> and commit.")
    p.add_argument("--override-budget", dest="override_budget", action="store_true",
                   help="Proceed even when token_budget_total would be exceeded; logs override in Activity Log.")
    args = p.parse_args()

    # Token sanity
    tokens = args.tokens
    notes = args.notes
    if tokens <= TOKEN_WARN_LOW:
        msg = f"WARNING: --tokens={tokens} is <= 0; value looks incorrect."
        print(msg, file=sys.stderr)
        if notes:
            notes = notes + " | " + msg
        else:
            notes = msg
    elif tokens > TOKEN_REFUSE:
        print(f"ERROR: --tokens={tokens} exceeds {TOKEN_REFUSE:,}; value is absurd. "
              "Check your token count and retry.", file=sys.stderr)
        return 2
    elif tokens > TOKEN_WARN_HIGH:
        msg = f"WARNING: --tokens={tokens} exceeds {TOKEN_WARN_HIGH:,}; double-check your count."
        print(msg, file=sys.stderr)
        if notes:
            notes = notes + " | " + msg
        else:
            notes = msg

    # ------------------------------------------------------------------
    # Token ceiling enforcement (Phase 2: goal-skill-v2.1)
    # Read the beacon to check budget BEFORE the --abort or normal path
    # mutates it.  We do this here (after token-sanity, before anything
    # that touches the file) so a budget refusal exits cleanly with no
    # partial state.
    # We only enforce when the beacon file actually exists (the absurd-
    # tokens test deliberately passes a nonexistent path and we must not
    # crash on that; that test exits at the TOKEN_REFUSE guard above).
    _budget_beacon_path = Path(args.beacon)
    if _budget_beacon_path.exists():
        _budget_content = _budget_beacon_path.read_text(encoding="utf-8")
        _budget_total = _parse_token_budget(_budget_content)
        if _budget_total > 0:
            _cost_so_far = _sum_cost_log_tokens(_budget_content)
            _new_total = _cost_so_far + tokens
            if _new_total > _budget_total:
                if not args.override_budget:
                    print(
                        f"BUDGET EXCEEDED: {_new_total}/{_budget_total}",
                        file=sys.stderr,
                    )
                    return 5
                else:
                    # Override: proceed, but record a note in Activity Log
                    # The full mutation happens later; we store the warning
                    # to inject into the activity row notes.
                    _budget_override_note = (
                        f"BUDGET OVERRIDE: cumulative {_new_total} exceeds budget {_budget_total}"
                    )
                    notes = (notes + " | " + _budget_override_note) if notes else _budget_override_note

    # --abort short-circuit
    if args.abort:
        if args.phase is None:
            print("ERROR: --abort requires --phase", file=sys.stderr)
            return 2
        outcome = "BLOCKED"
        notes_abort = f"ABORT: {args.abort}"
        if notes:
            notes_abort = notes + " | " + notes_abort
        bp = Path(args.beacon)
        content = bp.read_text(encoding="utf-8")

        # Collision warning
        others = _glob_collision(args.beacon, bp.stem.replace("-audit-tracker", ""))
        if others:
            print(f"WARNING: multiple audit-trackers match slug -- collision candidates: {', '.join(others)}", file=sys.stderr)

        try:
            content = update_row(content, args.phase, STATUS_MAP[outcome], args.commit, args.subagent)
        except RuntimeError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 2
        content = append_cost_row(content, args.phase, args.subagent, "ABORT",
                                  tokens, args.duration, outcome, notes_abort)
        content = _update_cost_rollup(content, None)
        content = append_activity_row(content, args.phase, outcome, args.commit or "--")
        content = append_failure_row(content, args.phase, args.subagent,
                                     notes_abort, "Goal aborted by operator", "")
        content = update_checkpoint(content, args.phase,
                                    "(aborted)", args.commit or "--",
                                    f"ABORT: {args.abort}")
        atomic_write(args.beacon, content)
        msg = f"chore({bp.stem.replace('-audit-tracker','')}): phase {args.phase} ABORT -- {args.abort}"
        subprocess.run(["git", "add", str(bp)], check=True)
        subprocess.run(["git", "commit", "-q", "-m", msg], check=True)
        print(f"ABORT committed: phase {args.phase} marked BLOCKED.", file=sys.stderr)
        return 0

    # Normal advance path
    if args.phase is None or args.outcome is None:
        print("ERROR: --phase and --outcome are required for normal advance", file=sys.stderr)
        return 2

    if args.outcome == "PASS" and not args.commit:
        print("ERROR: --commit required when --outcome=PASS", file=sys.stderr)
        return 2

    bp = Path(args.beacon)
    content = bp.read_text(encoding="utf-8")

    # Collision warning
    slug_guess = bp.stem.replace("-audit-tracker", "")
    others = _glob_collision(args.beacon, slug_guess)
    if others:
        print(f"WARNING: multiple audit-trackers match slug -- collision candidates: {', '.join(others)}", file=sys.stderr)

    # -- Loop hard controls (Phase 1: goal-skill-v2.1) -------------------------
    # These checks apply only on a FAIL outcome and only when max_retries field
    # is present in frontmatter (missing field = legacy beacon = no cap).
    effective_outcome = args.outcome
    effective_notes = notes
    if args.outcome == "FAIL":
        max_retries = _parse_max_retries(content)
        if max_retries is not None:
            prior_fails = _count_fail_rows(content, args.phase)
            # No-progress check: compare new note against last FAIL note for this phase.
            # Applied BEFORE the retry-cap check so near-identical stalls exit early
            # even on the first retry.
            if prior_fails >= 1:
                last_note = _get_last_fail_note(content, args.phase)
                if last_note is not None:
                    overlap = _token_overlap(effective_notes, last_note)
                    if overlap >= 0.8:
                        effective_outcome = "BLOCKED"
                        effective_notes = (
                            f"NO PROGRESS DETECTED: {effective_notes}"
                            if effective_notes
                            else "NO PROGRESS DETECTED"
                        )
                        print(
                            f"ERROR: no-progress detected for phase {args.phase} "
                            f"(token overlap={overlap:.2f} >= 0.8); blocking.",
                            file=sys.stderr,
                        )
            # Retry cap: this FAIL would be fail number (prior_fails + 1).
            # If that exceeds max_retries, escalate to BLOCKED.
            if effective_outcome == "FAIL" and (prior_fails + 1) > max_retries:
                cap_n = prior_fails + 1
                effective_outcome = "BLOCKED"
                effective_notes = (
                    f"RETRY CAP HIT ({cap_n}): {effective_notes}"
                    if effective_notes
                    else f"RETRY CAP HIT ({cap_n})"
                )
                print(
                    f"ERROR: retry cap hit for phase {args.phase} "
                    f"(fail #{cap_n} > max_retries={max_retries}); blocking.",
                    file=sys.stderr,
                )

    try:
        content = update_row(content, args.phase, STATUS_MAP[effective_outcome], args.commit, args.subagent)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    content = append_cost_row(content, args.phase, args.subagent, "phase work",
                              tokens, args.duration, effective_outcome, effective_notes)
    # Update the Cost Rollup line now that a new row has been appended.
    content = _update_cost_rollup(content, None)
    content = append_activity_row(content, args.phase, effective_outcome,
                                  args.commit or "--")
    if effective_outcome == "PASS":
        content = update_checkpoint(content, args.phase,
                                    "(see Phase Status)", args.commit,
                                    f"Dispatch phase {args.phase + 1}")
    elif effective_outcome == "BLOCKED":
        content = append_failure_row(content, args.phase, args.subagent,
                                     effective_notes or "agent reported blocked",
                                     "Investigate and re-dispatch",
                                     "")
    elif effective_outcome == "FAIL":
        # On FAIL (below cap), write a Failure Log row so subsequent calls can
        # count prior failures and detect no-progress via the note text.
        content = append_failure_row(content, args.phase, args.subagent,
                                     effective_notes or "(no notes)",
                                     "Re-dispatch",
                                     "")
    atomic_write(args.beacon, content)
    # Commit -- use effective_outcome so BLOCKED cap/no-progress shows correctly
    msg = f"chore({bp.stem.replace('-audit-tracker','')}): phase {args.phase} {effective_outcome.lower()}"
    subprocess.run(["git", "add", str(bp)], check=True)
    subprocess.run(["git", "commit", "-q", "-m", msg], check=True)
    # Exit 4 when a FAIL was escalated to BLOCKED by loop controls so the driver
    # hard-stops rather than re-dispatching the phase.
    if args.outcome == "FAIL" and effective_outcome == "BLOCKED":
        return 4
    return 0

if __name__ == "__main__":
    sys.exit(main())
