import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from atomic_write import atomic_write
from phase_table import update_row, get_source, source_is_warranted
from checkpoint import update_checkpoint
from log_appender import (append_cost_row, append_activity_row, append_failure_row,
                          append_decision_row, append_detour_row, close_detour_row,
                          open_detours)

STATUS_MAP = {"PASS": "OK Done", "FAIL": "ERROR Failed", "BLOCKED": "BLOCKED Blocked"}

# Beacons armed before this date predate requirement tracking and are exempt from the
# warrant guard.  Anything armed after it is expected to carry the markers.
GUARD_EPOCH = "2026-09-18"

def _git_add_beacon(bp):
    """Stage the beacon, even when it sits under an ignored directory.

    The beacon is a file this tool creates and owns, and it is the only
    cross-session safety net; it must reach git.  Plain `git add` on a path under
    an ignore rule exits 1 EVEN WHEN THE FILE IS ALREADY TRACKED and even when it
    successfully stages the change -- so a `check=True` call raised on a command
    that had actually worked, and the commit below it never ran.  That is how a
    beacon could be silently left uncommitted for a whole goal.
    """
    subprocess.run(["git", "add", "-f", str(bp)], check=True)




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


VALID_DETOUR_ORIGINS_PREFIX = "phase-"
VALID_DETOUR_ORIGINS = ("pre-existing", "external")


def _handle_decision_and_detour(args):
    """Write a decision or open/close a detour, then return an exit code.

    Returns None when no such flag was passed, so the normal advance path runs.
    These are separate from phase advancement on purpose: a detour is discovered
    mid-phase, and phase advancement only happens at a phase boundary.  Without a
    mid-phase write point the detour record could never be made at the moment it
    is learned, which is the moment it is true.
    """
    if not (args.decision or args.detour_open or args.detour_close):
        return None

    bp = Path(args.beacon)
    content = bp.read_text(encoding="utf-8")
    written = []

    if args.decision:
        content, dec_id = append_decision_row(
            content, args.decision, args.decision_why, args.decision_ruled_out)
        written.append(dec_id)

    if args.detour_open:
        origin = (args.detour_origin or "").strip()
        if not origin:
            print("ERROR: --detour-open requires --detour-origin "
                  "('pre-existing', 'external', or 'phase-<n>'). Which it is decides "
                  "whether this is a detour or drift.", file=sys.stderr)
            return 6
        if origin not in VALID_DETOUR_ORIGINS and not origin.startswith(VALID_DETOUR_ORIGINS_PREFIX):
            print(f"ERROR: --detour-origin must be 'pre-existing', 'external', or "
                  f"'phase-<n>'; got {origin!r}", file=sys.stderr)
            return 6
        if not args.detour_blocks.strip():
            print("ERROR: --detour-open requires --detour-blocks <phase>. Without it "
                  "nothing records where the goal resumes, and the detour quietly "
                  "becomes the project.", file=sys.stderr)
            return 6
        if not args.detour_checked.strip():
            print("ERROR: --detour-checked required. Name the existing mechanism you "
                  "looked at before building something new -- the most common shape of "
                  "drift is new machinery built beside a system that already does the "
                  "job.", file=sys.stderr)
            return 6
        if origin.startswith(VALID_DETOUR_ORIGINS_PREFIX):
            if not re.match(r"^phase-\d+$", origin):
                print(f"ERROR: --detour-origin {origin!r} is not a phase reference; use "
                      f"phase-<n>.", file=sys.stderr)
                return 6
            if not (args.drift_acknowledged or "").strip():
                print(f"ERROR: origin {origin} means an earlier phase of THIS goal created "
                      f"the blocker. That is drift, not a detour, and the remedy is to "
                      f"revert that phase's mechanism rather than build on top of it.\n"
                      f"  This is the repair-loop shape: work that exists only to repair a "
                      f"constraint an earlier choice created.\n"
                      f"  If the owner has looked and still wants to proceed, pass\n"
                      f"    --drift-acknowledged \"<what the owner decided, and when>\"",
                      file=sys.stderr)
                return 6
            print(f"NOTE: recording drift-origin detour with owner acknowledgement.",
                  file=sys.stderr)
        content, det_id = append_detour_row(
            content, origin, args.detour_blocks, args.detour_open, args.detour_checked)
        written.append(det_id)

    if args.detour_close:
        try:
            content = close_detour_row(content, args.detour_close)
        except RuntimeError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 6
        written.append(f"{args.detour_close} closed")

    atomic_write(args.beacon, content)
    # Commit here too. A detour is learned mid-phase, which is exactly when a crash
    # is likely, and 56f5839 established that the beacon must reach git rather than
    # sit on disk until the next phase boundary.
    try:
        _git_add_beacon(Path(args.beacon))
        subprocess.run(["git", "commit", "-q", "-m",
                        f"chore({Path(args.beacon).stem.replace('-audit-tracker','')}): "
                        f"record {', '.join(written)}"], check=True)
    except subprocess.CalledProcessError:
        print("WARNING: recorded in the beacon but the commit failed; commit by hand",
              file=sys.stderr)
    still_open = open_detours(content)
    for w in written:
        print(w)
    if still_open:
        print(f"open detours: {', '.join(still_open)}", file=sys.stderr)
    return 0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--beacon", required=True)
    p.add_argument("--phase", type=int)
    p.add_argument("--outcome", choices=["PASS", "FAIL", "BLOCKED"])
    # Not required at parse time: a --decision / --detour-open write happens mid-phase
    # and has no token or subagent cost of its own.  The normal advance path below
    # still refuses without them.
    p.add_argument("--tokens", type=int, default=None)
    p.add_argument("--duration", type=int, default=None)
    p.add_argument("--commit")
    p.add_argument("--subagent", default=None)
    p.add_argument("--notes", default="")
    p.add_argument("--verify", default="",
                   help="Gate 4 evidence for a PASS: the check that was run plus one quoted "
                        "output line, or 'UNVERIFIED: <reason>'. Required when --outcome=PASS.")
    p.add_argument("--abort", metavar="REASON",
                   help="Mark current phase BLOCKED with ABORT:<reason> and commit.")
    p.add_argument("--override-budget", dest="override_budget", action="store_true",
                   help="Proceed even when token_budget_total would be exceeded; logs override in Activity Log.")
    # --- Decision + detour writers -------------------------------------------
    # Before these existed the beacon could hold a Decisions/Detours section that
    # nothing ever wrote to -- the same failure the Source column already had.
    p.add_argument("--decision", metavar="TEXT",
                   help="Record an owner decision. Prints its DEC-<n> id, which then "
                        "becomes a legal Source value for phases it authorises.")
    p.add_argument("--decision-why", dest="decision_why", default="",
                   help="Why this decision was taken.")
    p.add_argument("--decision-ruled-out", dest="decision_ruled_out", default="",
                   help="What this decision closes off, so it is not silently reopened later.")
    p.add_argument("--detour-open", dest="detour_open", metavar="PROOF",
                   help="Open a detour. PROOF names the failing test, error, or file:line.")
    p.add_argument("--detour-origin", dest="detour_origin", default=None,
                   help="Who created the blocker: 'pre-existing', 'external', or 'phase-<n>'. "
                        "phase-<n> means an earlier phase of THIS goal caused it -- that is "
                        "drift, and the remedy is to revert that phase's mechanism.")
    p.add_argument("--detour-blocks", dest="detour_blocks", default="",
                   help="Which phase this detour unblocks; the goal resumes there.")
    p.add_argument("--detour-checked", dest="detour_checked", default="",
                   help="What existing mechanism you checked first. Required: most drift is "
                        "new machinery built beside something that already does the job.")
    p.add_argument("--drift-acknowledged", dest="drift_acknowledged", default=None,
                   metavar="OWNER_DECISION",
                   help="Required when --detour-origin is phase-<n>: the blocker was "
                        "created by this goal's own earlier phase, so proceeding is a "
                        "decision the owner has to make, not one a session makes alone.")
    p.add_argument("--detour-close", dest="detour_close", metavar="DET-N",
                   help="Close a detour by id. Acceptance refuses while any are open.")
    args = p.parse_args()

    rc = _handle_decision_and_detour(args)
    if rc is not None:
        return rc

    for _flag, _val in (("--tokens", args.tokens), ("--duration", args.duration),
                        ("--subagent", args.subagent)):
        if _val is None:
            print(f"ERROR: {_flag} is required for a phase advance", file=sys.stderr)
            return 2

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
        # Templated, like the PASS path at the bottom of this file. The abort reason is
        # free text and routinely quotes the owner or a client; it is already recorded in
        # the beacon body (Failure Log + Cost Log notes above), where it can be edited.
        # Interpolating it here would put it in a commit message instead, where the only
        # way to remove it is a history rewrite that propagates to every mirror and PR view.
        msg = f"chore({bp.stem.replace('-audit-tracker','')}): phase {args.phase} abort -- see beacon Failure Log"
        _git_add_beacon(bp)
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

    # Fail-closed unverified-done guard (personal-fable-mode Gate 4): a PASS is a
    # done-claim, and a done-claim without evidence is refused before any beacon
    # MUTATION (the budget block above only reads).  'UNVERIFIED: <reason>' passes
    # the guard but is recorded in the Cost Log notes for the critic to see.
    if args.outcome == "PASS" and not args.verify.strip():
        print("ERROR: --verify required when --outcome=PASS "
              "(Gate 4 evidence: the check command + one quoted output line, "
              "or 'UNVERIFIED: <reason>'). Unverified done is refused.", file=sys.stderr)
        return 2
    # Fail-closed unwarranted-scope guard.  A PASS says this phase is done and
    # therefore that it was worth doing; the Source cell is the record of who said
    # so.  PROPOSAL means a plan or a findings pass produced it and nobody has
    # authorised it yet.  Refusing here is what stops a findings inventory becoming
    # a shipped phase list one defensible step at a time.
    if args.outcome == "PASS":
        _beacon_text = Path(args.beacon).read_text(encoding="utf-8")
        try:
            _src = get_source(_beacon_text, args.phase)
        except RuntimeError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 2
        if _src is None:
            print(f"ERROR: phase {args.phase} not declared in the Phase Status table",
                  file=sys.stderr)
            return 2
        # Legacy beacons (armed before requirement_status existed) are warned, not
        # refused.  A goal already in flight must not be bricked mid-run by a new
        # rule it was never armed under; enforcement applies from the next arm.
        # A guard whose off-switch is a deletable line is a guard the gated party owns.
        # Real legacy beacons predate ALL of this, so require every marker to be absent
        # AND the arm date to precede the guard. A beacon armed after GUARD_EPOCH with
        # requirement_status stripped is tampering, not history, and is refused below.
        _markers = (re.search(r"^requirement_status:", _beacon_text, re.MULTILINE),
                    re.search(r"^## Requirement", _beacon_text, re.MULTILINE),
                    re.search(r"^## Detours", _beacon_text, re.MULTILINE))
        _started = re.search(r"^started:\s*(\d{4}-\d{2}-\d{2})", _beacon_text, re.MULTILINE)
        _pre_epoch = bool(_started) and _started.group(1) < GUARD_EPOCH
        _legacy = not any(_markers) and _pre_epoch
        if _legacy and not source_is_warranted(_src, _beacon_text):
            print(f"WARNING: phase {args.phase} has Source {_src!r}, which records no owner "
                  f"warrant. This beacon predates requirement tracking, so the advance is "
                  f"allowed. Re-arm with /personal-goal to get the guard.", file=sys.stderr)
        elif not source_is_warranted(_src, _beacon_text):
            print(f"ERROR: phase {args.phase} has Source {_src!r}, which records no owner "
                  f"warrant, so it cannot be marked done.\n"
                  f"  Set the Source cell to one of:\n"
                  f"    ASK:<a quoted fragment of the requirement this phase serves>\n"
                  f"    DEC-<n>        (an owner decision -- record it with --decision)\n"
                  f"    UNBLOCK:DET-<n> (a logged detour -- open it with --detour-open)\n"
                  f"  If none of those is true, this phase is work nobody asked for.",
                  file=sys.stderr)
            return 6

    # Record VERIFY on PASS only: FAIL/BLOCKED notes feed the Jaccard no-progress
    # detector (_get_last_fail_note), and a near-constant VERIFY string would skew
    # it in both directions.  Sanitize pipes/newlines -- notes land in markdown
    # table cells, and a raw '|' splits the cell and truncates read-back.
    if args.outcome == "PASS" and args.verify.strip():
        v = re.sub(r"\s*[\r\n]+\s*", " ; ", args.verify.strip()).replace("|", "/")
        vnote = f"VERIFY: {v}"
        notes = (notes + " ; " + vnote) if notes else vnote

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
    _git_add_beacon(bp)
    subprocess.run(["git", "commit", "-q", "-m", msg], check=True)
    # Exit 4 when a FAIL was escalated to BLOCKED by loop controls so the driver
    # hard-stops rather than re-dispatching the phase.
    if args.outcome == "FAIL" and effective_outcome == "BLOCKED":
        return 4
    return 0

if __name__ == "__main__":
    sys.exit(main())
