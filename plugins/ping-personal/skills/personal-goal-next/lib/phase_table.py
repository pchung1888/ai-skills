import re
import sys
from pathlib import Path

PHASE_STATUS_HEADING = "## Phase Status"

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

def update_row(content, phase_num, new_status, new_commit, new_subagent):
    idx, start, end, header, sep, rows = find_table(content)
    matched = []
    for i, r in enumerate(rows):
        cells = [c.strip() for c in r.strip("|").split("|")]
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
    new_row = "| " + " | ".join(cells) + " |"
    rows[i] = new_row
    abs_lines = content.split("\n")
    abs_start = idx + sum(len(l) + 1 for l in content[:idx].split("\n")[:-1])
    # Splice rows back -- simpler: rebuild full content
    full_lines = content.split("\n")
    abs_offset = full_lines.index(header)
    for j, r in enumerate(rows):
        full_lines[abs_offset + 2 + j] = r
    return "\n".join(full_lines)
