---
name: personal-grill-me
description: Use when the user wants a plan, decision or idea stress-tested - "grill me", "grill this", "stress-test my plan", "ask me questions until we agree", "poke holes in this" - or when a plan's intent is unclear before work starts. Interviews in rounds over a decision tree, gives a recommended answer for every question, and looks up facts itself instead of asking. Add "with docs" to also record settled terms and decisions in docs/glossary/. Also reached by /grill-me, /grilling and /grill-with-docs.
---

# Grill me

Adapted from Matt Pocock's `grill-me`, `grilling` and `grill-with-docs` skills (MIT, see
`THIRD-PARTY-NOTICES.md`). It is one skill here: the interview, plus an optional docs mode.

## In your daily work

| You say | What happens |
|---|---|
| "grill me on this plan" | Rounds of numbered questions, each with a recommended answer, until nothing is left assumed |
| "grill me with docs" or `/grill-with-docs` | The same interview, and each settled term or decision is written to `docs/glossary/` |
| A goal or big project starts with fuzzy intent | Other skills call this one first, so the work starts from a shared understanding |

## How the interview runs

Interview the user until you reach a shared understanding. Treat the plan as a **design tree**:
every decision branches into the decisions that depend on it.

Work the tree in **rounds**. The **frontier** is every decision whose prerequisites are already
settled. Those are the questions you can ask now without guessing at earlier answers. Ask the
whole frontier in one round, then wait for the user's answers.

Format each question like this:

```
**Q1 - <question title>**
<the question, and each option named by what it leads to: its cost, risk and consequence>

-> Recommended: <the answer you would pick, and why, in one sentence>
```

Rules for a round:

- Word each question so "yes" accepts your recommended answer.
- Name options by what they do, never by bare letters such as "Option A".
- The user can answer in shorthand, such as "1 yes, 2 the cheap one, 3 no because ...".
- The user often dictates by speech-to-text. If an answer looks garbled, ask once rather than guess.
- A question that depends on another question still open this round waits for a later round.

Each answer reshapes the tree. Settled decisions move the frontier outward. Recompute it and ask
the next round.

**Facts are your job, never the user's.** When a question needs a fact from the code, the database
or the docs, look it up or send a subagent. Do not ask the user for anything you can find yourself.
Do not block on the lookup either. Ask the rest of the frontier while it runs.

**Decisions are the user's.** Put each one to them and wait.

The session is done when the frontier is empty: every branch visited, nothing silently assumed.
Then write a short summary of what was agreed. Do not act on it until the user confirms the
summary is right.

## With docs

When the user says "with docs", or runs `/grill-with-docs`, also call the Skill tool with
`ping-personal:personal-domain-modeling` and follow it during the interview. Settled terms go
into `docs/glossary/GLOSSARY.md`. Hard-to-reverse choices become decision notes in
`docs/glossary/decisions/`, only when they pass that skill's three tests.

## Writing

Questions and summaries follow the htsw Explaining sentences rules (20 words or fewer per
sentence, context first) and the personal-unslop pass.
