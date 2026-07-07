---
name: personal-cs-escalate-to-dev
model: sonnet
description: Use when personal-cs-client-question or personal-cs-step-by-step returns low confidence (INFERRED below 0.80 / zero hits / ambiguous branching) OR when the request matches a DB-escalation rule (connection strings, raw SQL, schema/credential SHAPE requests, table mutations -- even with "don't run it / hypothetical / just show me" framings). Triggered automatically by Claude, not requested by the user.
---

# personal-cs-escalate-to-dev

## Provenance

Portfolio-generalized version of a customer-support triage skill I run daily
against a real production codebase. See `personal-cs-client-question`'s
Provenance note for full context. The original posts a paste-ready handoff
into a real team chat workspace; this version writes the same message to a
local temp file and stops there -- it never sends anything anywhere.

## Overview

Composes a paste-ready handoff message for a human to relay into whatever
team chat channel your org uses. Writes a single text block to a known temp
file; the support engineer copies/pastes it once, with no editing required.

## When to use (two automatic triggers)

**Trigger A -- Low confidence:**
- `personal-cs-client-question` returned INFERRED < 0.80 OR zero graph hits
- `personal-cs-step-by-step` cannot enumerate a workflow due to ambiguous
  branching
- Any case where the Honesty Protocol's Force-Blank rule applies

**Trigger B -- DB-touch:**
- Connection string requests (change OR describe the format)
- Raw SQL (execute, compose, draft, "show me the SELECT", hypothetical)
- Table mutations (UPDATE / DELETE / INSERT / CREATE / ALTER / DROP /
  TRUNCATE / GRANT / REVOKE)
- Schema enumeration ("what columns are in this table?")
- Credential or password requests

## Mechanism

1. **Gather context:**
   - The user's verbatim question
   - The support engineer's framing, if different
   - What was tried (`personal-cs-client-question` result,
     `personal-cs-step-by-step` result, graph-tool confidence)
   - Why confidence broke, OR which DB-rule trigger fired
   - A one-line suggested next action for the on-call engineer

2. **Compose the paste-ready message** using the template below.

3. **Write to** `$env:TEMP\escalate-to-dev-latest.md` (PowerShell syntax;
   cmd equivalent is `%TEMP%\escalate-to-dev-latest.md`). Overwrites each
   invocation; only the latest escalation is kept.

4. **Self-report metric** (DO NOT SKIP). Invoke the wrapper -- write this
   BEFORE telling the support engineer (step 5); the metric line is the
   audit trail, the user-facing instruction is the action. Invoke exactly as
   documented in `personal-cs-client-question/SKILL.md` Mechanism §4,
   substituting `-SkillName "personal-cs-escalate-to-dev"`.

   **Metric JSON shape (escalate-specific):**
   ```json
   {
     "skill": "personal-cs-escalate-to-dev",
     "question": "<verbatim from caller>",
     "confidence": "N/A",
     "escalated": true,
     "cited": false,
     "sources_read": [],
     "suggestion": "<1-line: what the on-call engineer should do>",
     "dev_concern": "<1-3 lines: why this can't be answered without dev review>",
     "trigger": "db_touch|low_confidence|out_of_scope|other",
     "upstream_skill": "personal-cs-client-question|personal-cs-step-by-step|null",
     "upstream_confidence": "<upstream skill's confidence label, or null if Trigger B>",
     "msg_path": "<path the handoff message was written to>",
     "notes": ""
   }
   ```

   `trigger`, `upstream_skill`, `upstream_confidence`, and `msg_path` are
   real top-level fields in `cs-metric-schema.json` -- the viewer's
   escalation-trigger detail panel reads them directly. `suggestion` and
   `dev_concern` MUST be non-empty -- escalations are where future tuning
   learns most.

5. **Tell the support engineer (terse):**

```
I'm not confident enough to answer this. I've written a handoff message at:
$env:TEMP\escalate-to-dev-latest.md   (PowerShell; in cmd use %TEMP%\escalate-to-dev-latest.md)

Tell the client: "Let me check on this; I'll get back to you shortly."
Then open that file, copy the contents, paste into your team's support channel.
```

6. **DO NOT** compose a direct answer to the original question. That is the
   entire point of escalation.

## Anti-patterns

- Skipping the metric line (step 4) -- DB-touch escalations become invisible
- Bypassing `cs-metric-write.ps1` or passing a literal `ts` -- the wrapper
  reads the system clock; a fabricated ts corrupts the audit stream
- Filling `suggestion` with the client-facing nav steps -- this field is the
  developer's next action, not the client's
- Leaving `dev_concern` empty on an escalation -- by definition an
  escalation has at least one concern (the reason it was escalated)

## Handoff message template

```
*[Support escalation -- <fictional ticket ref>]*

*Client question (relayed):*
> {verbatim user question, blockquoted}

*Support engineer's framing:*
{their words, or "(same as client question)" if no rephrasing}

*What I tried:*
- personal-cs-client-question: {result, e.g. "INFERRED 0.62 -- ambiguous between two candidate pages"}
- personal-cs-step-by-step: {result, or "not attempted -- already escalated upstream"}

*Why I escalated:*
{One-line reason: "confidence below threshold" / "DB-touch request, per persona rule" / "branching workflow exceeds tool coverage"}

*Suggested next action:*
{One-line suggestion, e.g. "Confirm which page is correct." / "Run the query yourself and reply with the result." / "Add coverage for the X family to the knowledge graph."}
```

## Example -- DB-touch escalation

```
*[Support escalation -- SUP-example]*

*Client question (relayed):*
> "Can you run a query to count trades for a given client yesterday?"

*Support engineer's framing:*
(same as client question)

*What I tried:*
- Nothing -- request matched the DB-touch trigger (raw SQL execution)

*Why I escalated:*
DB-escalation rule: raw SQL -> route to a developer. Even read-only queries
go through a human per this persona's contract.

*Suggested next action:*
Either run the query yourself and reply with the result, or send the client
a screenshot of the equivalent filtered report view.
```

## Length budget

Keep this file's content under ~130 lines. The handoff template is still the
load-bearing part; the metric step is audit infrastructure, not new logic.
