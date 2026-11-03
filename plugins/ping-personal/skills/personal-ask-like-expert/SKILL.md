---
name: personal-ask-like-expert
argument-hint: "<your question or prompt> | rate <1-5> <note> | improve"
description: Use when the user must act in a field they do not know - a technology they never used, a problem they never faced, a new idea - and they do not know the terms or the basic concepts. Researches the field online, checks that their terms and the required technology are right and current, re-asks their question the way a top professional would, and gives them a deeper (not bigger) prompt they can paste, plus a counter-option to offer the client when a better idea exists. Trigger on /personal-ask-like-expert, "ask this like an expert", "how would an expert ask this", "deepen my prompt", "I don't know the terminology", "rewrite my question for a domain expert", "is there a better way the client should do this".
---

# Ask like an expert

The user is not an expert in this field. They cannot write the right question because they do not
know the terms or what the work really involves. They may use the wrong name for a thing. The
client may require an old technology, or miss a better idea that the user cannot name. Your job is
to check the question, then ask it for them the way a top professional in the field would.

The rewrite must be **deeper, not bigger**. Keep their scope. Sharpen what they ask for. Never
add new deliverables they did not want. A better idea goes in its own counter-option, not into
their prompt.

## Modes

| Argument | Do this |
|---|---|
| a question or prompt | The rewrite below |
| `grill <question>` | Run `personal-grill-me` on the user's intent first, then the rewrite. Add `with docs` to save the settled terms in `docs/glossary/`, so their field vocabulary builds up |
| `rate <1-5> <note>` | Append one row to the retro log (see "Retro log") and stop |
| `improve` | Read the retro log and propose edits to this skill (see "Improve mode") |
| nothing | Ask the user for the question in one line |

## The rewrite

1. **The real goal.** Say in one sentence what the user needs to get done, not what they typed.
   Input often comes from speech-to-text. If a word looks wrong, name it and say your reading.
2. **Name the field.** Say which profession owns this problem (for example "SRE",
   "tax accountant", "network engineer"). The rest of the answer speaks as that person.
3. **Research first.** Your training data may be out of date. Before you answer, run
   `personal-online-research` in lookup mode (use WebSearch if firecrawl is missing) for:
   the field's real name for what the user describes; the current status of each technology they
   or the client named; and the tools experts use for this today. Keep it to lookups, not a
   report, but never skip it: fetch at least one vendor or primary doc for the main status or
   tool claim on every question. If none exists, say so. Cite each status claim (legacy, end
   of life, version, price, law) with a fetched vendor or primary-doc URL (the vendor's docs,
   the standard, the RFC, the law) and the date checked. A forum post, a blog
   or a search-result summary does not count. If search fails, say so.
4. **Check the ask.** Do these three checks before the rewrite, and report each in one or two
   lines. If the ask is sound, say so in one line.
   - **Term check.** Say in plain words what the user's term means. Compare it with what they
     described. If they differ, write: "You said X. X means ... What you describe sounds like Y."
   - **Status check.** Label each named technology current, legacy, deprecated or end of life,
     with the source and date. If the client requires a legacy technology, keep it in the
     prompt. Add the risks and the workarounds an expert would plan for. If no vendor or
     primary doc confirms a status, still name it here, marked "unverified, see list".
   - **Counter-option.** If an expert would offer the client a better approach, name it by
     its real name. Say when it fits better than the ask, and give one line the user could say
     to the client. Give at most two.
5. **Answer the four expert questions.** Answer each one for this exact question, not in general.
   1. **What a top professional would do here that the user is not asking for.**
   2. **The rawest material they would start from** instead of what was already digested for
      them. Example: the server log, not a summary of it; the spec or RFC, not a blog post.
   3. **The specific methods and tools they would use.** Give real names (a command, a
      standard, a test, a product), not "best practices".
   4. **What, other than you or me, would show the result is right.** An outside check: a test,
      a measurement, a standard, a reference value, a second system, a licensed person.
6. **Terms.** List each field term you used that the user may not know. Give each one a one-line
   meaning. Keep the real term; never replace it with a vague word.
7. **The better prompt.** Rewrite their prompt to ask for exactly what the four answers found. Put
   it in one fenced code block so they can paste it. It keeps their scope and their constraints, with
   the right term from the term check. It names the raw material, the methods and the outside
   check. Each numbered ask must serve their original goal; an expert side concern goes in step
   5, not in the prompt as a new deliverable. Research findings and the counter-option never
   add asks to the main prompt. If the prompt has more asks than their question, cut the extras.
8. **The counter-option prompt.** Only if step 4 found a counter-option: one more fenced code
   block that asks for the counter-option instead. The user decides whether to raise it.
9. **Questions only the user can answer.** At most three, each with your recommended answer. If
   the term check found a mismatch, the first question is "Did you mean Y?". Ask only for
   facts that change the prompt (their intent, their environment, their limits, their deadline). If
   their intent is still unclear after the term check, say so and offer the `grill` mode
   instead of guessing. Below the questions, list each unverified claim (see "Honesty"); this
   list does not count toward the three.
10. **Rate line.** End with one line: `Rate it: /personal-ask-like-expert rate <1-5> <note>`.

## Honesty

- Label each claim in steps 4 and 5: `EXTRACTED` (from a page you fetched, with URL and the
  date checked), `INFERRED` (from your knowledge, one-sentence basis) or `UNKNOWN`.
- A status claim (legacy, end of life, version, price, law) with no fetched vendor or
  primary-doc URL does not stay in steps 4 or 5. Move it to the unverified list under the
  questions, labelled `INFERRED`, so the user knows to check it.
- Tool and method names stay in the main answer even without a fetched URL. Label an
  unfetched one `INFERRED`. A novice needs the names where the work is described.
- If you do not know how an expert in this field works, say "I don't know for sure" and stop.
  A made-up method sends the user the wrong way with false confidence.

## Retro log

The log is `~/.claude/ask-like-expert-retros.md`, outside every repo. Create it with this header
if it is missing:

```text
| Date | Field | Score 1-5 | Note |
|---|---|---|---|
```

On `rate`, append one row: today's date, the field from the last rewrite, the score, and the user's
note verbatim. Then confirm in one line.

## Improve mode

1. Read the retro log. If it has fewer than three rows, say so and stop.
2. Group the rows with a score of 3 or less by what went wrong.
3. For each group, propose one edit to this SKILL.md: the line to change and the new text.
4. The user picks which edits ship. Do not edit the skill until they pick. Shipping an edit is a
   plugin release (`/personal-plugin-release`).

The scoring rubric for test runs is [evals/judge-rubric.md](evals/judge-rubric.md).
