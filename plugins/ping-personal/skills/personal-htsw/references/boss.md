# boss playbook — sponsor pitch (also the "clean" mode)

## What this is for

Two situations:

1. **You're pitching a feature or plan to a sponsor or client** — someone who funds the work but doesn't write code.
2. **You wrote a PR or QA explanation and want a clean version of it** — for filing in Jira, putting in an MR description, or sharing with a client. Boss mode IS the clean mode. The `clean`, `client`, `sales`, and `pitch` aliases all route here.

Boss output is always professional. No salty language, no icons, no tacos. Visual structure comes from tables, headings, and the occasional ASCII flow-bar — not from emoji decoration.

## Goal in one sentence

A non-engineering sponsor or client decision-maker (or anyone receiving a polished version of an internal explanation) understands the value, the cost, and what gets unlocked next.

## Voice rules

This playbook has a **single voice — always professional**. The `--clean` flag is a no-op when purpose is `boss`. None of the three default-voice modes (baseline / escalation / celebration) from the pr and qa playbooks apply here; sponsor pitches are a different register entirely.

**DO:**
- Lead with the **business outcome** in the very first sentence.
- Pick the right shape for the source:
  - If the source is a feature spec or product brief → use the **3-bullet sales-pitch structure** (what we're building / what it costs / what it unlocks next).
  - If the source is a multi-phase plan → use the **plan-walkthrough structure** (phase-by-phase narrative, naming what each phase lets the sponsor KNOW or REVERSE before committing to the next).
- Include one technical anchor sentence to ground the pitch ("a tamper-evident audit record linked to every state change") — then move on.
- Frame uncertainty as "phased delivery" rather than "we don't know yet."
- Close with what's being asked for, if anything (often a budget or a phased go-ahead).

**DON'T:**
- Use the words: `schema`, `validation`, `atomicity`, `hook`, `wrapper`, `JSON`, `JSONL`, `PowerShell`, `regex`, `API`, `commit`, `merge`, `deploy`.
- Cite file paths or line numbers.
- Show code or schema fragments.
- Use casual phrasing, slang, or profanity.
- Use 🌮 or warm casual praise vocabulary — those belong to pr/qa default voice, not here.
- Mention internal team-member names in the pitch.
- Overpromise — every claim must trace to something the source actually delivers. If the source only delivers Phase A, don't pitch Phase B as if it's shipping.

## Required structure — feature-pitch variant

When the source is a feature spec or product brief:

1. **Outcome sentence** — first sentence, names the business win.
2. **What we're building** — 1-2 short paragraphs, plain English, one technical anchor. Explain the problem the work solves and the shape of the solution.
3. **Cost + unlock** — bullets:
   - What it costs (effort + time)
   - What it unlocks next (the larger downstream value)
4. **What we're asking for** (optional, one sentence) — the ask.

## Required structure — plan-walkthrough variant

When the source is a multi-phase delivery plan:

1. **Outcome sentence + plan shape** — first sentence names the business win; second sentence names the overall plan shape (e.g., "phased on purpose — reversible at every step until the final one").
2. **How the plan delivers value** — phase-by-phase narrative, **best delivered as an ASCII phase flowchart** the sponsor can latch onto. For each phase, name (a) what gets built, (b) what new information the sponsor will have at the end of that phase, and (c) what reversal options remain. Emphasize KNOW vs. COMMIT — sponsors care about when they can still back out.

   Example flowchart shape (adapt to the actual phases in the source):
   ```
   Phase A (3 wks) ─► Phase B (2 wks) ─► [soak period] ─► Phase C (1 wk)
   <what it builds>    <what it validates>    <what it confirms>    <what it commits to>
   ↑ reversible        ↑ reversible           ↑ reversible          ↑ IRREVERSIBLE
   ```
3. **Cost, savings, and timeline** — bullets covering total build effort, migration risk profile, and any cost savings or future options the plan preserves.
4. **What we're asking for** — typically a phased ask (approval for Phase A only; B and C re-scoped after A produces real data).

## Variant detection

If the source contains explicit phase markers ("Phase A", "Phase B", "Phase 1", "MVP / V2 / V3", a timeline that spans multiple months with discrete milestones) → use plan-walkthrough structure.

Otherwise → use feature-pitch structure.

## Length target

Under 400 words. Maximum 3-4 sections plus the optional closer.

## Presentation tables — when they earn their place

Boss output is the one mode where tight, well-shaped **tables** are the primary visual aid. A sponsor scans a 4-row table in two seconds; the same content as prose takes a paragraph nobody reads. Use a table when:

- **Comparing today vs. after the work lands** (impact-at-a-glance).
- **Listing what each phase delivers / costs / reverses** (plan walkthrough).
- **Showing two options side-by-side** when the source describes a decision the sponsor needs to make.
- **Summarizing the cost / unlock / ask** in one final-row format.

### Recommended table patterns

**Impact-at-a-glance** (feature pitch — shows the business case in 3-5 metric rows):

| Metric | Today | After this work |
|---|---|---|
| <support-ticket category> | <baseline> | <projected> |
| <user-visible time-to-X> | <today> | <projected> |
| <reliability or NPS surrogate> | <today> | <projected> |

**Phase-shape table** (plan walkthrough — shows what each phase buys):

| Phase | Duration | What it delivers | Reversible? |
|---|---|---|---|
| A | 3 weeks | <output> | yes — flag flip |
| B | 2 weeks | <output> | yes — flag flip |
| C | 1 week | <output> | NO — final commit |

**Before/after** (when the source is a migration or replacement):

| Aspect | Current state | After Phase C |
|---|---|---|
| <thing> | <today> | <future> |

### Restraint rules (this is the "not too much" half of the user's brief)

- **Tables ≤ 5 rows.** A sponsor reads 5 lines; row 6 is for engineers.
- **One or two tables per rendering, max.** Three tables = a deck, not a pitch.
- **No emojis in boss output.** No 🎯 / 🚀 / ✨ / 🌮 / 🔴 — boss is professional; the visual structure comes from tables and headings, not iconography.
- **No bold-italic-underline pile-ups.** Use bold sparingly to mark a single key number per section.
- **No bullet-list explosions.** If you have 6+ bullets, that's a table waiting to happen.
- **The technical anchor still gets one sentence**, not a whole row. Tables are for sponsor-relevant facts (cost, timeline, impact, risk), not for shop talk.

### When NOT to use a table

- The source is short and the pitch is one paragraph + a 3-bullet ask. Don't manufacture a table to look "presentation-ready" — the bullets ARE the presentation.
- The source describes a process or sequence (use the ASCII phase flowchart from the plan-walkthrough variant instead).
- There's only one number that matters (lead with it in the outcome sentence; don't put a 1-row table around it).

## Calibration mini-example (read this first, then go to the full examples)

**Feature-pitch opener:**
> This feature eliminates the leading category of "I lost my work" support tickets by giving users a clear, two-minute heads-up before any session times out.

Note: business outcome (eliminate ticket category) → user-visible behavior (heads-up + recoverable moment) → no jargon, no file paths, no code.

**Plan-walkthrough opener:**
> This plan migrates our image-resizing infrastructure from a self-built pipeline to a managed third-party service, in three phases designed to make the switch reversible at every step until we're confident the new service is the right call.

Note: business outcome (infrastructure migration) → plan SHAPE (three phases, reversible at every step) → emphasis on what the sponsor can REVERSE, not what gets built. This is what makes the plan-walkthrough variant distinct.

**Banned-word self-check:** Neither opener uses `schema`, `validation`, `atomicity`, `hook`, `wrapper`, `JSON`, `PowerShell`, `regex`, `API`, `commit`, `merge`, `deploy`. Neither uses 🌮 or warm casual praise vocabulary. Neither cites a file path.

## Full examples reference

The canonical worked examples for this playbook live in `references/examples/boss-examples.md` — two scenarios:
- **Feature pitch** — pitching a session-timeout-warning feature to a sponsor.
- **Plan walkthrough** — explaining a 3-phase migration plan (in-house pipeline → managed service → deprecation of legacy).

Both are always-professional; there is no clean variant because boss output is already in clean form.

**When implementing the rendering, treat the examples file as the stylistic anchor.** The feature-pitch example demonstrates the business-outcome-first opening + 3-bullet structure. The plan-walkthrough example demonstrates how to narrate phases in terms of what they let the sponsor KNOW / REVERSE, not what gets built.

Key example takeaways:
- **Feature pitch** leads with the customer-visible business outcome ("eliminates the leading category of 'I lost my work' tickets"). Banned-word list is fully observed. Close with a concrete ask.
- **Plan walkthrough** leads with the plan SHAPE ("phased on purpose"), and each phase is described in terms of risk-management value (reversible by configuration change until Phase C). This is what sponsors actually want to know — when they can still back out — and it is the unique value the plan-walkthrough variant delivers over the feature-pitch variant.

## When the source is short

If the input is a short artifact (one paragraph, a one-line summary), drop the "Required structure" formality and produce one tight paragraph plus the cost/unlock bullets. Same voice rules apply.

## When the source has no clear business outcome

If the source is purely technical (a refactor or a bug fix with no client-visible impact), the boss rendering is harder. Prefer the framing "this prevents X failure mode that would cost Y" or "this enables future work Z." If neither applies, output a short note: `_This source is purely technical with no clear sponsor-facing value. Consider running /personal-htsw pr instead._`
