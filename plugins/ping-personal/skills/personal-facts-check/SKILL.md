---
name: personal-facts-check
model: sonnet
description: Run a fact-finding session BEFORE spec/plan work -- probe the live system and code, and produce a confidence-labeled facts doc (CONFIRMED-LIVE / EXTRACTED / INFERRED / UNKNOWN, with RESOLVED for closed discrepancies) under docs/<area>/facts/. Trigger on /personal-facts-check (formerly /personal-facts), "fact session", "facts pass", "facts check", "I need to do a fact thing session", "verify the facts doc", "kill the blanks in the facts". Update mode re-verifies an existing facts doc and marks discrepancies RESOLVED.
---

# /personal-facts-check

Establish what is actually true about a system before anyone plans against
it. The deliverable is a facts doc where every claim carries a confidence
label and enough provenance that a later session can re-verify it.

REQUIRED SUB-SKILL: personal-fable-mode -- this skill IS Gate 2 (evidence
before reasoning) run as a formal deliverable. Run the full gate loop while
producing the doc: scope the decision the facts serve (Gate 1), probe before
reasoning (Gate 2), attack your own facts before recording them (Gate 3),
verify each claim at the layer it makes (Gate 4), and the labels below are
Gate 5 made durable.

## Labels (the contract)

| Label | Meaning | Minimum provenance |
|---|---|---|
| `CONFIRMED-LIVE` | Observed on the running system this session | the command/query/screenshot and its output |
| `EXTRACTED` | Read directly from code / schema / config | file:line |
| `INFERRED` | Derived from EXTRACTED facts | one-sentence derivation naming its inputs |
| `UNKNOWN` | Could not determine | what probe would resolve it |
| `RESOLVED` | A previously recorded discrepancy, now settled | what settled it + date |

No unlabeled claims. A wrong fact is 3x worse than an UNKNOWN.

## Procedure

1. **Scope.** One sentence: what system/behavior are we establishing facts
   about, and for which upcoming decision. Name the ticket/area.
2. **Probe before asking.** Read the code, run the read-only queries or
   commands, check the live system where reachable. Ask Ping only for what
   no tool can observe (and record his answer as its own labeled fact,
   source: "Ping, <date>").
3. **Write the doc** to `docs/<area>/facts/<YYYY-MM-DD>-<topic>-facts.md`
   (ticket-shaped areas like `docs/ST-690/facts/` are the norm on work
   repos). Structure: Scope, Facts table (label, claim, provenance), Open
   UNKNOWNs (each with the probe that would kill it), New questions raised.
4. **Kill the blanks loop.** For each UNKNOWN whose probe is cheap and
   read-only, run the probe now and upgrade the label. Stop when remaining
   UNKNOWNs need approval, write access, or Ping.
5. **Update mode** (facts doc already exists): re-verify each CONFIRMED-LIVE
   fact that the decision depends on, mark settled discrepancies `RESOLVED`
   with what settled them, and never delete a superseded fact -- strike it
   through with the correction beside it, so the history of being wrong
   stays auditable.

## Boundaries

- Probes are read-only: no data mutation, no state-changing commands, no
  writes outside the facts doc.
- The facts doc records reality, not proposals -- design options belong in
  the spec/plan that consumes this doc.
