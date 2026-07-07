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
