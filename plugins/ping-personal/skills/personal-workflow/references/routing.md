# Routing -- disambiguation procedure (bounded model judgment, not a numeric scorer)

Input: the merged capability map (discover.py project rows + model-folded plugin/built-in rows) and
the phase intent.

1. Match the phase intent against every row's description.
2. Single clear best match -> use it.
3. Overlap (several rows claim the same verb -- e.g. multiple skills/agents claim "write" or "test"):
   disambiguate by --
   (a) prefer the most SPECIFIC description over a catch-all;
   (b) prefer a subagent over a slash-skill for delegated background work;
   (c) treat "TRIGGER IMMEDIATELY / no intent word needed" phrasing as interactive-dispatch greed and
       discount it for autonomous routing.
4. Still tied, OR the leading candidate is confidence=low, OR the phase is high-stakes -> ASK the operator.
5. No match -> fall back to RESEARCHER (read) or IMPLEMENTER (write) from the roles block, or run inline;
   announce the substitution.

Priority order when otherwise equal (stated inline -- does NOT depend on reading using-superpowers):
(1) process skills (brainstorming, debugging, planning) -> (2) most domain-specific implementation skill
-> (3) generic subagent -> (4) inline.

Honesty rule: BEFORE acting, announce the pick + basis + fan-out decision, e.g.
"Phase 3 'triage 13 items' -> RESEARCHER/iris (most-specific 'read/understand existing code'); fan-out
eligible (N=13, read-only, no shared state)." This surfaces a mis-route for override -- it is a control,
not a guarantee. A wrong description does not become right because it was announced; the announcement
just makes the wrongness visible.

## ping-personal role anchors (this plugin's defaults)
- RESEARCHER = `iris` -- read/trace/understand existing code, no writes.
- IMPLEMENTER = `bunny` -- write/edit source per an approved plan.
- CRITIC = `ms-mario` (direct adversarial review) or `/personal-critic-gate` (3-vote ship gate).
- Other ping-personal agents are domain-specific and outrank the generic fallbacks when their
  description matches the phase intent (e.g. a parser phase -> `vex`; a git/PR phase -> `dora`;
  a design/chart phase -> `maggie`). These are model-folded, not discover.py rows.
