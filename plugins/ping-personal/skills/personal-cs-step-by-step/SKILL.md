---
name: personal-cs-step-by-step
model: sonnet
description: Use when a support engineer asks "how do I do X?" or "how does the ops team change Y?" -- procedural how-to questions about app workflows or system-setting changes. Triggers on phrases like "how do I", "how does", "walk me through", "what are the steps to".
---

# personal-cs-step-by-step

## Provenance

Portfolio-generalized version of a customer-support triage skill I run daily
against a real production codebase. See `personal-cs-client-question`'s
Provenance note for the full context -- this skill inherits the same
generalization (fictional demo app, generic ticket-system language, no real
inbox/chat wiring).

## Overview

Procedural how-to skill. Calls `personal-cs-client-question` first to locate
the relevant page or setting, then reads the source or docs to enumerate the
workflow as numbered imperative steps. Does NOT duplicate page-location
logic.

## When to use

- "How do I enter a new trade?"
- "How does the ops team change the default rollover deadline?"
- "How do I generate the end-of-day report?"
- "Walk me through allocating a partial trade."

## When NOT to use

- "Where is X?" -> use `personal-cs-client-question` directly.
- "Why is X happening?" -> diagnose question; route through
  `personal-cs-client-question` (its decision tree includes the
  ticket-system case-law lookup). If it returns a resolution-based answer,
  relay it AS-IS including the `WATCH OUT FOR` recency caveat; do not
  re-enumerate or re-paraphrase -- the citation and caveat are load-bearing.
  If it still escalates, follow suit.
- DB-touch requests (run a query, show SQL, schema, connection info) ->
  escalate.
- Deployment / cache-bust "how do I" questions ARE in scope when the
  procedure is documented in a rules/reference doc. Let
  `personal-cs-client-question` (step 1 below) try its doc-fallback path
  first; don't pre-emptively escalate these.

## Mechanism

Run under `personal-fable-mode` gates: every emitted step must trace to source
read this session (Gate 2/4 -- no steps from memory). If the workflow depends
on 2+ unverified live-system facts, run `personal-facts-check` to probe and
label them before enumerating.

1. **Call `personal-cs-client-question` internally** with the user's
   question, unchanged. It applies its own smart-search decision tree
   (graph-query first, budget/suffix retries, doc fallback, ticket-system
   case-law lookup, grep fallback) and writes its OWN metric line. If it
   returned a ticket-resolution-based answer
   (`ticket_system_used_resolution: true` in its metric), the response shape
   is already correct -- relay it AS-IS in step 4; do not re-paraphrase or
   strip the caveat.
2. **If `personal-cs-client-question` returns < 0.80 confidence:** stop. It
   already invoked `personal-cs-escalate-to-dev`; do not compose your own
   answer (still emit your own metric line below -- step 6 -- with
   `escalated:true`).
3. **Read the located file** via the Read tool. Scan for the user-facing
   workflow: form fields, button handlers, or a settings doc's procedure
   section.
4. **Enumerate** as numbered imperative steps per the output contract below.
5. **Flag branching workflows.** If a step depends on a prior choice AND the
   choices vary in ways the code-location tool can't predict, list the most
   common path + add a `WATCH OUT FOR:` caveat -- or escalate if the
   branching is unmanageable.
6. **Self-report metric** (FINAL STEP -- DO NOT SKIP). Invoke the wrapper
   script exactly as documented in `personal-cs-client-question/SKILL.md`
   Mechanism step 4, substituting `-SkillName "personal-cs-step-by-step"`.

   **Metric JSON shape (skill must emit):**
   ```json
   {
     "skill": "personal-cs-step-by-step",
     "question": "<first 500 chars>",
     "confidence": "EXTRACTED|INFERRED|BLANK|N/A",
     "escalated": false,
     "cited": true,
     "sources_read": ["path:line", ...],
     "suggestion": "<1-line condensation of the workflow handed to the support engineer>",
     "dev_concern": "",
     "cs_client_question_confidence": "EXTRACTED|INFERRED|BLANK",
     "located_file": "path:line or empty",
     "branching_workflow": false,
     "watch_out_for_added": false,
     "steps_emitted": "<N>",
     "tool_uses_self_count": <N>,
     "notes": ""
   }
   ```

   Even when this skill escalates via `personal-cs-escalate-to-dev`, invoke
   the wrapper FIRST (with `escalated:true`, `cited:false`, empty
   `sources_read`, and `suggestion`/`dev_concern` describing why), THEN
   invoke escalation.

## Output contract

```
1. [first imperative step]
2. [second imperative step]
3. [third imperative step]

(optional)
WATCH OUT FOR: [single-line caveat about permission, role, or branching]

SOURCE: file:line
```

## Refusal conditions

- `personal-cs-client-question` returned low confidence -> already
  escalated; do not re-attempt.
- Workflow has 3+ branch points whose choices depend on data Claude cannot
  observe -> escalate via `personal-cs-escalate-to-dev`.
- The "how do I" question is actually a "why is" question in disguise ->
  escalate.

## Anti-patterns

- Skipping `personal-cs-client-question` and reading source directly (loses
  the confidence threshold)
- Including implementation-language code in the steps -- the reader wants
  steps, not code
- Pedagogic WHY explanation between steps
- Composing an answer when `personal-cs-client-question` already escalated
- Embedding a literal or fabricated `ts` in the metric line instead of
  reading the system clock at write time

## Length budget

Keep this file's content under ~120 lines. Enumeration work is runtime work
(read the source), not encoded in this file.
