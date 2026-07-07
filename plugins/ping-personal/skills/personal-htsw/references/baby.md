# baby -- the story-first analogy-alongside-jargon playbook

## What this is for

You point at a thing (code, spec, plan, system) and the reader needs to understand it -- but they haven't seen this particular system before. Baby mode teaches by pairing every jargon term with an everyday physical object. The jargon stays literally on the page; the analogy is a companion, not a replacement.

v0.3.0 invariant: the reader watches the play; characters introduce themselves.

## The best-analogy rule

Before writing any character, stop and ask: what does the declared audience do every day? What objects, processes, roles, and places are in their immediate lived experience? Pick analogy characters from THEIR world, not from a generic "easy" world.

A retail investor thinks in household budgets, restaurant tabs, and grocery receipts -- not office buildings. A voter who follows news thinks in neighborhood disputes, family arguments, and school playground politics -- not libraries. A fiction-writing student thinks in cooking, music composition, theater rehearsal, and gardening -- not warehouses. A junior database engineer thinks in libraries, card catalogs, and reference desks -- not theaters.

The analogy lands when it is drawn from the audience's daily lived experience, never from a fallback default. If multiple domains fit, pick the one with the strongest cast of named roles -- people who do specific jobs the reader can picture doing right now, not abstract objects.

Apply two filters to every character before it goes on the page:

1. **Action filter.** Can the reader picture this character DOING something specific? "Stamp machine" fails (no person, no verb). "The receptionist who copies the whiteboard onto Post-its and sticks them on the outside of the door" passes.
2. **Domain filter.** Does this character live in a world the declared audience inhabits in daily life? A receptionist works for a junior FE dev (office building experience). A receptionist FAILS for a fiction student (their experience is closer to a stage manager during rehearsal). For each audience, the same technical concept gets a different character drawn from the audience's world.

The 4-to-N worked anchors in `baby-examples.md` are illustrative, not bounding. The skill is genuinely universal -- pick the best analogy for each invocation, do not default.

A reader who finishes a baby-mode rendering should be able to:
1. Describe what the system does using the physical analogy (mental model built).
2. Name the technical terms for each piece (vocabulary acquired).
3. Talk to a senior engineer without needing a translator.

That's the test. If the analogy replaced the jargon, the reader passes test 1 but fails tests 2 and 3. That's the failure the previous kid/family/non-tech mode shipped with -- and the reason it was dropped. Baby mode is the replacement.

**Voice:** mentor-explains-to-curious-junior. The reader is smart and capable; they just haven't seen this system before. Never talk down to them. No kindergarten voice.

## What baby mode is NOT

- **Not a sanitizer.** Do NOT remove technical terms. `useEffect`, `useState`, `verifyAttrs()`, `registerUnit()` must appear in the output -- unredacted, unaliased, exactly as engineers use them.
- **Not a walk-mode rendering with a Cast table stapled on.** The analogy must be woven through the prose AND the diagram. A Cast table followed by jargon-only prose is not baby mode.
- **Not a verdict.** No tier title (no GOOD/PASS/WARNING/BAD). No 🌮 opener, no 🔴 opener as a section head.
- **Not a pitch.** Use `boss` mode when the audience is a sponsor.
- **Not condescending.** If the prose sounds like you're explaining to a toddler, rewrite it. The reader chose to ask; treat that as intelligence.

## D9 Audience Declaration (REQUIRED -- every baby rendering)

Every baby rendering must declare who it is written for. The audience shapes which analogy domain to pick.

**Syntax:** First line immediately after the citation must be:

```
_For: <audience persona -- what they know, what they don't know>_
```

Italic single-line. Required. Non-empty body.

**Examples:**
- `_For: junior front-end developer -- knows JS and the DOM, has never written React_`
- `_For: junior data engineer -- knows SELECT and WHERE, has never seen CTEs or window functions_`
- `_For: new QA engineer -- knows browser dev tools, has never written automated tests_`
- `_For: amateur Claude skill author -- knows markdown, has never written a SKILL.md_`

**Auto-detection when no `--for` flag is given:**

| File extension / name | Inferred audience |
|---|---|
| `.tsx` / `.jsx` | junior FE dev -- knows JS, never written React |
| `.sql` / `.sp` / `.proc` | junior data engineer -- knows SELECT, not CTEs/window functions |
| `*.spec.ts` / `*.spec.js` / `*.verify.ts` | new QA -- knows browser dev tools, not test infra |
| `SKILL.md` | amateur Claude skill author -- knows markdown, not frontmatter/triggers |
| `*.asp` / `*.bas` / `*.vb` | junior VBScript dev |
| fallback | engineer who knows the language but not this codebase |

**Override:** `/personal-htsw baby <path> --for "<persona>"` overrides the auto-detect.

**Analogy-domain consequence:** the author MUST pick analogies from a world the declared audience already inhabits. A junior SQL dev does not have React component-tree intuition; office-building analogies land badly. Library and archive analogies land well. The validator checks only presence + non-empty body. The comprehension-proxy subagent (Phase 4) catches domain mismatch because the proxy IS the declared audience.

## D5 Cast Persistence Rule

Once a baby rendering establishes a Cast of Characters in a conversation thread, **follow-up questions in the same thread MUST extend that cast, not start a fresh analogy universe.**

**Rule in plain English:**
- First rendering in a thread: pick any physical-analogy universe (office, library, theater, recipe kitchen, etc.). Build the Cast.
- Follow-up rendering in the SAME thread: open with a one-line continuity nod ("(continuing the office story -- new character enters)"), then run a short story for the new characters only. Cast recap at the end shows the FULL roster with each row tagged `inherited` or `new` in a Status column.
- New conversation / different thread / unrelated topic: pick any universe you like. Fresh starts are allowed; mid-thread pivots are not.

**Why this matters:** the physical world is the reader's memory anchor. If the errand boy (`useEffect`) becomes a courier pigeon two messages later, the reader has to re-learn the map from scratch.

**What the v0.3.0 Cast-extension looks like in practice:**
- Follow-up opening: "(continuing the office story -- `registerUnit` walks on.)"
- Cast recap table at end: `| jargon | analogy | status | role |` -- inherited rows tagged `inherited`, new rows tagged `new`.
- Inherited rows: exempt from the inline-intro check (they were introduced in the previous rendering).
- New rows: must have a bold subject-position inline-intro before the Cast table.

The v0.2.0 "Cast extension note" text marker is replaced by the Status column. Do NOT write `**Cast extension note:** Rows 1-N inherited...` anymore. Use the Status column.

**Follow-up detection heuristic:**
- Does the current conversation already contain a baby-mode rendering?
- Do the noun phrases in the new question overlap with terms in the previous Cast's jargon column?
- If BOTH are true: extend the existing Cast. Do not pivot the universe.
- If either is false: a fresh universe is fine.

## Required structure (v0.3.0 story-first order)

Baby-mode renderings have 6 mandatory sections. Length cap: 1800 words inline / 3000 words persisted, with a per-section soft warning at >400 words per `###` section.

### 1. Citation line (REQUIRED)

First line: `_Explaining: <source> · purpose: baby_`

No variation allowed. The validator splits multi-example files on this exact pattern.

### 2. Audience declaration line (REQUIRED -- D9)

Second line (immediately after citation):

`_For: <audience persona -- what they know, what they don't know>_`

The validator checks for presence and non-empty body within the first 5 lines after the citation.

### 3. Title (REQUIRED -- descriptive, not a verdict)

An H2 heading (`##`) that names the subject, not the mode. Pick from this library OR write one in the same shape:

- `## How the <X> framework hangs together`
- `## The shape of <subject> -- what each piece actually does`
- `## What <X> really does and how it talks to <Y>`
- `## How <X> works -- the office analogy`
- `## The mechanics of <subject> -- jargon and analogy side by side`
- `## How <X> hangs together (the sticky-notes version)`

Banned title patterns:
- Generic heads: `## Explanation`, `## Overview`, `## Summary`, `## Introduction`
- Verdict openers: anything starting with `🌮`, `🔴`, `⚠`, `🟢`

### 4. TL;DR block (REQUIRED)

Right after the title. Label: `**TL;DR -- the core idea:**` or `**TL;DR -- short version:**` or `**TL;DR -- in one breath:**`. Never a verdict label.

Use `📦` for physical-object analogy bullets. Use `🏷️` for label/tag bullets connecting jargon to analogy. Walk navigation icons (`▶ ⚙ 🧠 🚧 📍`) are also available. Verdict icons (`🔴 ⚠ 🟢 🌮`) are FORBIDDEN here.

Shape:
```
**TL;DR -- the core idea:**

- 📦 **errand boy (`useEffect`)** -- fetches once on mount; never re-runs unless the whiteboard changes.
- 📦 **whiteboard on the wall (`useState`)** -- the value the whole room can see; React redraws when it changes.
- 🏷️ **receptionist (`verifyAttrs()`)** -- copies whiteboard values onto Post-its on the door every time the whiteboard changes.
```

2-4 bullets. <= 15 words per bullet. <= 60 words for the whole block.

### 5. HOW-THIS-WORKS section (REQUIRED -- the main explainer, the story)

The load-bearing artifact. This is where the vertical story lives. Pick one heading from the shared HOW-WORKS library -- optionally prefixed with `📦` or `🏷️`:

- `### 📦 How this shit works`
- `### 🏷️ Under the hood`
- `### How this shit works`
- `### What this actually does`
- `### Under the hood`
- `### The flow`
- `### The mechanics`
- `### The plumbing`

Content rules:

- **Open with a brief scene-setter** (1-2 sentences): where are we? what is the system doing right now?
- **Introduce each character as the story reaches them.** The character's FIRST mention must be a dedicated sentence where the term is bold and the character is the subject, followed immediately by a parenthetical or dash gloss with the analogy and role. Examples:
  - `**The errand boy (`useEffect`)** (the character who fetches data once when the room opens) walks to the back room and pulls the rows.`
  - `**`useState`** (the whiteboard on the wall -- the value the whole room reads) gets the new numbers written on it.`
- **Never introduce a character inside a subordinate clause.** Characters are sentence subjects, not parenthetical asides.
- **Use BOTH vocabularies in every sentence** that introduces a new step.

**The story-rhythm block (REQUIRED within the HOW-WORKS section):**
A fenced code block (triple backticks, no language tag) showing the vertical scene as a chain. Each step is its own line. Characters appear when they enter the action.

Required shape:
- >= 5 pipe-only connector lines (`   |`)
- >= 5 lines that each contain a parenthetical analogy gloss `(...)` at least 5 chars long

Example:
```
Page loads (the office opens for the day)
   |
useEffect fires (the errand boy walks to the back room)
   |
Database query runs (errand boy opens the filing cabinet, pulls the rows)
   |
useState set (errand boy writes the value on the whiteboard)
   |
React repaints (painters read the whiteboard, redraw the room)
```

Plain code block (triple backticks, no language tag) for universal rendering. Fit within ~90 columns.

### 6. Cast of Characters table (REQUIRED -- at the END)

The recap. Every jargon term that appears in the rendering must have a row here. This table is a reference you reach for when you forgot who character N was -- not an upfront roster you must memorize.

**Position:** the `### Cast of characters` heading MUST appear in the last ~30% of the rendering (byte offset >= 65% of total doc length). The validator enforces this.

Fixed header: `### Cast of characters`

**Standard 3-column shape (new thread / first rendering):**
```
| Jargon | Analogy | What it actually does |
|---|---|---|
```

**4-column shape with Status (follow-up rendering -- D5):**
```
| Jargon | Analogy | Status | What it actually does |
|---|---|---|---|
```

Status values: `inherited` (introduced in a prior rendering) or `new` (first appearance in this rendering).

Rules:
- Minimum 3 rows.
- "Jargon" column: the exact technical term -- wrapped in backticks.
- "Analogy" column: a concrete physical object or role from one consistent universe. Must be tangible.
- "What it actually does" column: one-line technical description.
- Every term in the Jargon column MUST appear in the story body BEFORE the Cast table (the validator checks this).

**D5 inline-intro exemption:** inherited rows (Status = `inherited`) are exempt from the inline-intro requirement -- they were introduced in a previous rendering. New rows (Status = `new`) still require a bold subject-position intro before the Cast table.

> The Cast recap at the end is for reader scan-back AFTER the story has landed. It is never a substitute for inline character introduction in the story body.

### 7. Optional sections (same as walk mode)

These are optional but usually useful:

**The knobs / Watch out for / Where to look** -- same shapes as walk.md sections 6, 7, 8. Use navigation icons (`▶ ⚙ 🧠 🚧 📍`). The `🔴` inline-punctuation rule from walk mode applies here too.

## Icon reference for baby mode

| Icon | Use it when... |
|---|---|
| `📦` | Calling out a physical-object analogy in TL;DR bullets or prose |
| `🏷️` | Labeling the connection between jargon and analogy |
| `▶` | Flow step (same as walk mode) |
| `⚙` | Mechanism -- how something works internally |
| `🧠` | Non-obvious -- read carefully |
| `🚧` | Known wart that works |
| `📍` | Focal point -- here's where to look |
| `🔴` | Inline only -- something genuinely broken the reader must know about |
| `🌮` | Inline only -- a piece of design that's genuinely beautiful (once or twice max) |

Verdict icons as tier titles or TL;DR openers: FORBIDDEN.

## Banned words

Two categories of banned words. The validator enforces both mechanically.

### Sanitization smells

These words signal that the explanation is replacing thinking instead of supporting it.

- `easy` -- if it were easy, they wouldn't be asking
- `simple` -- same problem
- `just` -- as in "you just call the function" -- minimizes the actual complexity
- `basic` -- often condescending
- `don't worry` -- clearest signal of kindergarten voice; delete it

### Baby-talk words

These words make the voice sound like adult-explains-to-toddler.

- `sweetie`
- `honey`
- `ok kiddo`
- `buddy`
- `lil'` (as in "lil' trick")

None of these belong in htsw output.

## Human contracts (validator cannot enforce, author carries)

These are load-bearing rules that a regex cannot check:

1. **Analogy domain matches audience.** A SQL dev does not have React intuition. Pick analogies from the world the declared `_For:` audience already inhabits.

2. **Analogy concreteness.** The analogy must be a physical, tangible thing or role (errand boy, filing cabinet, whiteboard, stamp machine) -- not an abstract metaphor ("a coordinator of state" is not an analogy).

3. **Universe consistency within a thread.** Once you pick an office world, stay in it. Do not mix "errand boy" (office) with "conveyor belt" (factory) in the same rendering unless you explicitly acknowledge the shift.

4. **Characters have actions.** Each analogy should carry a verb. "The stamp machine" is weaker than "the receptionist who copies the whiteboard onto Post-its." Characters do things; labels just exist.

5. **Jargon first, analogy second.** In prose, lead with the jargon or use both together. Never write "the errand boy fetches data" when you mean "the errand boy (`useEffect`) fetches from the filing cabinet (`Database`)". The jargon must be visible.

6. **Diagram dual-vocabulary coverage.** Every Cast jargon term should appear in at least one diagram node alongside its analogy.

## What the validator checks mechanically (v0.3.0)

The validator (`htsw-check.py`) runs `check_baby` and enforces:

a. **D9 audience declaration present.** `_For: <non-empty body>_` within the first 5 lines after the citation. FAIL if absent or empty.

b. **HOW-WORKS section present** at `###` level, with a recognized header phrase (optionally prefixed with `📦` or `🏷️`). FAIL if absent or body < 30 words.

c. **Story-rhythm block present.** A fenced code block (no language tag) with >= 5 pipe-only connector lines AND >= 5 lines containing a parenthetical analogy gloss of >= 5 chars. FAIL if no qualifying block found. The block's line range is emitted to INFO stream.

d. **Cast table in the last ~30%.** `### Cast of characters` heading byte offset >= 0.65 * total content length. FAIL if Cast heading appears too early.

e. **Cast table has >= 3 rows** shaped `| jargon | analogy | role |` (or 4-col with Status).

f. **Every Cast term appears in story body before the Cast table** (at least once). FAIL if any term has 0 occurrences before the heading.

g. **Every new Cast row has a bold inline-intro before the Cast table.** First occurrence of the term in story body must be inside a bold span (`**term**` or `**phrase (term)**`) followed within ~120 chars by a parenthetical `(` or dash `--` gloss. Inherited rows (Status = `inherited`) are exempt. FAIL if any new row's first occurrence is not in this shape.

h. **Label-only analogy WARN (soft, stderr only, does NOT fail).** For each Cast analogy cell, if the cell contains no verb-indicator (no word ending `-s`/`-es`/`-ing`/`-ed`, no `who`/`that`/`which`), emit: `WARN (baby): analogy '<cell>' may be label-only`.

i. **Banned sanitization words absent:** `easy`, `simple`, `just`, `basic`, `don't worry` (case-insensitive).

j. **Banned baby-talk words absent:** `sweetie`, `honey`, `ok kiddo`, `buddy`, `lil'` (case-insensitive).

k. **Length cap:** <= 1800 words inline, <= 3000 words persisted.

l. **No verdict action-verb TL;DR label** (same rule as walk mode).

m. **No H2 heading opens with verdict icons** (`🔴 ⚠ 🟢 🌮`).

**Caveat -- how term matching actually works (S3, carried from v0.2.0):**
- Backtick characters are stripped from the Jargon cell before matching. So `` `useEffect` `` becomes `useEffect` for counting.
- Matching is **case-sensitive**. `props` does NOT match `verifyProps`.
- Matching is **substring**. Keep Cast terms specific enough that accidental substring matches are not a concern.

The validator does NOT check: analogy-domain-matches-audience (that is the comprehension-proxy's job), analogy concreteness, diagram dual-vocabulary coverage. These are human contracts.

## Examples

`references/examples/baby-examples.md` -- four worked examples demonstrating audience-distinct analogy domains:

1. **Anchor 1** -- junior front-end developer. React TodoApp (useState, useEffect, verifyAttrs, props, Database). Analogy domain: office building (errand boy, whiteboard, receptionist, Post-its, index card from building manager).
2. **Anchor 2** -- junior data engineer. SQL CTEs and window functions. Analogy domain: library archive (reference desk, card catalog clerk, shelf boundary marker, stamp).
3. **Anchor 3** -- new QA engineer. Playwright spec follow-up. Analogy domain: theater (director, prompter, stage manager, audience checker). Demonstrates D5 Cast Persistence with Status column (2 inherited rows + 2 new rows).
4. **Anchor 4** -- amateur Claude skill author. SKILL.md frontmatter and body contract. Analogy domain: recipe book (recipe card, head chef, kitchen instructions, pantry).
