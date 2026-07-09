---
name: personal-cs-client-question
model: sonnet
description: Use when a support engineer asks "where is X in the app?" / "which page does Y?" / "where do I find Z?" -- questions about locating features, pages, reports, or settings in a codebase. Triggers on phrases like "where do I see", "which page", "where in the app".
---

# personal-cs-client-question

## Provenance

Portfolio-generalized version of a customer-support triage skill I run daily
against a real production codebase. The original wires into that company's
internal tools (a proprietary knowledge-graph CLI, a real ticket system, a
real chat workspace); this version keeps the exact decision logic and
telemetry design but points at the generic `/graphify` and
`/understand-anything` skills in this plugin instead, and describes the
ticket-system / inbox integration in deliberately vague terms -- it is not
wired to any real email account, ticket system, or chat workspace.

## Overview

Thin wrapper over a code-location tool. Translates a plain-English question
about a fictional demo app ("Northwind Trading" -- a legacy web app with
Trade / Investor / Security / Position style entities, used here purely as
an illustrative example domain) into a knowledge-graph query and formats the
result as `page name + navigation path + file:line citation`. Does NOT
duplicate graph-traversal logic -- that lives in `/graphify` or
`/understand-anything`.

## When to use

- "Where do I see all trades from today?"
- "Where in the app do I view positions?"
- "Which page lets me add a new investor?"
- "Where does the ops team change the default deadline setting?"
- Deployment / cache-bust procedural questions ARE in scope when the answer
  is documented in a rules/reference doc. Route those to step 5 (doc
  fallback), not to escalation. Only escalate when no documented procedure
  exists.

## When NOT to use

- The user is asking HOW to do something -> use `personal-cs-step-by-step`
  instead (it calls this skill internally).
- The user is asking WHY something behaves a certain way -> diagnose
  question, out of scope; escalate.
- The user is asking for a connection string, credentials, or any
  **data-mutating** SQL (`INSERT`/`UPDATE`/`DELETE`/`MERGE`/`TRUNCATE`/
  `ALTER`/`DROP`/`CREATE`/`GRANT`/`REVOKE`) -> escalate.
- EXCEPTION: a **read-only SELECT** MAY be suggested under "Preliminary
  Diagnostic SELECT" below. SELECTs don't change data and are routinely
  handed to a client's DBA as the first investigation step.

## Smart-search decision tree

Try in order -- each step is token-cheap, escalate only when needed:

1. **First graph query.** Map business terms to code-level names via a
   project vocabulary doc if one exists, then run `/graphify query "<term>"`
   or `/understand-anything` (whichever is set up for the target repo).
2. **Budget-bump retry.** If you're asking about a low-degree node (a single
   setting, a small utility, one narrow page) and the first query's expected
   seed is missing from the rendered output, retry with a larger traversal
   budget/depth flag if the tool exposes one. Some graph-query CLIs evict
   low-degree seeds from the render window when a breadth-first walk pulls in
   high-degree "god nodes" first -- this is a rendering-window limitation of
   the tool, not evidence the seed doesn't exist. Confidence stays EXTRACTED
   if the retry surfaces the seed.
3. **Naming-suffix retry.** If previous steps return only backend seeds (a
   stored procedure, a service class) but the user asked about a UI page,
   retry with the app's common page-naming suffixes (e.g. `<Entity>Browse`,
   `<Entity>Detail`) -- most legacy web apps have a small, learnable set of
   these.
4. **Tool switch.** If an "explain a named node" style query returned no
   match, switch to the free-text query mode. "Explain" tools are for named
   graph nodes only, not free-text concepts.
5. **Doc fallback.** For config / settings / version-display / deployment
   questions, the graph tool may not cover prose docs. Read the relevant
   `docs/**/README.md` directly.
6. **Ticket-system case-law lookup.** If previous steps surface nothing
   useful, search your team's ticket system for previously resolved tickets
   matching the question. See `references/ticket-system-search.md` for the
   query pattern, the decision rule, and the confidentiality redaction rule
   -- this step is described generically and is NOT wired to a real ticket
   system in this demo.
7. **Grep fallback.** If the ticket-system search is also empty and 2-3
   graph queries surfaced nothing useful, fall back to `grep`/`Grep` over the
   source tree or docs.
8. **Escalate.** If grep also comes up empty, OR best confidence < 0.80, OR
   the user is asking for a data-mutating action, OR the user is probing for
   the identity of a client tied to a past ticket -> invoke
   `personal-cs-escalate-to-dev`.

## Input channels (vague, by design)

In the original production version, a question arrives from a support
engineer relaying something a client asked, over a real chat workspace and a
real ticket system. The same pattern generalizes to any inbound channel: a
shared support inbox, a ticket-system webhook, or a chat message someone
pastes in. This demo does not implement, poll, or read any real inbox,
ticket system, or chat workspace -- "where the question comes from" is out of
scope; this skill only covers "how to answer it once you have it."

## Mechanism

Run under `personal-fable-mode` gates: the `SOURCE:` citation must be a file
actually opened this session (Gate 4 -- never cite from memory), and when the
answer depends on 2+ unverified live-system facts (config state, deployment
layout, data shape), run `personal-facts-check` first to probe and label them;
its labels feed the `confidence` field.

1. Apply the decision tree above to locate the answer.
2. **Refuse** if best confidence < 0.80 OR no useful result -> invoke
   `personal-cs-escalate-to-dev`.
3. **Format** per the output contract below: numbered nav steps +
   `SOURCE:` citation. If multiple candidate pages exist and the graph tool
   ranks them clearly, list the top 3 with one-line descriptors each.
4. **Self-report metric** (FINAL STEP -- DO NOT SKIP). Invoke the wrapper
   script:

   **Invoke via the PowerShell tool (NOT Bash -- Bash misreads PS backtick
   line-continuations as command tokens).** Use the call operator `&` so the
   wrapper runs in-process; do NOT use `pwsh -File ... -AnswerMarkdown
   $multilineVar` -- on Windows, argv fragments multi-line strings across
   line breaks and the wrapper reports a missing-argument error even when the
   variable is populated.

   ````powershell
   $metric = @'
   <row JSON without id/ts/host/answer_path/answer_sha256 -- single line>
   '@
   $answer = @'
   <sidecar markdown -- see shape below; multi-line OK with @'...'@ here-string>
   '@
   & "${CLAUDE_PLUGIN_ROOT}/skills/personal-cs-client-question/cs-metric-write.ps1" `
     -SkillName "personal-cs-client-question" `
     -MetricJson $metric `
     -AnswerMarkdown $answer
   ````

   The wrapper stamps id/ts/host from the system clock, substitutes
   `{{id}}` `{{ts}}` `{{host}}` `{{skill}}` `{{confidence}}` `{{escalated}}`
   placeholders ONLY within the YAML frontmatter, writes both files
   atomically, and validates against `cs-metric-schema.json`. If the wrapper
   exits non-zero, **re-run with corrected inputs; do not bypass.**

   Schema reference: `cs-metric-schema.json` (sibling file).

   **Answer markdown shape (skill must emit):**
   ````markdown
   ---
   id: {{id}}
   ts: {{ts}}
   host: {{host}}
   skill: {{skill}}
   confidence: {{confidence}}
   escalated: {{escalated}}
   ---

   # Question
   <verbatim user question>

   # Answer (rendered to support engineer)
   <exact text rendered -- nav steps, SOURCE, Preliminary Diagnostic SELECT block, etc.>

   # Suggestion
   <1-line condensation>

   # Dev concern
   <or "_(none -- straight extraction)_">

   # Trajectory
   graph_queries: [...]
   tool_uses_self_count: <N>
   ````

   **Metric JSON shape (skill must emit):**
   ```json
   {
     "skill": "personal-cs-client-question",
     "question": "<first 500 chars>",
     "confidence": "EXTRACTED|INFERRED|BLANK|N/A",
     "escalated": false,
     "cited": true,
     "sources_read": ["path:line", ...],
     "suggestion": "<1-line>",
     "dev_concern": "",
     "graph_hit": true,
     "budget_retry": false,
     "suffix_retry": false,
     "fallback_grep": false,
     "fallback_doc_read": false,
     "ticket_system_searched": false,
     "ticket_system_top_ticket": null,
     "ticket_system_used_resolution": false,
     "diagnostic_select_suggested": false,
     "select_template": null,
     "graph_queries": [...],
     "tool_uses_self_count": <N>,
     "notes": ""
   }
   ```

   Even when this skill escalates via `personal-cs-escalate-to-dev`, invoke
   the wrapper FIRST (with `escalated:true`, `cited:false`, empty
   `sources_read`, and `suggestion`/`dev_concern` describing why), THEN
   invoke escalation. The metric line on the escalation branch is how the
   pattern learns from refusals.

## Preliminary Diagnostic SELECT (read-only, safe to share)

> **Illustrative case study:** `case-studies/example-deadline-lookup.md` --
> a fully fictional walkthrough of this mode end to end, invented for this
> demo (no real app, table, or client).

When the located page's behavior depends on database state and the
question is diagnostic ("why is X empty?", "what does my data say for Y?"),
this skill MAY append a read-only SELECT that a support engineer forwards to
the client or their DBA. SELECTs don't change data and are routinely shared
as the first investigation step -- this is a normal part of the answer, not
a fallback.

### Eligible (safe to suggest)

Any **read-only SELECT**, including:

- Single-table queries against config/reference tables
- Single-table queries against operational tables (illustrative examples for
  the Northwind Trading demo domain: `Trade`, `Investor`, `Security`,
  `Position`)
- Multi-table `JOIN`s -- diagnostics often require joining related entities
- Aggregates (`COUNT`, `SUM`, `MAX`, `AVG`, `GROUP BY`, `HAVING`)
- Views
- Read-only schema lookups: `sp_helptext`, `INFORMATION_SCHEMA.*`,
  `sys.objects`, `sys.columns`

### NOT eligible (escalate)

- Any data-mutating statement: `INSERT`, `UPDATE`, `DELETE`, `MERGE`,
  `TRUNCATE`, `BULK INSERT`, `DROP`, `CREATE`, `ALTER`, `GRANT`, `REVOKE`
- `EXEC <sp>` where the SP is known or suspected to mutate -- if you can't
  tell, escalate
- Connection strings, login passwords, credential descriptions

### Trigger logic (ALL must be true)

1. Main path succeeded -- a specific page/feature/table was located.
2. The question implies wanting to understand state or root cause (not just
   "where do I find X?").
3. The SELECT can be composed by reading actual source, a stored procedure
   body, or docs -- no fabricated column or table names.

If any check fails -> emit only the standard navigation answer; do not
append the SELECT block.

### Honesty Protocol caveats inside this mode

- Never fabricate column names, table names, or key/value names -- confirm
  by reading the source or docs first.
- An `EXPECTED:` line is INFERRED unless explicitly extracted from
  authoritative docs. Label it inline.
- If you cannot predict the expected value with reasonable grounding, omit
  `EXPECTED:` rather than guess.
- Claude never runs SQL against a client's database -- the support engineer
  forwards the SELECT; the client or their DBA runs it.

## Output contract

Standard (always emitted):

```
1. [navigation step, e.g. Main Menu -> Browse -> Trades]

SOURCE: <path>:<line>
```

Extended (append only when Preliminary Diagnostic SELECT trigger logic is
satisfied):

```
PRELIMINARY DIAGNOSTIC SELECT (read-only, safe to share with the client):

    SELECT KeyName, Value, Description
    FROM SystemData
    WHERE KeyName = 'ExampleDeadlineSetting';

EXPECTED: a non-empty Value -- INFERRED from the fallback chain at
   <path>:<line>. NULL / empty / missing row -> likely root cause.
READ-ONLY: SELECT only. Does not change any data. A DBA can run it safely.
IF VALUE LOOKS WRONG: escalate via personal-cs-escalate-to-dev.
```

## Anti-patterns

- Re-implementing graph traversal in this skill (use `/graphify` or
  `/understand-anything`)
- Returning an answer when the located confidence is < 0.80 (escalate)
- Fabricating a page name when no graph hit exists (escalate)
- Composing pedagogic explanations of how the page works internally
- Adding code-level detail the reader (a support engineer, not a developer)
  doesn't need
- (Diagnostic SELECT mode) emitting any statement that is not a pure read
- (Diagnostic SELECT mode) fabricating a column, table, or key name
- (Diagnostic SELECT mode) emitting an `EXPECTED:` value that isn't grounded
- Embedding a literal or fabricated `ts` in the metric line instead of
  reading the system clock at write time

## Length budget

Keep this file's content under ~220 lines. Pure graph-traversal and
ticket-system-query logic live outside this file -- in `/graphify` /
`/understand-anything` and `references/ticket-system-search.md`
respectively. This file is the routing-and-telemetry contract; data tables
live elsewhere.
