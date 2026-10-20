---
name: personal-domain-modeling
description: Build and sharpen a project's glossary - docs/glossary/GLOSSARY.md for the terms, docs/glossary/decisions/ for hard-to-reverse choices. Challenges fuzzy or conflicting terms, tests them with edge-case scenarios, checks them against the code and stored procedures, and writes them down as they settle. Use when discussing what a term means, when a client and the code use different words, writing or editing the glossary, or recording a decision a future reader would question. Also /personal-domain-modeling.
---

# Domain Modeling

Adapted from Matt Pocock's `domain-modeling` skill (MIT, see `THIRD-PARTY-NOTICES.md`). This
version keeps everything under `docs/glossary/`, and calls a decision record a **decision note**.
The industry name for one is an ADR (architecture decision record).

Build and sharpen the project's domain model while you design. That means challenging terms,
inventing edge-case scenarios, and writing terms and decisions down the moment they settle.
Only *reading* the glossary for vocabulary is not this skill. This skill is for changing the model.

## In your daily work

| Moment | What this skill does |
|---|---|
| A client and the code use one word for two things | Asks which one you mean, then writes the winner into the glossary |
| A ticket uses a term the code calls something else | Finds the stored procedure or page that uses it, and shows where the words disagree |
| You choose something a future reader would question, like keeping logic in T-SQL | Offers a one-paragraph decision note, if the choice passes the three tests below |
| A support engineer asks what a term means | The glossary entry is the answer, and htsw reuses the same words |

## File structure

```
/
+-- docs/
    +-- glossary/
        +-- GLOSSARY.md
        +-- decisions/
            +-- 0001-<decision>.md
```

If `docs/glossary/GLOSSARY-MAP.md` exists, the project has several areas, each with its own
glossary file, and the map lists them. Infer which area the topic belongs to. Ask if unclear.

Create files lazily. Create `docs/glossary/GLOSSARY.md` when the first term is resolved.
Create `docs/glossary/decisions/` when the first decision note is needed.

## During the session

### Challenge against the glossary

When the owner uses a term that conflicts with the glossary, say so at once. For example:
"Your glossary defines 'cancellation' as X, but you seem to mean Y. Which is it?"

### Sharpen fuzzy language

When a term is vague or overloaded, propose a precise one. For example: "You said 'account'.
Do you mean the trading account or the login user? Those are different things."

### Test with concrete scenarios

When relationships between terms come up, invent edge cases that force a precise boundary.
For example: "A position is closed and reopened the same day. Is that one position or two?"

### Check against the code

When the owner says how something works, check whether the code agrees. In an ASP Classic and VB6 app that means
the stored procedure, the page that calls it, and the VB6 class in between. Surface any
contradiction: "The procedure deletes the whole order, but you said partial cancels exist. Which is right?"

### Update the glossary inline

When a term is resolved, update `docs/glossary/GLOSSARY.md` right away.
Do not batch the updates. Use the format in [GLOSSARY-FORMAT.md](GLOSSARY-FORMAT.md).

The glossary holds no implementation details. It is not a spec, a scratch pad or a decision log.

### Offer decision notes sparingly

Offer a decision note only when all three are true:

1. **Hard to reverse**: changing your mind later would cost real time.
2. **Surprising without context**: a future reader will ask why it was done this way.
3. **The result of a real trade-off**: there were genuine alternatives, and one won for reasons.

If any of the three is missing, skip it. Use the format in [DECISION-FORMAT.md](DECISION-FORMAT.md).
