#!/usr/bin/env python3
"""stop_eval.py -- evaluate crisp STOP conditions for a loop tick.

THE GATE LAW (see SKILL.md): the stop gate MUST be co-extensive with the goal,
and there is exactly ONE authoritative completion gate per run:
  - campaign / multi-artifact goal -> all-goals-done is authoritative;
    accept_cmd (if any) is a PER-CHILD health check, NEVER the run-level stop.
  - single-artifact goal           -> accept_cmd-green is authoritative.
It was the inverse (a one-file accept_cmd halting a multi-message goal after the
first deliverable) that caused the reported one-unit-per-fire stutter.

Precedence (highest first):
    gate-error          single-artifact accept_cmd could not run (fail loud)
    child-gate-error    campaign: the current child's gate could not run (fail loud)
    all-goals-done      campaign mode: the ONE authoritative completion gate
    accept_cmd-green    single-artifact mode: the ONE authoritative gate
    fuzzy-judge-pass    declared fuzzy STOP; verdict supplied by the driver
    no-progress         k identical tick signatures (fold a monotone progress
                        marker into every signature so real progress always
                        changes it -- see progress_hash.py / SKILL.md)
    iters               iteration ceiling
    budget-spent        token ceiling
    deadline            wall-clock deadline passed (timer-cadence equivalent of
                        all-goals-done; the driver computes deadline_passed)
    run-ceiling         cumulative run count reached (across Task Scheduler fires)

secrets-HALT and fence-HALT outrank everything here but are enforced by the
driver BEFORE stop_eval runs (see SKILL.md "Halt precedence").

A broken gate is detected by exit code: shell convention 126 = found-but-not-
executable, 127 = command-not-found, 128+n = killed by signal n. Any
accept_exit >= 126 means the gate never evaluated the goal. accept_cmd MUST exit
0 (done) / small nonzero (not done yet) and never be wrapped in a killer such as
`timeout` (whose 124 would read as "not done"); see SKILL.md gate-error note.
"""
import argparse, json, sys
import progress_hash

GATE_ERROR_FLOOR = 126

REASON_GLOSS = {
    "gate-error": "the acceptance command did not run (broken gate) -- fix the command",
    "child-gate-error": "the current campaign child's gate did not run -- fix that child's accept_cmd",
    "all-goals-done": "every campaign child goal reached done",
    "accept_cmd-green": "the acceptance command exited 0",
    "fuzzy-judge-pass": "the declared fuzzy-judge verdict reached pass",
    "no-progress": "no change in the tick signature for k consecutive ticks",
    "iters": "iteration ceiling reached",
    "budget-spent": "token ceiling reached",
    "deadline": "wall-clock deadline passed",
    "run-ceiling": "cumulative run count reached",
    "continue": "no stop condition met",
}


def _gate_errored(accept_exit) -> bool:
    return isinstance(accept_exit, int) and accept_exit >= GATE_ERROR_FLOOR


def evaluate_stop(state: dict) -> tuple[bool, str]:
    accept_exit = state.get("accept_exit")
    total = state.get("goals_total", 0)
    done = state.get("goals_done", 0)

    # exactly ONE authoritative completion gate, chosen by mode (THE GATE LAW):
    if total:
        # campaign: a broken CHILD gate fails loud before the completion check.
        if _gate_errored(state.get("child_accept_exit")):
            return True, "child-gate-error"
        if done >= total:
            return True, "all-goals-done"
    else:
        # single-artifact: a broken gate fails loud; exit 0 completes.
        if _gate_errored(accept_exit):
            return True, "gate-error"
        if accept_exit == 0:
            return True, "accept_cmd-green"

    # declared fuzzy-judge STOP: the driver runs a judge against the written
    # rubric each tick and supplies the verdict. "pass" completes the goal.
    if state.get("fuzzy_verdict") == "pass":
        return True, "fuzzy-judge-pass"

    # no-progress: k identical tick signatures. Progress is judged purely from
    # the signature history (no separate, unenforceable progress_made flag): the
    # driver MUST fold a monotone progress marker (goals_done / artifact count)
    # into every signature, so a tick that truly advanced changes the signature
    # and is not a stall. A genuinely identical signature k times IS a stall.
    sigs = state.get("signatures", [])
    k = state.get("no_progress_k", 3)
    if progress_hash.is_no_progress(sigs, k):
        return True, "no-progress"

    if state.get("iters", 0) >= state.get("max_iters", 0) > 0:
        return True, "iters"

    ceiling = state.get("token_ceiling", 0)
    if ceiling and state.get("tokens_spent", 0) >= ceiling:
        return True, "budget-spent"

    # long-horizon caps for the timer-cadence path (a --every chore has no
    # all-goals-done; these stop it ever running forever).
    if state.get("deadline_passed"):
        return True, "deadline"
    rc = state.get("runs_ceiling", 0)
    if rc and state.get("runs_total", 0) >= rc:
        return True, "run-ceiling"

    return False, "continue"


def stop_detail(state: dict) -> dict:
    """Structured result so the REPORT always shows PROGRESS, not a bare code.
    A 'no-progress' halt at 2/5 reads as 'stalled at 2 of 5 (next: goal-c)',
    never as a total failure that invites an unnecessary full re-run."""
    stop, reason = evaluate_stop(state)
    total = state.get("goals_total", 0)
    done = state.get("goals_done", 0)
    return {
        "stop": stop,
        "reason": reason,
        "gloss": REASON_GLOSS.get(reason, ""),
        "goals_done": done,
        "goals_total": total,
        "remaining": max(0, total - done) if total else None,
        "next_pending": state.get("next_pending", ""),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", required=True)
    a = ap.parse_args()
    print(json.dumps(stop_detail(json.loads(a.state))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
