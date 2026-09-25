import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from log_appender import split_cells, join_cells

PHASE_STATUS_HEADING = "## Phase Status"

# Legal Source values.  Kept here rather than imported from personal-goal/lib so the
# enforcement point has no cross-skill import to break.  personal-goal/lib/plan_parser.py
# holds the matching emitter.
SOURCE_PROPOSAL = "PROPOSAL"
_DECISION_RE = re.compile(r"^DEC-\d+$")


def _normalise(text):
    """Lowercase, collapse whitespace and drop punctuation, so a quoted fragment
    still matches the requirement across re-wrapping and copy-paste."""
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def _section_text(content, heading):
    """Body of a '## <heading>' section, bounded by the next line-start '## '."""
    idx = content.find("\n" + heading)
    if idx < 0:
        idx = 0 if content.startswith(heading) else -1
    else:
        idx += 1
    if idx < 0:
        return ""
    nxt = content.find("\n## ", idx + len(heading))
    return content[idx:(nxt if nxt > 0 else len(content))]


def source_is_warranted(value, beacon_text=None):
    """True only when a phase traces to the owner -- REFERENTIALLY, not by shape.

    Shape alone is not provenance.  Without `beacon_text` this can only check the
    form, and form is trivially satisfiable: 'DEC-99' for a decision that was never
    taken, 'UNBLOCK:DET-42' for a detour nobody logged, 'ASK:' plus any sentence the
    owner never said.  That would make the guard a spelling test for the exact class
    of claim it exists to verify.

    With `beacon_text` the referents are checked:
      DEC-<n>        the row must exist in ## Decisions
      UNBLOCK:DET-<n> the row must exist in ## Detours
      ASK:<fragment>  the fragment must actually appear in ## Requirement

    PROPOSAL and blank are unwarranted in either mode.
    """
    v = (value or "").strip()
    if not v or v == SOURCE_PROPOSAL:
        return False

    if _DECISION_RE.match(v):
        if beacon_text is None:
            return True
        return re.search(r"^\|\s*" + re.escape(v) + r"\s*\|",
                         _section_text(beacon_text, "## Decisions"), re.MULTILINE) is not None

    if v.startswith("UNBLOCK:") and len(v) > 8:
        ref = v[len("UNBLOCK:"):].strip()
        if not re.match(r"^DET-\d+$", ref):
            return False
        if beacon_text is None:
            return True
        return re.search(r"^\|\s*" + re.escape(ref) + r"\s*\|",
                         _section_text(beacon_text, "## Detours"), re.MULTILINE) is not None

    if v.startswith("ASK:") and len(v) > 4:
        frag = _normalise(v[len("ASK:"):])
        if len(frag) < 8:
            return False  # a two-word gesture is not a citation
        if beacon_text is None:
            return True
        return frag in _normalise(_section_text(beacon_text, "## Requirement"))

    return False

def find_table(content):
    idx = content.find(PHASE_STATUS_HEADING)
    if idx < 0:
        raise RuntimeError(f"no '{PHASE_STATUS_HEADING}' heading")
    rest = content[idx:]
    lines = rest.split("\n")
    # Find first markdown table after heading
    start = None
    for i, ln in enumerate(lines):
        if ln.startswith("|"):
            start = i
            break
    if start is None:
        raise RuntimeError("no markdown table after Phase Status heading")
    header = lines[start]
    sep = lines[start + 1] if start + 1 < len(lines) else ""
    if header.count("|") - 1 != 6:
        raise RuntimeError(f"phase status table must have 6 columns; got {header.count('|') - 1}")
    rows = []
    end = start + 2
    while end < len(lines) and lines[end].startswith("|"):
        rows.append(lines[end])
        end += 1
    return idx, start, end, header, sep, rows

def get_source(content, phase_num):
    """Return the Source cell for a phase, or None when the phase is not declared.

    The Source cell is what records who warranted this phase: a quoted fragment of
    the owner's ask, a decision id, or a logged detour.  advance.py gates PASS on it.
    """
    _idx, _start, _end, _header, _sep, rows = find_table(content)
    for r in rows:
        cells = [c.strip() for c in split_cells(r)]
        if cells and cells[0] == str(phase_num):
            return cells[1] if len(cells) > 1 else ""
    return None


def update_row(content, phase_num, new_status, new_commit, new_subagent):
    idx, start, end, header, sep, rows = find_table(content)
    matched = []
    for i, r in enumerate(rows):
        # split_cells honours the \| escape the writers emit; a naive split on a
        # title containing a pipe shifts every later column, so the positional
        # writes below would land on the wrong fields.
        cells = [c.strip() for c in split_cells(r)]
        if cells and cells[0].lstrip().startswith(str(phase_num)):
            # Distinguish phase 1 from phase 10 etc.
            if cells[0].strip() == str(phase_num):
                matched.append((i, cells))
    if len(matched) == 0:
        raise RuntimeError(f"phase {phase_num} not declared in Phase Status table")
    if len(matched) > 1:
        raise RuntimeError(f"duplicate phase {phase_num} rows -- corruption")
    i, cells = matched[0]
    current_status = cells[3]
    if "✅ Done" in current_status or "OK Done" in current_status:
        raise RuntimeError(f"duplicate advance: phase {phase_num} already done")
    cells[3] = new_status
    cells[4] = new_commit or "--"
    cells[5] = new_subagent or "--"
    new_row = join_cells(cells)
    rows[i] = new_row
    abs_lines = content.split("\n")
    abs_start = idx + sum(len(l) + 1 for l in content[:idx].split("\n")[:-1])
    # Splice rows back -- simpler: rebuild full content
    full_lines = content.split("\n")
    abs_offset = full_lines.index(header)
    for j, r in enumerate(rows):
        full_lines[abs_offset + 2 + j] = r
    return "\n".join(full_lines)
