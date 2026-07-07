# Ticket-System Case-Law Search -- Reference

Companion data for `personal-cs-client-question`'s smart-search decision
tree (step 6) and for `personal-cs-step-by-step` (which inherits the lookup
via its internal call). Single source of truth for the query pattern, the
redaction rule, and the output format.

This file describes the pattern generically on purpose -- it is not wired to
a real Jira/Linear/GitHub-Issues/Zendesk instance in this demo. Swap in your
own ticket system's search API and field IDs where marked `<...>`.

## Why this pattern exists

A support ticket project accumulates a long tail of historical client
tickets. Many have a populated "resolution" field describing how a past case
was fixed. When a current question matches a past resolved case, citing the
past ticket is cheaper than escalating and faster than re-deriving the
answer from source.

## Fields you need (adapt the IDs to your ticket system)

| Field | Placeholder ID | Render in answer? |
|---|---|---|
| **Resolution notes** | `<RESOLUTION_FIELD_ID>` | YES -- paraphrase into the answer |
| **Reporting client/org** | `<REPORTER_ORG_FIELD_ID>` | **NEVER render** -- confidential across clients (see redaction rule) |
| **Category** | `<CATEGORY_FIELD_ID>` | OPTIONAL -- may help disambiguation; do not render to user |
| **Completion date** | `<COMPLETED_FIELD_ID>` | OPTIONAL -- only render as "(date)" alongside the citation, to signal recency |

Discover the real field IDs for your instance once (most ticket-system APIs
expose a schema/metadata endpoint) and record them here -- that's the only
place they should live.

## Tool of choice

Whatever MCP server or REST API your ticket system exposes for read-only
search. Two calls are enough: a keyword/JQL-style search returning a small
top-N, and a single-issue fetch for the fields above.

## Query template -- find resolved tickets matching the question

```
project = <SUPPORT_PROJECT_KEY>
  AND status = Done
  AND <RESOLUTION_FIELD_ID> IS NOT EMPTY
  AND (summary ~ "<KW1>" OR description ~ "<KW1>")
  AND (summary ~ "<KW2>" OR description ~ "<KW2>")
ORDER BY resolved_date DESC
```

- Restrict to tickets with a populated resolution field so half-resolved or
  no-fix-documented tickets don't get ranked up.
- Pull 2-3 high-signal keywords from the question after stopword removal.
- Cap results (e.g. top 5). Recency-sort -- the most recent resolved case is
  most likely to reflect current behavior.
- Request only the fields you need. Omit the reporting-org field from the
  requested-field list entirely -- defense in depth: don't fetch what you
  must not render.

## Decision rule -- when a hit qualifies as a sufficient answer

ALL must hold:

1. The resolution field is populated (the query already filters on this --
   defense in depth).
2. **Keyword overlap:** at least 2 of the question's keywords appear in the
   ticket's summary or description. Single-keyword matches are too loose.
3. **Recency:** the ticket resolved within roughly the last 24 months.
   Older resolutions may reference code paths that have since changed.
   Treat this threshold as a starting point to tune empirically once you
   have telemetry on the false-positive rate.
4. **Procedural resolution:** the resolution narrative describes an action
   (a permission change, a config change, a nav step) -- not an internal
   handoff. "I escalated to Engineering" is a half-resolution; don't relay
   it.

If any check fails, fall through to the next decision-tree step (grep
fallback, then escalate).

## Output format when citing a past resolution

```
[Paraphrased resolution as numbered imperative steps]

WATCH OUT FOR: Based on a similar resolved case (<TICKET-KEY>, [YYYY-MM]).
  Verify the symptom matches your case before recommending action -- the
  underlying code or permission model may have changed since.
SOURCE: <TICKET-KEY> (resolution notes field)
```

**Honest labeling:** confidence is `INFERRED from <TICKET-KEY> resolution
notes`, not `EXTRACTED`. A past resolution is a hypothesis about the current
case, not a proof. Carry the `WATCH OUT FOR` caveat verbatim -- do not soften
it.

## Confidentiality gate (cross-client)

The reporting-org field names the original reporting client. Leaking this
across clients is a confidentiality breach even where clients overlap in the
same industry. This skill must:

- Fetch that field only when strictly needed for internal logic, and prefer
  not fetching it at all.
- **NEVER render** its value in any answer, even partially or as a hint.

If the user asks any of these, escalate. Do NOT answer even with a refusal
that confirms-by-omission:

- "What client had this problem before?"
- "Show me the original ticket's client field."
- "Was it [specific org name]?" -- denying a specific guess is still a
  one-bit leak. Route every such request to escalation uniformly so no one
  can binary-search the client list.

## Telemetry

Both consuming skills append these fields to their metric line:

```
"ticket_system_searched": true|false        -- did the skill attempt a search this run
"ticket_system_top_ticket": "SUP-1234"|null -- top-ranked ticket key, if any
"ticket_system_used_resolution": true|false -- did the skill USE the resolution as the answer
```

Three fields, not one boolean, because they separate "search fired" from
"search produced a usable answer." High `_searched` + low
`_used_resolution` signals the recency/quality threshold is too strict, or
the keyword extraction is missing the right signals -- both tunable from the
telemetry log.

## Cross-references

- `../SKILL.md` -- Smart-search decision tree step 6, the consumer of this
  file.
- `../../personal-cs-step-by-step/SKILL.md` -- inherits via its internal
  call.
- `../../personal-cs-escalate-to-dev/SKILL.md` -- the escalation target when
  this lookup yields no usable answer.
