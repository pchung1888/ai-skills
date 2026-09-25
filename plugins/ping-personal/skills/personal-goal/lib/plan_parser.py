"""Parse a plan file into beacon Phase Status rows.

The Source column is deliberately NOT auto-filled with a self-reference.  A phase
parsed out of a plan document has no owner warrant yet -- the plan is a proposal
until the owner triages it -- so every parsed row is emitted as PROPOSAL.

advance.py refuses to mark a PROPOSAL phase Done (exit 6).  That refusal is what
makes the Source column mean something; before it, the column was filled with the
phase's own number and nothing ever read it.
"""

import re
import sys
from pathlib import Path

PHASE_RE = re.compile(r"^#{2,3}\s+Phase\s+(\d+)(?:\s*[:\-]\s*(.+?))?\s*$", re.MULTILINE)

# Legal Source cell values.  Anything else cannot advance.
SOURCE_PROPOSAL = "PROPOSAL"
SOURCE_ASK_PREFIX = "ASK:"
SOURCE_DECISION_RE = re.compile(r"^DEC-\d+$")
SOURCE_UNBLOCK_PREFIX = "UNBLOCK:"


def cell_escape(text):
    """Make free text safe for a pipe-delimited markdown table cell.

    phase_table.find_table() hard-enforces a 6-column header and update_row()
    indexes cells positionally, so a raw '|' anywhere in a Source cell silently
    shifts every later column and the NEXT advance raises.  Newlines would end
    the row outright.
    """
    if text is None:
        return ""
    return (str(text)
            .replace("\\", "\\\\")
            .replace("|", "\\|")
            .replace("\r", " ")
            .replace("\n", " ")
            .strip())


def is_legal_source(value):
    """True when a Source cell carries an owner warrant.

    PROPOSAL is a legal *value* but not a warrant -- it is the honest label for
    'nobody has authorised this yet'.  Callers that gate advancement check
    source_is_warranted() instead.
    """
    v = (value or "").strip()
    if not v:
        return False
    if v == SOURCE_PROPOSAL:
        return True
    if v.startswith(SOURCE_ASK_PREFIX) and len(v) > len(SOURCE_ASK_PREFIX):
        return True
    if SOURCE_DECISION_RE.match(v):
        return True
    if v.startswith(SOURCE_UNBLOCK_PREFIX) and len(v) > len(SOURCE_UNBLOCK_PREFIX):
        return True
    return False


def source_is_warranted(value):
    """True only when the phase traces to the owner: a quoted ask, a decision id,
    or a logged detour.  PROPOSAL, blank, and junk are all unwarranted."""
    v = (value or "").strip()
    if v == SOURCE_PROPOSAL or not v:
        return False
    return is_legal_source(v)


def parse_phases(plan_path):
    text = Path(plan_path).read_text(encoding="utf-8")
    phases = []
    for m in PHASE_RE.finditer(text):
        n = int(m.group(1))
        title = (m.group(2) or "").strip()
        phases.append((n, title))
    return phases


def phase_rows(phases):
    rows = []
    for n, title in phases:
        rows.append(
            f"| {n} | {SOURCE_PROPOSAL} | {cell_escape(title)} | Pending | -- | -- |"
        )
    return "\n".join(rows)


if __name__ == "__main__":
    print(phase_rows(parse_phases(sys.argv[1])))
