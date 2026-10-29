"""Measure a finished (or stopped) run for RETRO.md, so the retro starts from numbers, not memory.
Prints a markdown table, then a "Transcript sample for the retro" section. Reads only process files, never the work's content.

  python retro_metrics.py --state-dir docs/proj-123/autopilot --journals <dir> [--transcript <session>.jsonl]
         [--json <state-dir>/metrics.json --goal-kind "<kind of goal>" --skill-version <x.y.z>]
--json also writes the scorecard metrics (references/scorecard.json ids) for scripts/scorecard.py.

Sources: workflow journals (wf_*.json; a resumed workflow's replayed agents count once), log/quota-log.md
(a pause is a row whose Action is exactly PAUSE), log/skill-friction.md, GOAL-BRIEF.md, run-state.json
(deferrals, agent vs owner), and the coordinator transcript (owner messages, questions asked, wall clock
from the latest timestamp, coordinator tokens from assistant message.usage after unattendedSince).
"""
import argparse
import glob
import json
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
        if statefiles.is_owner_message(entry):
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


SCHEMA_VERSION = 1
COST = re.compile(r"Cost estimate:\s*([\d.]+)\s*([KkMm]?)\s*-\s*([\d.]+)\s*([KkMm]?)")
DAY_TIME = re.compile(r"^\w{3} (\d\d)-(\d\d) (\d\d):(\d\d)$")


def _tokens(number, unit):
    return float(number) * {"k": 1e3, "m": 1e6}.get(unit.lower(), 1)


def _share(part, whole):
    return round(part / whole, 3) if whole else None


def _check_line(lines, name):
    """(PASS|FAIL, message) of one check in log/run-check.txt, or (None, '') when it is not there."""
    for line in lines:
        if line.startswith(f"PASS {name}"):
            return "PASS", ""
        if line.startswith(f"FAIL {name}:"):
            return "FAIL", line
    return None, ""


def metrics_json(state, journal_dirs, transcript):
    """The scorecard metrics of one run (references/scorecard.json ids), each from a named file. A metric
    whose source is missing is null (UNKNOWN), never 0. Owner-message counts stay raw; scorecard.py turns
    them into per-10-hour rates."""
    inputs = statefiles.read_json_safe(os.path.join(state, "inputs.json"))
    inputs = inputs if isinstance(inputs, dict) else {}
    out = []

    def add(mid, value, unit, source):
        out.append({"id": mid, "value": value, "unit": unit, "label": "UNKNOWN" if value is None else "EXTRACTED",
                    "source": source})

    since = hours = None
    try:
        since = statefiles.parse_time(inputs["unattendedSince"])
    except (KeyError, ValueError, TypeError):
        pass
    if transcript and since and os.path.isfile(transcript):
        last = transcript_facts(transcript, since)[2]
        hours = round((last - since).total_seconds() / 3600, 1) if last else None

    fb_path = os.path.join(state, "log", "owner-feedback.md")
    fb = [r for r in statefiles.table_rows(fb_path) if len(r) >= 6] if os.path.exists(fb_path) else None
    count = (lambda cls: sum(1 for r in fb if r[1] == cls)) if fb is not None else (lambda cls: None)
    score = next((int(r[4]) for r in reversed(fb or []) if r[1] == "score" and r[4].strip() in "12345" and r[4].strip()), None)
    add("ownerScore", score, "1-5", "log/owner-feedback.md score row")

    run_state = statefiles.read_json_safe(os.path.join(state, "run-state.json"))
    run_state = run_state if isinstance(run_state, dict) else {}
    verdict = str(run_state.get("verdict") or "")
    found = re.search(r"(\d+) deferred", verdict)
    add("verdict", ("all" if found and found.group(1) == "0" else "deferred") if verdict.startswith("PASS")
        else "stopped" if verdict.startswith("STOPPED") else None, "", "run-state.json verdict")
    tasks = [t for s in run_state.get("stages") or [] for t in (s.get("tasks") or {}).values() if isinstance(t, dict)]
    owner_deferred = sum(1 for t in tasks if t.get("outcome") == "deferred" and t.get("deferredBy") == "owner")
    passed = sum(1 for t in tasks if t.get("outcome") == "passed")
    add("tasksFinished", _share(passed, len(tasks) - owner_deferred), "share", "run-state.json outcomes, owner deferrals left out")
    add("premature", count("premature"), "count", "log/owner-feedback.md class premature")

    times = []
    for r in statefiles.table_rows(os.path.join(state, "log", "status-log.md")):
        m = DAY_TIME.match(r[0])
        if m:
            mo, d, h, mi = (int(x) for x in m.groups())
            times.append(((mo * 31 + d) * 24 + h) * 60 + mi)  # minutes; only the gaps matter
    every = (inputs.get("report") or {}).get("everyMin", 30) if isinstance(inputs.get("report"), dict) else 30
    gap = max((b - a for a, b in zip(sorted(times), sorted(times)[1:])), default=None) if len(times) > 1 else None
    add("statusGap", round(gap / every, 2) if gap is not None else None, "ticks", "log/status-log.md, one row per Now rewrite")

    add("complaints", count("complaint"), "count", "log/owner-feedback.md class complaint")
    reports = sorted(glob.glob(os.path.join(state, "reports", "*.md")))
    ticks = len(statefiles.table_rows(os.path.join(state, "log", "quota-log.md")))
    add("reportsOnTime", min(1.0, round(len(reports) / ticks, 3)) if ticks else None, "share", "reports/ vs quota-log.md ticks")
    style = (inputs.get("report") or {}).get("style") if isinstance(inputs.get("report"), dict) else None
    failed_load = any(statefiles.read_text(p).lstrip().startswith("copilot talk did not load") for p in reports)
    add("copilotLoaded", ("no" if failed_load else "yes" if reports else None) if style == "copilot" else "n/a", "",
        "reports/ first line")

    journals = statefiles.read_journals(journal_dirs)
    agents, dropped = statefiles.unique_agents(journals)
    total = sum(statefiles.number(j.get("totalTokens")) for j in journals) - sum(statefiles.number(a.get("tokens")) for a in dropped)
    status_text = statefiles.read_text(os.path.join(state, "STATUS.md")) if os.path.exists(os.path.join(state, "STATUS.md")) else ""
    incident_rules = sum(1 for line in status_text.splitlines() if line.lstrip().startswith("- ") and "incident:" in line)
    gate_tasks = len({a["label"].split(":gate")[0] for a in agents if ":gate" in a.get("label", "")})
    fixes = count("fix")
    caught = incident_rules + gate_tasks
    add("selfCaughtShare", _share(caught, caught + fixes) if fixes is not None else None, "share",
        "STATUS.md rules with incident:, critic gates vs owner fix rows")

    check_lines = statefiles.read_text(os.path.join(state, "log", "run-check.txt")).splitlines() \
        if os.path.exists(os.path.join(state, "log", "run-check.txt")) else []
    side, side_msg = _check_line(check_lines, "side-effects")
    base, base_msg = _check_line(check_lines, "baselines")
    tags, tags_msg = _check_line(check_lines, "remote-tags")
    heads, heads_msg = _check_line(check_lines, "remote-branches")
    cap = None if side is None else "FAIL" if "> cap" in side_msg else "PASS"
    baseline = None if base is None else "FAIL" if "changed after capture" in base_msg else "PASS"
    pushed = None if None in (tags, heads) else "FAIL" if ("added or moved" in tags_msg or "differ" in heads_msg) else \
        "PASS" if (tags, heads) == ("PASS", "PASS") else None
    start, end = inputs.get("reviewsAtStart"), inputs.get("reviewsAtEnd")
    allowed = set(inputs.get("reviewsChangedByOwner") or [])
    external = None
    if isinstance(start, dict) and isinstance(end, dict):
        changed = [k for k, v in start.items() if v == "open" and end.get(k) in ("merged", "closed") and k not in allowed]
        external = "FAIL" if changed else "PASS"

    decisions = statefiles.read_text(os.path.join(state, "log", "decisions.md")) if os.path.exists(os.path.join(state, "log", "decisions.md")) else ""
    stops = decisions.count("self-stop:")
    risk = stops or (count("premature") or 0) or "FAIL" in (cap, baseline, pushed, external)
    add("selfStops", "stopped" if stops else "missed" if risk else "n/a", "", "log/decisions.md self-stop: rows")
    add("steering", count("steer"), "count", "log/owner-feedback.md class steer")

    if journals:
        by_name = {}
        for j in journals:
            by_name.setdefault(j.get("workflowName", "?"), []).append(j)
        earlier = sum(statefiles.number(j.get("totalTokens")) for js in by_name.values() for j in js[:-1])
        kept_ids = {id(j) for js in by_name.values() for j in js[-1:]}
        fix_tokens = sum(statefiles.number(a.get("tokens")) for j in journals if id(j) in kept_ids
                         for a in j.get("workflowProgress") or [] if isinstance(a, dict) and ":fix" in str(a.get("label", "")))
        add("reworkShare", _share(earlier + fix_tokens, total), "share", "journals: earlier attempts of a stage + :fix agents")
        add("verifierShare", _share(sum(statefiles.number(a.get("tokens")) for a in agents if ":verify" in a.get("label", "")), total),
            "share", "journals: :verify agents")
    else:
        add("reworkShare", None, "share", "journals")
        add("verifierShare", None, "share", "journals")
    brief = os.path.join(state, "GOAL-BRIEF.md")
    found = COST.search(statefiles.read_text(brief)) if os.path.exists(brief) else None
    mid = (_tokens(found.group(1), found.group(2) or found.group(4)) + _tokens(found.group(3), found.group(4))) / 2 if found else 0
    add("estimateRatio", round(total / mid, 3) if found and mid and total else None, "ratio", "GOAL-BRIEF.md Cost estimate line")

    complaint_rows = [r for r in fb or [] if r[1] in ("fix", "complaint")]
    filed_text = "".join(statefiles.read_text(os.path.join(state, p)) for p in ("log/skill-friction.md", "RETRO.md")
                         if os.path.exists(os.path.join(state, p)))
    add("complaintsFiled", _share(sum(1 for r in complaint_rows if r[2] and r[2] in filed_text), len(complaint_rows)), "share",
        "owner-feedback.md skill column vs skill-friction.md and RETRO.md")
    for mid, value in (("capOverrun", cap), ("protectedPush", pushed), ("baselineChanged", baseline), ("externalState", external)):
        add(mid, value, "", "log/run-check.txt" if mid != "externalState" else "inputs.json reviewsAtStart / reviewsAtEnd")

    by_skill = {}
    for r in complaint_rows:
        by_skill[r[2]] = by_skill.get(r[2], 0) + 1
    return {"schemaVersion": SCHEMA_VERSION, "runId": os.path.basename(os.path.normpath(state)),
            "runDate": since.strftime("%Y-%m-%d") if since else None, "goalKind": None,
            "skillVersion": None, "scorecardVersion": None, "unattendedHours": hours, "backfilled": False,
            "metrics": out, "complaintsBySkill": by_skill}


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
    for m in metrics_json(state, journal_dirs, transcript)["metrics"]:
        rows.append((f"scorecard: {m['id']}", "don't know" if m["value"] is None else m["value"]))

    return ("| Metric | Value |\n|---|---|\n" + "\n".join(f"| {k} | {v} |" for k, v in rows) + "\n"
            + transcript_sample(agents, journal_dirs))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--state-dir", required=True, help="state folder. Example: docs/proj-123/autopilot")
    ap.add_argument("--journals", nargs="*", default=None, help="folders holding wf_*.json; default: every session in inputs.json. Example: ~/.claude/projects/<proj>/<session>/workflows")
    ap.add_argument("--transcript", help="coordinator transcript .jsonl. Example: ~/.claude/projects/<proj>/<session>.jsonl")
    ap.add_argument("--json", help="also write the scorecard metrics here. Example: docs/proj-123/autopilot/metrics.json")
    ap.add_argument("--goal-kind", default=None, help="--json: one-line kind of goal, no project names. Example: answer review comments")
    ap.add_argument("--skill-version", default=None, help="--json: plugin version from the cache path. Example: 0.43.0")
    a = ap.parse_args()
    dirs = a.journals
    if dirs is None:
        run_inputs = statefiles.read_json_safe(os.path.join(a.state_dir, "inputs.json"))
        dirs = statefiles.journal_dirs(run_inputs if isinstance(run_inputs, dict) else {})
    print(metrics(a.state_dir, dirs, a.transcript), end="")
    if a.json:
        doc = metrics_json(a.state_dir, dirs, a.transcript)
        card = statefiles.read_json_safe(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                                      "references", "scorecard.json")) or {}
        doc.update(goalKind=a.goal_kind, skillVersion=a.skill_version, scorecardVersion=card.get("version"))
        with open(a.json, "w", encoding="utf-8", newline="\n") as f:
            json.dump(doc, f, indent=2)
