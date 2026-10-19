"""Shared readers for the run's state files, so every script parses them the same way.

Used by build_table.py, check_run.py, retro_metrics.py and run_state.py.
"""
import glob
import json
import os
from datetime import datetime, timezone

HEADER_WORDS = {"when", "#", "metric", "id"}  # first-cell words that mark a table's header row


def read_text(path):
    """File text, tolerant of a BOM and of bytes that are not UTF-8 (Windows PowerShell 5.1 writes ANSI)."""
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        return f.read()


def read_json_safe(path):
    """Parsed JSON, or None when the file is missing or half-written (a live journal or snapshot)."""
    try:
        return json.loads(read_text(path))
    except (OSError, ValueError):
        return None


def split_row(line):
    """Cells of one markdown table row; a pipe written as \\| stays inside its cell."""
    body = line.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|") and not body.endswith("\\|"):
        body = body[:-1]
    cells, cur, i = [], "", 0
    while i < len(body):
        if body[i] == "\\" and i + 1 < len(body) and body[i + 1] == "|":
            cur += "|"
            i += 2
            continue
        if body[i] == "|":
            cells.append(cur.strip())
            cur = ""
        else:
            cur += body[i]
        i += 1
    cells.append(cur.strip())
    return cells


def is_separator(cells):
    return all(c and set(c) <= set("-: ") for c in cells)


def table_rows(path):
    """Data rows of the markdown tables in a file: separator rows and header rows are skipped by
    content, never by position, so a file written without a header loses no row."""
    if not os.path.exists(path):
        return []
    rows = []
    for line in read_text(path).splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = split_row(line)
        if is_separator(cells) or cells[0].strip().lower() in HEADER_WORDS:
            continue
        rows.append(cells)
    return rows


def journal_dirs(inputs):
    """Workflow journal folders of every session this run has used (inputs.json "sessions"), so a
    resume in a new session keeps the earlier stages' history."""
    sessions = list(inputs.get("sessions") or [])
    if inputs.get("sessionId") and inputs["sessionId"] not in sessions:
        sessions.append(inputs["sessionId"])
    env = os.environ.get("CLAUDE_CODE_SESSION_ID")
    if env and env not in sessions:
        sessions.append(env)
    root = os.path.join(os.path.expanduser("~"), ".claude", "projects")
    dirs = []
    for sid in sessions:
        dirs += glob.glob(os.path.join(root, "*", sid, "workflows"))
    return dirs


def read_jsonl_safe(path):
    """Dicts of a .jsonl file; a half-written or damaged line is skipped, never raised."""
    entries = []
    for line in read_text(path).splitlines():
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if isinstance(entry, dict):
            entries.append(entry)
    return entries


def parse_time(text):
    """datetime (timezone-aware) from an ISO 8601 string; a time with no zone is read as UTC.
    Raises ValueError for text that is not a time."""
    parsed = datetime.fromisoformat(str(text).strip().replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def number(value):
    """int of a journal number that may be missing, a string, or junk: junk counts as 0."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def read_journals(dirs):
    """Readable wf_*.json journals of the given folders, oldest first. A half-written journal is skipped."""
    journals = []
    for folder in dirs:
        for path in glob.glob(os.path.join(folder, "wf_*.json")):
            journal = read_json_safe(path)
            if isinstance(journal, dict):
                journals.append(journal)
    journals.sort(key=lambda j: number(j.get("startTime")))
    return journals


def unique_agents(journals):
    """(agents, dropped): every workflow_agent entry once. A resumed workflow replays earlier agents
    under the same agentId, so the newest copy wins and the older copy goes to `dropped`. An agent
    with no agentId is always kept."""
    kept, dropped = [], []
    position = {}
    for journal in journals:
        for agent in journal.get("workflowProgress") or []:
            if not isinstance(agent, dict) or agent.get("type") != "workflow_agent":
                continue
            agent_id = agent.get("agentId")
            if agent_id and agent_id in position:
                dropped.append(kept[position[agent_id]])
                kept[position[agent_id]] = dict(agent, workflow=journal.get("workflowName", ""))
                continue
            if agent_id:
                position[agent_id] = len(kept)
            kept.append(dict(agent, workflow=journal.get("workflowName", "")))
    return kept, dropped
