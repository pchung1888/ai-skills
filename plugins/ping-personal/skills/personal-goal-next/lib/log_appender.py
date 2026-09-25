import re
import datetime


def _last_table_row_end(content, section_start, section_end):
    """Return the index of the newline that closes the last markdown table row
    (a line starting with '|') within the section.  Falls back to section_end
    if no table row is found."""
    chunk = content[section_start:section_end] if section_end > 0 else content[section_start:]
    last_pos = -1
    for i, line in enumerate(chunk.split("\n")):
        if line.startswith("|"):
            # track byte offset of this line's trailing newline
            last_pos = chunk.rindex(line)
    if last_pos < 0:
        return section_end if section_end > 0 else len(content)
    abs_pos = section_start + last_pos
    nl = content.find("\n", abs_pos)
    return nl if nl >= 0 else len(content)


def append_cost_row(content, phase_n, subagent_type, task_desc, tokens, duration, outcome, notes):
    marker = "## Subagent Token Cost Log"
    next_marker = "\n## "
    idx = content.find(marker)
    if idx < 0:
        raise RuntimeError("no cost log heading")
    nxt = content.find(next_marker, idx + len(marker))
    section = content[idx:nxt] if nxt > 0 else content[idx:]
    # Count existing data rows (exclude header and separator lines)
    rows = [l for l in section.split("\n") if l.startswith("| ") and not l.startswith("| #") and not l.startswith("|--")]
    n = len(rows) + 1
    row = f"| {n} | {phase_n} | {subagent_type} | {task_desc or 'phase work'} | {tokens} | {duration} | {outcome} | {notes or '-'} |"
    # Use robust insert-point: find end of last markdown table row (lines starting
    # with '|') to avoid being tricked by '|' characters in the Rollup prose line.
    insert_at = _last_table_row_end(content, idx, nxt if nxt > 0 else len(content))
    return content[:insert_at + 1] + row + "\n" + content[insert_at + 1:]


def append_activity_row(content, phase, outcome, commit):
    """Append a row to the Agent Activity Log.

    Columns (v2 template): | Timestamp | Phase | Outcome | Commit |
    """
    marker = "## Agent Activity Log"
    next_marker = "\n## "
    idx = content.find(marker)
    if idx < 0:
        return content  # tolerate missing
    nxt = content.find(next_marker, idx + len(marker))
    now = datetime.datetime.now().astimezone()
    ts = now.strftime("%H:%M")
    row = f"| {ts} | {phase} | {outcome} | {commit or '--'} |"
    insert_at = _last_table_row_end(content, idx, nxt if nxt > 0 else len(content))
    return content[:insert_at + 1] + row + "\n" + content[insert_at + 1:]


def _find_heading(content, heading):
    """Index of `heading` where it actually starts a line, or -1.

    A bare content.find() also matches the heading text quoted inside prose or an
    HTML comment earlier in the document, which silently appends rows to whatever
    table follows that mention instead.  Caught in testing: the template's own
    Requirement comment names '## Decisions' and '## Detours'.
    """
    if content.startswith(heading):
        return 0
    idx = content.find("\n" + heading)
    return idx + 1 if idx >= 0 else -1


def _section_bounds(content, heading):
    """(start, end) of a section, end being the next line-start '## ' heading."""
    idx = _find_heading(content, heading)
    if idx < 0:
        return -1, -1
    nxt = content.find("\n## ", idx + len(heading))
    return idx, (nxt if nxt > 0 else len(content))


def split_cells(row):
    r"""Split a markdown table row into cells, honouring the \| escape _cell() writes.

    Every writer here escapes pipes so free text cannot add columns.  Before this
    existed no reader honoured that escape: a naive split("|") on a row containing
    an escaped pipe returns one cell too many, so positional writes land on the
    wrong field.  Concretely, closing a detour whose Proof contained a pipe
    overwrote the already-checked cell and left the detour open forever.

    Also tolerates CRLF and trailing whitespace, which strip("|") alone does not.
    """
    body = row.rstrip()
    if body.endswith("|"):
        body = body[:-1]
    if body.startswith("|"):
        body = body[1:]
    cells, cur, i = [], [], 0
    while i < len(body):
        ch = body[i]
        if ch == "\\" and i + 1 < len(body) and body[i + 1] in ("|", "\\"):
            cur.append(body[i + 1]); i += 2; continue
        if ch == "|":
            cells.append("".join(cur)); cur = []; i += 1; continue
        cur.append(ch); i += 1
    cells.append("".join(cur))
    return cells


def join_cells(cells):
    """Inverse of split_cells: re-escape and rebuild a row."""
    return "| " + " | ".join(_cell(c.strip()) for c in cells) + " |"


def _cell(text):
    """Escape free text for a pipe-delimited cell.  A raw '|' shifts every later
    column and the next find_table() raises on the column count."""
    if text is None:
        return "-"
    out = (str(text).replace("\\", "\\\\").replace("|", "\\|")
           .replace("\r", " ").replace("\n", " ").strip())
    return out or "-"


def _next_id(content, marker, prefix):
    """Next sequential id (e.g. DEC-3) for the table under `marker`."""
    idx, nxt = _section_bounds(content, marker)
    if idx < 0:
        raise RuntimeError(f"no '{marker}' heading")
    section = content[idx:nxt]
    n = 0
    for ln in section.split("\n"):
        m = re.match(r"^\|\s*" + re.escape(prefix) + r"(\d+)\s*\|", ln)
        if m:
            n = max(n, int(m.group(1)))
    return n + 1


def append_decision_row(content, decision, why, ruled_out):
    """Record an owner decision.  Its id becomes a legal Source value (DEC-<n>),
    which is how a phase nobody explicitly asked for can still be warranted."""
    marker = "## Decisions"
    idx, nxt = _section_bounds(content, marker)
    if idx < 0:
        raise RuntimeError("no Decisions heading")
    n = _next_id(content, marker, "DEC-")
    date = datetime.datetime.now().astimezone().strftime("%Y-%m-%d")
    row = f"| DEC-{n} | {date} | {_cell(decision)} | {_cell(why)} | {_cell(ruled_out)} |"
    insert_at = _last_table_row_end(content, idx, nxt if nxt > 0 else len(content))
    return content[:insert_at + 1] + row + "\n" + content[insert_at + 1:], f"DEC-{n}"


def append_detour_row(content, origin, blocks, proof, already_checked):
    """Open a detour.  `origin` is the discriminator between a real detour and drift:
    pre-existing/external means reality blocked us; phase-<n> means an earlier phase
    of this goal created the constraint, which is drift."""
    marker = "## Detours"
    idx, nxt = _section_bounds(content, marker)
    if idx < 0:
        raise RuntimeError("no Detours heading")
    n = _next_id(content, marker, "DET-")
    date = datetime.datetime.now().astimezone().strftime("%Y-%m-%d")
    row = (f"| DET-{n} | {date} | {_cell(origin)} | {_cell(blocks)} | "
           f"{_cell(proof)} | {_cell(already_checked)} | open |")
    insert_at = _last_table_row_end(content, idx, nxt if nxt > 0 else len(content))
    return content[:insert_at + 1] + row + "\n" + content[insert_at + 1:], f"DET-{n}"


def close_detour_row(content, detour_id):
    """Mark one detour closed.  finalize refuses while any detour is still open --
    that refusal is the return path: it will not let the goal end on a side quest."""
    date = datetime.datetime.now().astimezone().strftime("%Y-%m-%d")
    start, end = _section_bounds(content, "## Detours")
    if start < 0:
        raise RuntimeError("no Detours heading")
    lines = content.split("\n")
    # Bound the search to the Detours section: a matching id anywhere else in the
    # file (a quoted example, a copy in another table) must never be the row closed.
    first_line = content[:start].count("\n")
    last_line = content[:end].count("\n")
    hit = False
    for i in range(first_line, min(last_line + 1, len(lines))):
        if not lines[i].lstrip().startswith("|"):
            continue
        cells = split_cells(lines[i])
        if cells and cells[0].strip() == detour_id:
            if len(cells) < 7:
                raise RuntimeError(
                    f"detour row {detour_id} has {len(cells)} cells, expected 7")
            # Status is the LAST cell, not index 6. With an escaped pipe in Proof a
            # naive split put index 6 on the already-checked column, so closing a
            # detour overwrote that field and left the detour open forever.
            cells[-1] = f"closed:{date}"
            lines[i] = join_cells(cells)
            hit = True
            break
    if not hit:
        raise RuntimeError(f"detour {detour_id} not found in the Detours table")
    return "\n".join(lines)


def open_detours(content):
    """Ids of detours still open.  Empty list means the goal is back on its own path."""
    marker = "## Detours"
    idx, nxt = _section_bounds(content, marker)
    if idx < 0:
        return []
    section = content[idx:nxt]
    out = []
    for ln in section.split("\n"):
        if not ln.lstrip().startswith("|"):
            continue
        cells = split_cells(ln)
        if len(cells) >= 7 and re.match(r"^DET-\d+$", cells[0].strip()):
            # Status is the last cell. Reading it positionally at index 6 misreads
            # any row whose free text contained an escaped pipe.
            if cells[-1].strip() == "open":
                out.append(cells[0].strip())
    return out


def append_failure_row(content, phase_n, subagent, what_failed, recovery, lesson):
    marker = "## Failure Log"
    next_marker = "\n## "
    idx = content.find(marker)
    if idx < 0:
        raise RuntimeError("no failure log heading")
    nxt = content.find(next_marker, idx + len(marker))
    section = content[idx:nxt] if nxt > 0 else content[idx:]
    rows = [l for l in section.split("\n") if l.startswith("| ") and not l.startswith("| #") and not l.startswith("|--")]
    n = len(rows) + 1
    row = f"| {n} | {phase_n} | {subagent} | {what_failed} | {recovery or '-'} | {lesson or '-'} |"
    insert_at = _last_table_row_end(content, idx, nxt if nxt > 0 else len(content))
    return content[:insert_at + 1] + row + "\n" + content[insert_at + 1:]
