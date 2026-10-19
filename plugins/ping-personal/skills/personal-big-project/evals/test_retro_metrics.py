"""Self-check for scripts/retro_metrics.py: wall clock from the latest timestamp, coordinator tokens
from assistant message.usage, a pause is Action == PAUSE exactly, deferrals from run-state.json,
resumed-workflow agents counted once. Run: python evals/test_retro_metrics.py   Prints RETRO METRICS TEST PASS."""
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import retro_metrics  # noqa: E402


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def assistant(when, message_id, usage, tools=()):
    content = [{"type": "tool_use", "name": n} for n in tools] or [{"type": "text", "text": "x"}]
    return json.dumps({"type": "assistant", "timestamp": when,
                       "message": {"id": message_id, "content": content, "usage": usage}}) + "\n"


def value(table, metric):
    hit = [l for l in table.splitlines() if l.startswith(f"| {metric} |")]
    assert len(hit) == 1, f"expected one row for {metric}, got {hit}"
    return hit[0].split("|")[2].strip()


def main():
    tmp = tempfile.mkdtemp()
    try:
        state = os.path.join(tmp, "autopilot")
        write(os.path.join(state, "inputs.json"), json.dumps({"unattendedSince": "2026-10-17T00:00:00"}))  # naive = UTC
        write(os.path.join(state, "log", "quota-log.md"),
              "| Sat 10-17 01:00 | 10% | 5% | 2026-10-17T05:00:00Z | LAUNCH |\n"
              "| Sat 10-17 01:30 | 50% | 6% | 2026-10-17T05:00:00Z | WAIT |\n"
              "| Sat 10-17 02:00 | 91% | 7% | 2026-10-17T05:00:00Z | PAUSE |\n"
              "| Sat 10-17 02:30 | 20% | 8% | 2026-10-17T05:00:00Z | WAIT (no PAUSE needed) |\n")
        write(os.path.join(state, "run-state.json"), json.dumps({"stages": [{"name": "s1", "tasks": {
            "T1": {"outcome": "deferred", "deferredBy": "agent"}, "T2": {"outcome": "deferred", "deferredBy": "agent"},
            "T3": {"outcome": "deferred", "deferredBy": "owner"}, "T4": {"outcome": "passed"}}}]}))
        # The latest timestamp (04:00) comes first in the file; the last line is earlier (01:00).
        usage_a = {"input_tokens": 5, "output_tokens": 100, "cache_read_input_tokens": 1000, "cache_creation_input_tokens": 200}
        usage_a_final = dict(usage_a, output_tokens=150)
        transcript = os.path.join(tmp, "t.jsonl")
        write(transcript,
              assistant("2026-10-17T04:00:00.000Z", "msg_late", {"input_tokens": 1, "output_tokens": 2, "cache_read_input_tokens": 3, "cache_creation_input_tokens": 4})
              + assistant("2026-10-16T23:00:00.000Z", "msg_before", {"input_tokens": 999, "output_tokens": 999})
              + assistant("2026-10-17T01:00:00.000Z", "msg_a", usage_a)
              + assistant("2026-10-17T01:00:01.000Z", "msg_a", usage_a_final, tools=("AskUserQuestion",))
              + '{"type": "assistant", "timestamp": "2026-10-17T01:00:')  # half-written last line
        journals = os.path.join(tmp, "wf")
        for name, tokens in (("wf_1.json", 1000), ("wf_2.json", 500)):
            write(os.path.join(journals, name), json.dumps({
                "workflowName": name, "startTime": "1" if name == "wf_1.json" else "2", "totalTokens": tokens,
                "workflowProgress": [{"type": "workflow_agent", "label": "T1", "agentId": "same", "tokens": 400, "state": "done"}]}))

        table = retro_metrics.metrics(state, [journals], transcript)
        assert value(table, "Wall clock unattended") == "4.0 h", table  # max timestamp, not file order
        assert value(table, "Coordinator tokens: input") == "6", table  # msg_a once + msg_late; msg_before is too early
        assert value(table, "Coordinator tokens: output") == "152", table  # msg_a counted at its final 150
        assert value(table, "Coordinator tokens: cache read") == "1,003", table
        assert value(table, "Coordinator tokens: cache write") == "204", table
        assert value(table, "Questions asked while unattended") == "1", table
        assert value(table, "Ticks (quota-log rows) / pauses") == "4 / 1", table  # only Action == PAUSE
        assert value(table, "5h window peak") == "91%", table
        assert value(table, "Deferrals (by agents / by owner)") == "2 / 1", table
        assert value(table, "Workflow agents") == "1", table  # the replayed agent counts once
        assert value(table, "Workflow tokens") == "1,100", table  # 1500 minus the dropped copy's 400

        # Item 15: the transcript sample lists 3 biggest agents, then :fix / :gate agents, up to 5, with where
        # their transcript file is expected ("not found" when none is under the session folder).
        sess = os.path.join(tmp, "sess1")
        agents = [("A", 900, "id-a"), ("B", 800, "id-b"), ("C", 700, "id-c"), ("D", 600, "id-d"), ("E", 500, "id-e"),
                  ("T1:fix", 10, "id-fix"), ("T2:gate:rhea", 5, "id-gate"), ("T3:fix2", 1, "id-fix2")]
        write(os.path.join(sess, "workflows", "wf_9.json"), json.dumps({
            "workflowName": "wf_9", "startTime": "9", "totalTokens": 0,
            "workflowProgress": [{"type": "workflow_agent", "label": l, "agentId": i, "tokens": t} for l, t, i in agents]}))
        write(os.path.join(sess, "subagents", "agent-id-a.jsonl"), "{}\n")
        sample = retro_metrics.metrics(state, [os.path.join(sess, "workflows")], None).split("## Transcript sample for the retro")[1]
        rows = [l.split("|")[1:5] for l in sample.splitlines() if l.startswith("| ") and "Agent label" not in l]
        labels = [r[0].strip() for r in rows]
        assert labels == ["A", "B", "C", "T1:fix", "T2:gate:rhea"], labels  # 3 biggest, then fix and gate; D, E and T3:fix2 cut
        assert rows[0][1].strip() == "900" and rows[0][2].strip() == "id-a", rows[0]
        assert rows[0][3].strip().endswith("agent-id-a.jsonl"), rows[0]  # found under the session folder
        assert rows[1][3].strip() == "not found", rows[1]  # honest when there is no file
        assert sess in sample, "the expected location is printed"
        # Fewer than 5 fix/gate-or-big agents: the next largest fill the free slots.
        write(os.path.join(sess, "workflows", "wf_9.json"), json.dumps({
            "workflowName": "wf_9", "startTime": "9", "totalTokens": 0,
            "workflowProgress": [{"type": "workflow_agent", "label": l, "agentId": i, "tokens": t} for l, t, i in agents[:5]]}))
        sample = retro_metrics.metrics(state, [os.path.join(sess, "workflows")], None).split("## Transcript sample for the retro")[1]
        assert [l.split("|")[1].strip() for l in sample.splitlines() if l.startswith("| ") and "Agent label" not in l] == list("ABCDE"), sample
        # An agent with no agentId is listed honestly.
        write(os.path.join(sess, "workflows", "wf_9.json"), json.dumps({
            "workflowName": "wf_9", "startTime": "9", "totalTokens": 0,
            "workflowProgress": [{"type": "workflow_agent", "label": "Z", "tokens": 5}]}))
        sample = retro_metrics.metrics(state, [os.path.join(sess, "workflows")], None)
        assert "| Z | 5 | no agentId | not found |" in sample, sample

        # Without a transcript the coordinator figures are "don't know", never zero.
        bare = retro_metrics.metrics(state, [journals], None)
        assert "Coordinator tokens: input" not in bare and "don't know" in bare, bare
        # A half-written run-state.json gives "don't know" for deferrals instead of a crash.
        write(os.path.join(state, "run-state.json"), '{"stages": [')
        assert "don't know (run-state.json unreadable)" in retro_metrics.metrics(state, [journals], transcript)
        print("RETRO METRICS TEST PASS")
    finally:
        shutil.rmtree(tmp)


if __name__ == "__main__":
    main()
