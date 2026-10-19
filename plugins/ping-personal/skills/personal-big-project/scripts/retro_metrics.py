"""Measure a finished (or stopped) run for RETRO.md, so the retro starts from numbers, not memory.
Prints a markdown table, then a "Transcript sample for the retro" section. Reads only process files, never the work's content.

  python retro_metrics.py --state-dir docs/proj-123/autopilot --journals <dir> [--transcript <session>.jsonl]

Sources: workflow journals (wf_*.json; a resumed workflow's replayed agents count once), log/quota-log.md
(a pause is a row whose Action is exactly PAUSE), log/skill-friction.md, GOAL-BRIEF.md, run-state.json
(deferrals, agent vs owner), and the coordinator transcript (owner messages, questions asked, wall clock
from the latest timestamp, coordinator tokens from assistant message.usage after unattendedSince).
"""
import argparse
import os
import re

import statefiles

SAMPLE_SIZE = 5  # workflow agents the retro reads in full
SAMPLE_LARGEST = 3  # of those, the biggest by tokens; fix and gate agents come next, then more big ones
USAGE_FIELDS = ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")


def transcript_facts(path, since):
    """Owner messages, AskUserQuestion calls and coordinator token usage after `since`, plus the latest
    activity time. Returns (owner, asked, last, usage) with usage = {input, output, cacheRead, cacheWrite}.
    A streamed assistant message appears on several lines with the same message id; each id counts once
    (its largest figures)."""
    owner = asked = 0
    last = None
    per_message = {}
    for entry in statefiles.read_jsonl_safe(path):
        try:
            when = statefiles.parse_time(entry["timestamp"])
        except (KeyError, ValueError):
            continue
        if when < since:
            continue
        if last is None or when > last:
            last = when
        message = entry.get("message") if isinstance(entry.get("message"), dict) else {}
        content = message.get("content")
        if entry.get("type") == "user" and isinstance(content, str) and not entry.get("isMeta"):
            # Background notices start with "<"; tick and resume prompts carry these marker words.
            head = content.lstrip()[:160]
            if not head.startswith("<") and "30-minute tick" not in head and "resume: relaunch" not in head:
                owner += 1
        elif entry.get("type") == "assistant":
            if isinstance(content, list):
                asked += sum(1 for c in content if isinstance(c, dict) and c.get("type") == "tool_use"
                             and c.get("name") == "AskUserQuestion")
            usage = message.get("usage")
            if isinstance(usage, dict):
                key = message.get("id") or entry.get("uuid") or len(per_message)
                seen = per_message.setdefault(key, {})
                for field in USAGE_FIELDS:
                    seen[field] = max(seen.get(field, 0), statefiles.number(usage.get(field)))
    totals = {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0}
    for seen in per_message.values():
        totals["input"] += seen.get("input_tokens", 0)
        totals["output"] += seen.get("output_tokens", 0)
        totals["cacheRead"] += seen.get("cache_read_input_tokens", 0)
        totals["cacheWrite"] += seen.get("cache_creation_input_tokens", 0)
    return owner, asked, last, totals


def deferral_counts(state):
    """(by agents, by owner) from run-state.json task outcomes; None when run-state.json is unreadable."""
    run_state = statefiles.read_json_safe(os.path.join(state, "run-state.json"))
    if not isinstance(run_state, dict):
        return None
    by_agents = by_owner = 0
    for stage in run_state.get("stages") or []:
        for info in (stage.get("tasks") or {}).values():
            if isinstance(info, dict) and info.get("outcome") == "deferred":
                if info.get("deferredBy") == "owner":
                    by_owner += 1
                else:
                    by_agents += 1
    return by_agents, by_owner


def percent(cell):
    found = re.search(r"\d+", cell)
    return int(found.group(0)) if found else None


def transcript_sample(agents, journal_dirs):
    """Markdown section naming up to SAMPLE_SIZE workflow agents whose raw transcripts the retro should read:
    the SAMPLE_LARGEST biggest by tokens, then every agent whose label has :fix or :gate (largest first), then
    more big ones if a slot is left. A transcript is expected
    as a file whose NAME contains the agentId, anywhere under the session folder (the parent of a journal
    folder); "not found" is printed when there is none."""
    by_tokens = sorted(agents, key=lambda a: -statefiles.number(a.get("tokens")))
    trouble = [a for a in by_tokens if ":fix" in a.get("label", "") or ":gate" in a.get("label", "")]
    chosen = []
    for a in by_tokens[:SAMPLE_LARGEST] + trouble + by_tokens:  # the rest of by_tokens only fills free slots
        if not any(a is c for c in chosen):
            chosen.append(a)
    sessions = sorted({os.path.dirname(os.path.normpath(d)) for d in journal_dirs})
    files = [os.path.join(root, f) for session in sessions if os.path.isdir(session)
             for root, _, names in os.walk(session) for f in names]
    lines = ["", "## Transcript sample for the retro", "",
             "Read these agents' raw transcripts and note the friction nobody logged (agents hide friction).",
             f"Transcripts are expected as a file named after the agentId under: {', '.join(sessions) or 'no session folder known'}",
             "", "| Agent label | Tokens | agentId | Transcript file |", "|---|---|---|---|"]
    for a in chosen[:SAMPLE_SIZE]:
        agent_id = str(a.get("agentId") or "")
        hit = next((f for f in files if agent_id and agent_id in os.path.basename(f)), None)
        lines.append(f"| {a.get('label', '?')} | {statefiles.number(a.get('tokens')):,} | {agent_id or 'no agentId'} | "
                     f"{hit or 'not found'} |")
    if not chosen:
        lines.append("| none | 0 | - | not found |")
    return "\n".join(lines) + "\n"


def metrics(state, journal_dirs, transcript):
    inputs = statefiles.read_json_safe(os.path.join(state, "inputs.json"))
    inputs = inputs if isinstance(inputs, dict) else {}
    rows = []

    journals = statefiles.read_journals(journal_dirs)
    agents, dropped = statefiles.unique_agents(journals)
    total = sum(statefiles.number(j.get("totalTokens")) for j in journals)
    total -= sum(statefiles.number(a.get("tokens")) for a in dropped)  # a resumed workflow replays agents
    rows.append(("Stages (workflows)", str(len(journals))))
    rows.append(("Workflow agents", str(len(agents))))
    rows.append(("Workflow tokens", f"{total:,}"))
    for j in journals:
        hours = statefiles.number(j.get("durationMs")) / 3_600_000
        rows.append((f"  {j.get('workflowName', '?')}", f"{statefiles.number(j.get('totalTokens')):,} tokens, "
                     f"{hours:.1f} h, {j.get('status', '?')}"))
    fixes = sum(1 for a in agents if ":fix" in a.get("label", "") or "-fix" in a.get("label", ""))
    gates = len({a["label"].split(":gate")[0] for a in agents if ":gate" in a.get("label", "")})
    rows.append(("Fix attempts / critic gates", f"{fixes} / {gates}"))

    quota = statefiles.table_rows(os.path.join(state, "log", "quota-log.md"))
    five = [percent(r[1]) for r in quota if len(r) > 2 and percent(r[1]) is not None]
    week = [percent(r[2]) for r in quota if len(r) > 2 and percent(r[2]) is not None]
    pauses = sum(1 for r in quota if len(r) > 4 and r[4].strip() == "PAUSE")
    rows.append(("Ticks (quota-log rows) / pauses", f"{len(quota)} / {pauses}"))
    rows.append(("5h window peak", f"{max(five)}%" if five else "don't know"))
    rows.append(("Weekly start -> end", f"{week[0]}% -> {week[-1]}%" if week else "don't know"))

    friction = statefiles.table_rows(os.path.join(state, "log", "skill-friction.md"))
    rows.append(("Skill friction rows (workarounds)", str(len(friction))))
    deferrals = deferral_counts(state)
    if deferrals is None:
        rows.append(("Deferrals (by agents / by owner)", "don't know (run-state.json unreadable)"))
    else:
        rows.append(("Deferrals (by agents / by owner)", f"{deferrals[0]} / {deferrals[1]}"))
    brief = os.path.join(state, "GOAL-BRIEF.md")
    found = re.search(r"Corrections before approval:\s*(\d+)", statefiles.read_text(brief)) if os.path.exists(brief) else None
    rows.append(("Goal-brief corrections at the door", found.group(1) if found else "don't know"))

    since = None
    if inputs.get("unattendedSince"):
        try:
            since = statefiles.parse_time(inputs["unattendedSince"])
        except ValueError:
            since = None
    if transcript and since and os.path.isfile(transcript):
        owner, asked, last, usage = transcript_facts(transcript, since)
        rows.append(("Owner messages while unattended", str(owner)))
        rows.append(("Questions asked while unattended", str(asked)))
        rows.append(("Wall clock unattended", f"{(last - since).total_seconds() / 3600:.1f} h" if last else "don't know"))
        rows.append(("Coordinator tokens: input", f"{usage['input']:,}"))
        rows.append(("Coordinator tokens: output", f"{usage['output']:,}"))
        rows.append(("Coordinator tokens: cache read", f"{usage['cacheRead']:,}"))
        rows.append(("Coordinator tokens: cache write", f"{usage['cacheWrite']:,}"))
    else:
        rows.append(("Owner messages / questions / wall clock / coordinator tokens",
                     "don't know (no transcript or unattendedSince)"))

    return ("| Metric | Value |\n|---|---|\n" + "\n".join(f"| {k} | {v} |" for k, v in rows) + "\n"
            + transcript_sample(agents, journal_dirs))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--state-dir", required=True, help="state folder. Example: docs/proj-123/autopilot")
    ap.add_argument("--journals", nargs="*", default=None, help="folders holding wf_*.json; default: every session in inputs.json. Example: ~/.claude/projects/<proj>/<session>/workflows")
    ap.add_argument("--transcript", help="coordinator transcript .jsonl. Example: ~/.claude/projects/<proj>/<session>.jsonl")
    a = ap.parse_args()
    dirs = a.journals
    if dirs is None:
        run_inputs = statefiles.read_json_safe(os.path.join(a.state_dir, "inputs.json"))
        dirs = statefiles.journal_dirs(run_inputs if isinstance(run_inputs, dict) else {})
    print(metrics(a.state_dir, dirs, a.transcript), end="")
