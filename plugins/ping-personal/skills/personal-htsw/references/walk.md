# walk — the explainer / how-it-works playbook

## What this is for

You point at a thing (code, spec, plan, conversation, feature, system) and ask "how does this work?" — and you want an answer that teaches, not grades. You're not reviewing it. You're not testing it. You're not pitching it. You want to understand it.

That's walk mode. The default when `/personal-htsw` is invoked with no mode arg. The output uses the htsw voice — blunt, plain English, no jargon-without-translation, no sales-pitch sanitization — but it doesn't pass a verdict.

## What walk mode is NOT

- **Not a verdict.** No tier title (no GOOD/PASS/WARNING/BAD). No 🌮 opener, no 🔴 opener.
- **Not a review.** It will not flag every imperfection; if you want a review, use `pr`.
- **Not a test plan.** It will not enumerate ACs and test cases; if you want a test plan, use `qa` pre-test.
- **Not a pitch.** It will not launder the language for a non-engineering audience; if you want a polished pitch, use `boss`.
- **Not a code dump.** It will not paste 200 lines of source then add three sentences. Source quotes are punctuation; the explanation is the artifact.

## Source resolution

Whatever you point it at — a file, a function, a Jira ticket export, the current conversation, a 600-line plan, a commit hash. Walk mode is the most forgiving with source shape because the goal is *understanding*, not *grading*. **No anti-leakage rule** in walk mode: commit messages, docstrings, README excerpts, prior conversation are all fair input. The user wants context; give it context.

## The voice — two modes (Mode 3 not used as a structure-level signal)

| Mode | When | Sounds like |
|---|---|---|
| 1 — Baseline | Most of the rendering — explaining what's there | "OK so this thing reads X, decides Y, writes Z. The catch is W." Blunt. Direct. No salt unless something specifically deserves it. |
| 2 — Salty (PG/R) | When a piece of the design is **genuinely** weird, ugly, or wrong — and the reader should know about it | "This part's a goddamn weird design choice but it works because X." "There's a hack here — `On Error Resume Next` swallowing everything; **probably** intentional but worth knowing." |

**Mode 3 (🌮) is NOT a structural opener in walk mode.** Don't put 🌮 in the title; don't lead the TL;DR with it. It can appear *inline* exactly once or twice when there's a piece of design that's genuinely beautiful and a newcomer might miss why — e.g. `The clever bit is the idempotent re-entry guard at line 47 🌮 — without it the cache would corrupt on retry.` That's fine; it's punctuation, not a verdict.

**Banned in walk voice:**
- The f-word (same as all modes)
- Praise-washing — "everything looks good" without saying why
- Pretending you understand something you don't — use the honest protocol below
- Verdict openers — "this is great", "this is a mess", "block this"

## Honest protocol (plain English)

- If you can't tell what a piece of code does, say "I can't tell from this; read X to confirm."
- If you're inferring from naming or surrounding context, lead with "looks like" or "**most likely**".
- If the source doesn't describe a behavior, say "the source doesn't say" — don't fill it in.
- Don't invent file paths, function names, or line numbers to round out the explanation. Empty pointers > made-up pointers.

A confident wrong explanation wastes more time than admitting a gap.

## Evidence — light-touch in walk mode

When walk-mode prose makes a specific factual claim ("the SP returns 0 on success", "the page redirects to Error.asp with ErrNum=50001"), the claim should be anchored to a file:line, a quoted source line, or an explicit "looks like" hedge. Walk mode isn't accusatory like PR/QA — but it's still factual writing, and the rendering's whole value depends on those facts being right.

When walk mode hits something *genuinely broken* and inline-flags it with 🔴, that 🔴 inherits the evidence-and-suggestion contract: a file:line citation AND a `→ note:` or `→ ask:` arrow saying what to do with the information. Don't drop a 🔴 in walk mode without a citation; it reads as drive-by.

## Explainer discipline — the four karpathy pillars (walker's form)

The same Karpathy pillars that govern review (`pr.md`) and test design (`qa.md`) apply to teaching:

| # | Pillar | Walker's form |
|---|---|---|
| 1 | **Surface assumptions** | If the source is ambiguous, **say so**. "I can tell X is happening; I can't tell whether the loop is intentional." Don't smooth over confusion with vague phrasing. |
| 2 | **Simplicity first** | Minimum explanation that gets the reader to understanding. If a 4-sentence paragraph would do, don't write 12. Don't pad with restated context. |
| 3 | **Surgical scope** | Explain the thing the user pointed at. Don't go on a guided tour of the surrounding module unless it's required to make the focal thing make sense. |
| 4 | **Goal-driven** | Every section should leave the reader with something concrete they didn't have before — a flow diagram, a knob name, a citation. A section that ends with no takeaway is filler. |

## The signature element — descriptive title (not a tier title)

The title names the **subject**, not a verdict. Pick one from this library OR write one in the same shape. Variation across renderings keeps the voice fresh.

**Title library — descriptive openers:**

- `## How this thing actually moves`
- `## The shape of <subject>`
- `## What this <thing> really does`
- `## Under the hood of <subject>`
- `## The mechanics of <subject>`
- `## The lay of the land — <subject>`
- `## What's actually going on in <subject>`
- `## The plumbing of <subject>`
- `## How <subject> hangs together`
- `## The moving parts of <subject>`
- `## How <X> works (the short version)`

**Banned title patterns** (validator rejects):

- `## Review` / `## PR Review` / `## Summary` / `## Overview` / `## Brief` / `## Introduction` / `## Intro` — generic stock-template heads
- `## Walk-through` / `## Explainer` — describing the document instead of the subject
- Anything opening with `🌮` — that's a GOOD-tier verdict pattern from PR/QA, not a walk-mode opener

## Required structure

Walk-mode renderings have 4 mandatory sections and 3 optional ones. Total target ≤ 700 words.

### 1. Citation line (REQUIRED)

First line: `_Explaining: <source> · purpose: walk_`

### 2. Title (REQUIRED — descriptive, see library above)

### 3. TL;DR — the core idea (REQUIRED, but the label is descriptive, not a verdict)

**Right after the title.** The label is `**TL;DR — the core idea:**` or `**TL;DR — short version:**` or `**TL;DR — in one breath:**`. The label is NOT `**TL;DR — block this:**` / `**TL;DR — ship it:**` — those are PR/QA verdict patterns.

Body is 2-4 bullets. Use navigation icons (`▶ ⚙ 🧠 🚧 📍`) OR no icons at all. Don't use `🔴 ⚠ 🟢` here — they read as verdict, and walk doesn't grade.

**Each bullet:** leads with a navigation icon (or none), then a **bolded noun phrase** naming the piece, then a short reason clause (≤ 12 words). ≤ 15 words/bullet, ≤ 60 words for the whole block.

Example:

```
**TL;DR — the core idea:**

- ▶ **Filter input arrives via AJAX** as `txtSearch` form field.
- ⚙ **Browse SP wraps it `'%' + @strFilter + '%'`** for the LIKE clause.
- 🧠 **The clever bit** — caller can pass `*` to disable wildcard wrap.
```

### 4. How this shit works (REQUIRED — the main section, 3-5 sentences)

This is the load-bearing artifact in walk mode. The other sections are scaffolding. Pick ONE heading from the standard HOW-WORKS library shared with PR/QA (`### How this shit works`, `### What this actually does`, `### Under the hood`, etc.). 30+ words; usually 60-120.

**Hedge rule:** if a sentence describes a cause-effect chain not directly observable from the source, qualify it with `most likely` / `appears to` / `seems to` / `probably` / `looks like`. Direct observations don't need hedging — only inferred mechanisms do.

### 5. The mechanism — ASCII flow, table, or numbered list (REQUIRED for non-trivial subjects, optional for one-liner subjects)

A scannable visual or list. The HOW-THIS-WORKS signature header (section 4) sits **immediately above** this element — the visual IS the explanation, the signature is the brand. **Prefer ASCII over mermaid for persisted docs** — see SKILL.md § "Diagram syntax" for the full rationale. ASCII renders in any viewer; mermaid only renders in mermaid-aware viewers (GitHub, Confluence with plugin, VS Code with extension). For a doc landing cold in someone's grep output or plain markdown preview, mermaid renders as raw source code — which is worse than no chart at all.

Pick the shape that fits the subject:

- **ASCII flow** (default for non-trivial flow / call-fanout / pipeline) — Unicode box-drawing characters (`│ ─ ┌ ┐ └ ┘ ├ ┤ ┬ ┴ ▼ ►`), wrapped in a plain code block (triple backticks, no language tag). Fits ~90 columns.
- **Table** for state-by-state or input/output mapping (≤ 6 rows)
- **Numbered checklist** for "to use this, you'd do these N things in order"
- **Mermaid `flowchart`** ONLY when the target renderer is confirmed to support it AND the diagram has dynamic-layout needs ASCII can't reasonably express. See SKILL.md § "Diagram syntax" for the mermaid syntax subset that survives Confluence's strict plugin.

Example (ASCII flow):

```
User input ──► AJAX POST ──► Browse_ajax.asp ──► clsDAL.RunSP ──► pBrowse<Entity>
     │              │                │                                   │
     │              └─ wraps as       └─ reads Request.Form               └─ wraps as
     │                 form-data         (no QueryString)                    '%' + @filter + '%'
     │                                                                       in WHERE LastName LIKE
     └─ typed in #txtSearch                                                  (substring match)
```

### 6. The knobs / what would I change (OPTIONAL, usually useful)

A short bullet list of configuration points the reader might want to know about — AppVars, feature flags, environment-specific config, "the line you'd touch to change behavior".

> - `FEATURE_FLAG_NAME` env var — flip to `'0'` to disable the gate entirely
> - `validateEligibility()` helper — change the detection predicate here (currently `productType === 'DERIVATIVE'`)
> - `ERR_INELIGIBLE` constant in `src/errors.ts` — change the error code surfaced to the UI

### 7. Watch out for (OPTIONAL — only when there's a genuine landmine)

Use `🧠` (non-obvious — read carefully), `🚧` (known wart that works), or `🔴` (genuinely broken; rare in walk mode). Each bullet is a one-sentence landmine.

> - 🧠 The `On Error Resume Next` on line 47 is intentional — it lets the SP fall through to a default path when the AppVar lookup fails. Looks like a swallowed-error smell, but **most likely** it's a fail-safe.
> - 🚧 The dummy-account bypass uses string comparison instead of an ID join — `UPPER(RTRIM(@accountId)) = UPPER(RTRIM(@dummyId))`. Works, but if the column gets a CHECK constraint someday this breaks silently.
> - 🔴 The output filename rename in a recent commit broke downstream scheduled-job consumers. → note: if you see this code, check whether the consumers got migrated. → ask: was the downstream scheduled job updated?

### 8. Where to look (OPTIONAL — pointers)

A numbered list of 1-3 things the reader should read next. File names, function names, "the implementation of X". Don't invent paths.

## Voice intensity — density rule (mild form for walk mode)

PR and QA both have a density rule that scales Mode 2 voice with 🔴 count. Walk mode rarely has many 🔴 because it doesn't grade — but the principle still applies in mild form: **don't be cheerful when the subject is a tire fire.** If the thing being explained is genuinely broken / messy / confusing, the prose should reflect that without crossing into PR/QA verdict territory.

| Subject quality | Voice load |
|---|---|
| Subject is clean, well-designed | Mode 1 throughout. One inline 🌮 allowed if a piece of design is genuinely beautiful. |
| Subject has rough edges but works | Mode 1 + 1-2 Mode 2 phrases describing the rough edges ("this part's a goddamn weird design but it works because…"). |
| Subject is broken or sketchy | Mode 1 + Mode 2 carried through the affected sections. Inline `🔴` allowed when reader needs to be warned. Title still doesn't grade. |

## What walk mode does NOT enforce (relative to PR/QA)

- **No tier-title contract.** Title is descriptive.
- **No verdict-style TL;DR.** Label is descriptive ("the core idea"), not an action verb.
- **No evidence-and-suggestion contract on every ⚠/🔴 bullet.** Only when walk *does* drop a verdict-icon inline — then the evidence requirement kicks in.
- **No deeper-dive trigger.** That's a PR-mode artifact for big diffs; walk handles big subjects by using the table/flow section.
- **No anti-leakage rule.** Walk wants context.

## Examples

`.claude/skills/personal-htsw/references/examples/walk-examples.md` — one or more rendered examples grounded in real subjects. Read these to see the voice and structure in practice.

## Validator

```bash
python3 .claude/skills/personal-htsw/personal-htsw-check.py --input-file <your-walk-rendering.md>
```

What the validator enforces for walk mode:

- First-line citation present with `purpose: walk`
- Some title in the first 15 lines, not generic, not starting with `🌮` (which would be a PR/QA GOOD-tier opener)
- No H2 heading starts with verdict icons (`🔴/⚠/🟢`) — those read as PR/QA-style verdict openers
- TL;DR label, if present, is NOT an action-verb verdict pattern (`block this`, `ship it`, `file it`, etc.)
- HOW-THIS-WORKS section present at `###` level (this is THE walk-mode artifact) with ≥ 30 words of plain-English explanation
- **Length — dual cap depending on persistence:**
  - **Inline** (invoked via `--input-string`): ≤ 700 words
  - **Persisted** (invoked via `--input-file`, `--examples-file`, or `--persisted` flag): ≤ 1200 words
- **Per-section soft warning** (advisory, does NOT fail the validator): any `###` section exceeding 300 words prints a `WARN` line to stderr. Compensates for the relaxed total cap by catching one bloated section in an otherwise OK doc.

Walk is the lightest-validated mode — structural minimums only. The honest protocol, evidence hedge, voice calibration, and "explain don't grade" rules are human-readable contracts that the validator can't check. The author carries them.

**Why the dual cap:** an inline chat answer leans on conversational context; a persisted doc landed-on-cold needs metadata, citations, code, charts — supporting material that earns its words but inflates the total count. The 700 cap was too tight for persisted docs; the 1200 cap + per-section warning is the calibrated replacement.
