import re

CHECKPOINT_HEADING = "## Last Known Good Checkpoint"

def update_checkpoint(content, last_phase_n, last_phase_title, last_commit, next_action):
    idx = content.find(CHECKPOINT_HEADING)
    if idx < 0:
        raise RuntimeError("no checkpoint heading")
    lines = content.split("\n")
    heading_idx = next(i for i, l in enumerate(lines) if l == CHECKPOINT_HEADING)
    # Find the table -- 4 value rows after the header line
    table_start = next(i for i in range(heading_idx, len(lines)) if lines[i].startswith("|"))
    # rows 0=header, 1=sep, 2..5 = data
    lines[table_start + 2] = f"| Last completed phase | Phase {last_phase_n} - {last_phase_title} |"
    lines[table_start + 3] = f"| Last successful commit | {last_commit or '(none yet)'} |"
    lines[table_start + 4] = f"| Next action | {next_action} |"
    return "\n".join(lines)
