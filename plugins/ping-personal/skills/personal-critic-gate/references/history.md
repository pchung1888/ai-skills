# Trigger and dependency history

Why triggers were struck, deferred or rejected, and how the Seat 5 Codex path was chosen.
Read before proposing a new trigger or a different Seat 5 route.

## Contents
- Trigger history
- Codex Path B note

## Trigger history

- **T5 -- Phase-Boundary. STRUCK 2026-09-18.** It was declared here and never
  routed to: `personal-workflow` sends only ship/merge decisions to this gate, so
  T5 had never once fired. A gate that exists only on paper is worse than no gate,
  because it earns credit in the operator's model of the harness while catching
  nothing. Wiring it instead was costed and rejected: one panel is ~150-400K
  tokens, so a six-phase goal would be 0.9-2.4M tokens in review alone -- the same
  order of magnitude as T2, which was already rejected for exactly that reason.
  What replaces it: per-phase scope is enforced in code, not by a panel.
  `advance.py` refuses to mark a phase done whose Source records no owner warrant
  (exit 6), and `finalize.py` refuses while any detour is open (exit 7). Those cost
  nothing per phase and cannot be skipped under deadline.

- **T1 -- AskQuestion-Swap. DEFERRED.** T1 (replace any `AskUserQuestion`
  call in autonomous mode with a `/personal-critic-gate` vote) cannot be
  implemented as a slash-command intercept. It requires a `PreToolUse`
  hook on `AskUserQuestion`, which has no precedent in the current hook
  framework. T1 is deferred to a follow-up version.

Do NOT add T2 (every option-set) or T4 (prior-critic-carryover) to the
trigger set. Both were explicitly rejected:

- T2: cost runaway (~1.5-4.5M tokens per goal, LARGE bucket).
- T4: redundant -- phase-boundary scope is now enforced in code by advance.py, not by a panel.

## Codex Path B note

Path B note: `/codex:review` and `/codex:adversarial-review` both carry
`disable-model-invocation: true` in their plugin frontmatter and CANNOT
be programmatically invoked by Claude. The `codex:codex-rescue` subagent
(reached via the `/codex:rescue` command, which has NO disable flag) is the
only model-invokable Codex review path and therefore serves as Seat 5's
exclusive source. Dispatch it with the Agent tool
(`subagent_type: "codex:codex-rescue"`), NOT the Skill tool -- see step 11.
(EXTRACTED from OpenAI codex plugin v1.0.4 frontmatter, verified 2026-06-07;
SUGGESTION: if a future plugin version drops the disable flag on `review`,
re-evaluate using `/codex:review` directly for Seat 5.)
