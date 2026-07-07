#!/usr/bin/env python3
"""orchestrate.py -- decompose+route dispatcher + bounded-tree guards.

route() is DETERMINISTIC over typed features the model extracts; a model
override is recorded separately in the tracker and is NOT this function's
concern (spec S4.1). check_depth enforces the depth-2 cap on a PARENT-INJECTED
immutable depth (never read from the untrusted tracker -- spec S4.2). check_width
counts TOTAL live descendants charged to the root ledger, per CLAUDE.md Process
Budget Discipline.
"""

def route(features):
    """Map typed features -> a dispatch target. Features: n_steps, n_domains,
    has_own_gate, long_horizon, multi_phase, est_tokens, external_actions."""
    n_steps = features.get("n_steps", 1)
    n_domains = features.get("n_domains", 1)
    if features.get("has_own_gate") and features.get("long_horizon"):
        return {"target": "personal-loop", "reason": "long-horizon, own gate -> nested loop (depth-2 cap)"}
    if n_domains > 1 or features.get("multi_phase"):
        return {"target": "personal-workflow", "reason": "multi-phase / multi-domain -> conductor"}
    if n_steps > 1:
        return {"target": "personal-goal", "reason": "multi-step, single-domain -> inner goal"}
    return {"target": "subagent", "reason": "single-shot -> bare subagent"}


def check_depth(injected_depth):
    """Refuse a nested-loop spawn at depth >= 2. injected_depth is the parent-
    injected IMMUTABLE value, NEVER read from the tracker (a self-reported
    Depth:0 would unlock a fork-bomb)."""
    return ["depth-cap"] if injected_depth >= 2 else []


# (ceiling, verdict) walked low->high; first match wins, else "stop".
_WIDTH_NORMAL = ((3, "free"), (6, "confirm"))
_WIDTH_CONCURRENT = ((1, "free"), (3, "confirm"))


def check_width(live_descendants, other_session=False):
    """Total live descendants charged to the root ledger -> free/confirm/stop.
    Per CLAUDE.md: normal {1 free, 2-3 fine, 4-6 confirm, 7+ stop} collapses to
    free<=3 / confirm<=6 / stop; concurrent session tightens to
    free<=1 / confirm<=3 / stop."""
    table = _WIDTH_CONCURRENT if other_session else _WIDTH_NORMAL
    for ceiling, verdict in table:
        if live_descendants <= ceiling:
            return verdict
    return "stop"
