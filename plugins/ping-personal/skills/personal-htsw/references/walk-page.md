# walk-page -- the clickable walk-through page (`now --deep --html --walk`)

Read this before you write a walk spec. `--walk` is a flag on `now --deep --html`. It is not the
`walk` mode. You write one JSON file (the walk spec). `walk/walk-build.py` turns it into a page.
`walk/walk-check.py` scores the page.

## When to use --walk

Use it for a plan, process, migration, proposal or decision that a busy reader must follow step
by step and then decide on. The reader should finish with answers, not just understanding.

Do not use it for:

- a status question ("where are we?") - use plain `now` or `now --deep --html`;
- code or a diff - use `code-explain` or `pr`;
- a topic with no decision and no sequence - use `walk` (the mode) or `baby`.

## The page it builds

The builder owns the structure. You only supply content. The order is fixed:

1. Hero: title, the one-sentence idea, and a "Decision needed" strip.
2. Opening: a few short points ending with Next (see Text length limits).
3. Flow chart: a clickable chart that is the table of contents (a diamond for the last step if it has `outcomes`).
4. One section per step, each with Back, Previous and Next links, and a Check yourself box.
5. Answer sheet: one question per decision, a Respond button that copies all answers.
6. Reference sections you define, then the glossary ("Words used here").

The builder adds the Next links and the hover definitions. Do not write them yourself.

## Text length limits

Every number lives in this table. Other sections say "see Text length limits".
The five character limits (title, step name, step sub, outcome label, outcome note) are scored idea
rules, `idea-len-*`. A MISS lowers the idea score and the build still passes. The must rules fail the
build. They are the opening word count, points over 22 words, and lead or takeaway sentences over the cap.

| Field | Limit |
|---|---|
| `title` | 40 characters or fewer, spaces included |
| step `name` | 28 characters or fewer (about 4-5 words) |
| step `sub` | 40 characters or fewer |
| outcome `label` | 16 characters or fewer |
| outcome `note` | 24 characters or fewer |
| `idea` | under 30 words |
| opening | 4-6 points, 40-110 words in all (about 80 is ideal) |
| every point, lead and takeaway sentence | 22 words or fewer, target 20 |
| `analogy` | 3-5 per page, cap 5 |
| `check` | on at least half the steps |
| visual | on at least 75% of steps |
| glossary hovers | 10 or more shown in the text (one per term per section) |

## How to make the reader catch the idea

This is the core of the mode. The page works only if a reader who skims still gets the point.

1. Write `idea` first. One sentence, plain words. A contrast or a metaphor is fine.
   Example: "Phase 0 builds the road, not the houses, so clients see no change."
2. Write `decision` second. It is today's ask, in one sentence. Example: "Approve phase 0, then fill in the answer sheet."
   Copy it from the source. If neither the source nor the conversation states it, ask the person who
   requested the page before you build. If you cannot ask them (for example you are a subagent) or they cannot answer, name the question
   the audience faces. Make the outcomes that question and its plain negation. Put "(suggestion)" in
   each outcome's table row and answer-sheet choice text, never in the 16-character label. Say in the
   last step that the source does not set it. Never write "to be set", "TBD" or "TODO" anywhere the
   reader sees (the checker fails it: `no-placeholder-text`). A source term that contains todo or TBD (a file name
   `TODO.md`, a status mark `[todo]`) goes in backticks, because the checker skips code. Context the caller gives (the audience,
   the ask) is recorded as caller context, never presented as a source fact.
   An ask the requester gave you counts as stated: no "(suggestion)" tag; say in the last step it came from the requester.
3. Cut the source into 6-14 steps. Each step teaches one thing. If a step needs two ideas, split it.
   Every step is something that happens, not a motive. The "why" goes in the opening, not in step 1.
   The decision step is always the LAST step, because the engine draws the diamond only there. If the
   reader decides before the process ends (for example "approve tonight's release" before the rollback),
   make the last step the decision itself. The decision step counts toward the 6-14 steps. Put what happens after it inside its blocks or the answers.
   If you add the decision step yourself, the flow lead says "N steps, then the decision".
   Never put `outcomes` on a step about failure. Put each top-level rule or exception of the source
   (for example "skip a phase only when you can say why") in the opening. When the opening is full,
   move the rule to step 1. The motive stays in the opening.
4. For each step write these fields in this order:
   - `name`: a claim that says what the step does or proves. It appears in the chart, menu, heading
     and links, so the chart alone tells the story. Never a topic, and never a generic name
     (The goal, Overview, Background, Next steps, Summary, Problem). The checker warns
     (`idea-claim-names`) when many names lack a verb. A decision step names who picks what, for example "Support picks use or skip".

     | Bad (a topic) | Good (a claim) |
     |---|---|
     | Safety floor | Serious risks never get dropped |
     | Open questions | Three answers before loop 1 |
     | The problem | Reviews miss what matters |
     | Rollout | Clients see no change |

   - `sub`: a short hint in the chart box that says what the step gives the reader.
     Never copy the source's own numbering ("Phase 3") and never use bare jargon.
   - `lead`: the one sentence the presenter says first. It is a claim: it says what the step achieves
     or why it matters. It never starts "The X is ..." (definitions go in the glossary).
     The checker warns (`idea-lead-is-claim`, `idea-lead-not-name`).

     | Bad (a definition) | Good (a claim) |
     |---|---|
     | The router is the front door that sends each click | One switch decides where each click goes |
     | The log is a file of every change | Every change leaves a trace you can read |
     | The gate is the last review before release | Nothing ships until one person says yes |

   - `takeaway`: one sentence that restates the lead's claim in new words. It adds no new point and
     never echoes the lead (checker: `idea-takeaway-not-echo`).
   - Lead and takeaway must read correctly with zero glossary lookups. Use at most one glossary term,
     and only after an earlier step said it in plain words (a self-check the checker does not test). Sentence length: see Text length limits
     (must rule `lead-takeaway-short`).
   - `check`: a question whose answer is the step's key point. The answer is one sentence.
     The answer is an action or result a person can see. It is not the lead restated and not a slogan.
     Bad: a recall question whose answer is a number or a name ("How many phases are there?").
     Good: a "what happens if" question whose answer is the step's point ("What happens if a risk is
     serious but the owner is away?").
   - `analogy`: only where the idea is abstract, taken from the reader's daily life (count: see Text
     length limits; more than the cap triggers `idea-analogy-cap`). An analogy explains a concept.
     It never adds facts, numbers or claims about the real system.
5. Pick the visual by idea type. The checker counts only `stats`, `ba`, `chips`, `svg`/`svg_file`
   (a figure), `analogy` and `table`. `note` and `done` are supporting blocks and do not count.
   The step-level `analogy` field counts as that step's visual.

   | Idea type | Block |
   |---|---|
   | Comparison, or items that exist side by side | `table` |
   | Change from today to later | `ba` (before and after) |
   | Sequence or pipeline (steps that happen in order) | `chips` |
   | Alternatives (two or more options) | `table` (Option, Effect) or `ba` with `"kind": "options"`. Never `chips`. |
   | Numbers that exist in the source | `stats` (never invent a number) |
   | Mechanism with moving parts | `svg_file` (you draw one SVG file) |
   | Open risk or warning | `note` with `tone: warn` |
   | Finished-when list | `done` |
   | List of rules or conditions | `table` with columns Rule and Effect |
   | Decision step with `outcomes` | `table` of each outcome and what happens next |

   Things that exist side by side go in a table, never in a `ba` block. `ba` is for change.
   Table Effect cells say what a person does or sees. When the source lists N items, show all N
   (table rows) or write "N-k more in the source" and say where to find them. Keep ordering words
   such as "in this order" and "last resort". A stat count must match the list the page shows.
   When the source gives no options for the ask, use the ask and its plain negation.

6. Writing rules for every point (bullets, table cells, notes):
   - One sentence per point (length: see Text length limits). No semicolons.
   - The checker measures list points: bullets, numbered items, chips (they are list items too),
     `done` items, `ba` items and the opening bullets. It does not measure table cells or notes,
     but keep those short too.
   - Say who does what. Name a term, then say what it does.
   - Mark each proposal "(suggestion)". Use "(recommended)" only as step 7 allows. The builder styles both tags.
   - Never invent numbers, owners, thresholds, content or scope. If the source gives none, leave the
     point out or tag it "(suggestion)". The `ba`, `note`, glossary meanings, consequences, check
     answers and decision restate source facts. Copy the source's scope words ("hard bugs", not "every ticket").
   - Put every technical term in `glossary`. A hover shows once per term per section, and only where the term appears word for word in the text.
   - Use `bullets` blocks, never paragraphs. The checker fails stray paragraphs.
7. End with questions. One question per real decision. Give each `choices` with a short `effect` line
   (what happens, what it costs). Set `"tag": "recommended"` only when the source or the requester recommends that choice. When the source sets no answer, put "(suggestion)" in the choice text and set no tag. For an open
   question, set `choices` to null (see Questions). The `outcomes` of the decision step become the
   hero pills, so make them mirror the deciding question's choices. An outcome label is the short
   form of its choice.
8. Source facts come from the conversation or the document the user named. Mark unknowns as unknown.

### Keep the meaning

Run this checklist before you build. Fix the spec for any line that fails.

- Source coverage: list each heading and each top-level rule or exception of the source. Map each to
  the step that carries it, or mark it "omitted on purpose" with a reason.
- Every condition and exception survives ("mandatory when installed" stays conditional).
- Do not make a source claim stronger than it is. Checking syntax and tracing values is not a test
  run. "Read first" is not "only after the records run out".
- A count says what is counted. Do not turn "six entries" into "six files".
- Every materially different branch in the source survives, in the steps and in the SVG.
- Every unknown that affects the decision becomes a question or a named owner.
- A field with no source value is left out. The engine does not default `when`.
- Every chart box is an action or event, and the motive sits in the opening.

## Draw the mechanism

Every page draws at least one SVG of the core mechanism, on the step that carries the idea. Draw
whatever moves: a router, a loop, a pipeline with branches. Use `svg_file` and save the file in the same
folder as the spec. Rules for the file:

- One `<svg>` element only, with `viewBox` width 600-760.
- Colors only through page tokens in `style` attributes, so dark mode works: `var(--ink)`,
  `var(--muted)`, `var(--line)`, `var(--hi)`, `var(--a)`, `var(--a-soft)`, `var(--b)`, `var(--b-soft)`,
  `var(--c)`, `var(--c-soft)`, `var(--ok)`, `var(--ok-soft)`, `var(--warn)`, `var(--warn-soft)`. Never write a hex color.
- Text uses `style="font-family:var(--sans)"` with sizes 13, 15 or 18 only (checker: `svg-font-tokens`).
  Labels fill `var(--ink)`, notes fill `var(--muted)`.
- Exactly one emphasized path, the path that matters, uses `stroke:var(--hi);stroke-width:2.5`. Other
  arrows use `var(--line)` or `var(--muted)` (checker: `svg-emphasis`).
- A box that carries meaning gets a group fill (`--a-soft`/`--a`, `--b-soft`/`--b`, `--c-soft`/`--c`),
  never plain `var(--panel)`. The end state uses `--ok-soft`/`--ok`. A blocked or dropped box uses fill `var(--warn-soft)` with stroke `var(--warn)`.
- Every box is something that happens (an action or an event), never a motive.
- Draw only the branches the source names. One branch is one path, not a fork. For alternatives, each
  branch leaves the same box, gets its own box, and carries a label with its condition. Arrows mean
  "then", so options never get arrows between them.
- Every `id` inside an author SVG must be unique on the page and must not start with `wb-`, which the
  engine reserves (`unique-ids`, a must rule).
- `role="img"` and an `aria-label` that says the idea in one sentence.
- No `<script>`, no `on*` attributes, no external links. ASCII only.
- On a phone the figure scrolls sideways inside its own box, so keep the labels short.

Starter to copy and edit (the router forks to two boxes, each branch labeled, one emphasized path):

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 200" role="img"
  aria-label="A request goes to the router, which sends it to the old page or the new page, depending on the switch.">
  <defs>
    <marker id="fig1-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto">
      <path d="M0 0L10 5L0 10z" style="fill:var(--muted)"/>
    </marker>
    <marker id="fig1-arrow-hi" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto">
      <path d="M0 0L10 5L0 10z" style="fill:var(--hi)"/>
    </marker>
  </defs>
  <g style="font-family:var(--sans);font-size:15px;fill:var(--ink)" text-anchor="middle">
    <rect x="10" y="75" width="120" height="50" rx="8" style="fill:var(--a-soft);stroke:var(--a)"/>
    <text x="70" y="105">Request</text>
    <rect x="190" y="75" width="120" height="50" rx="8" style="fill:var(--b-soft);stroke:var(--b)"/>
    <text x="250" y="105">Router</text>
    <rect x="470" y="20" width="150" height="50" rx="8" style="fill:var(--c-soft);stroke:var(--c)"/>
    <text x="545" y="50">Old page</text>
    <rect x="470" y="130" width="150" height="50" rx="8" style="fill:var(--ok-soft);stroke:var(--ok)"/>
    <text x="545" y="160">New page</text>
    <text x="400" y="45" style="font-family:var(--sans);font-size:13px;fill:var(--muted)">switch says old</text>
    <text x="400" y="175" style="font-family:var(--sans);font-size:13px;fill:var(--muted)">switch says new</text>
  </g>
  <path d="M130 100H188" style="stroke:var(--muted);stroke-width:2;fill:none" marker-end="url(#fig1-arrow)"/>
  <path d="M310 90L468 45" style="stroke:var(--muted);stroke-width:2;fill:none" marker-end="url(#fig1-arrow)"/>
  <path d="M310 110L468 155" style="stroke:var(--hi);stroke-width:2.5;fill:none" marker-end="url(#fig1-arrow-hi)"/>
</svg>
```

## Hero picture (optional, recommended)

The top-level key `hero_visual` (`{svg_file, caption}`) puts one picture of the idea itself in the
hero's right column. It replaces the step map, which the flow chart already shows. Draw the mechanism
the `idea` sentence names. A metaphor is fine only if the mechanism also shows. Test: name one
source-specific fact a reader could recover from the picture alone. Never draw the steps. Optional
`hero_links` makes up to 5 parts of the picture jump to a step (the builder checks both ids). The builder gives each linked part a glow and a focus ring, so its
colours may change. Keep the linked part's label inside or next to it. Rules:

- Use the SVG rules of Draw the mechanism (page tokens, `var(--sans)`, ids unique and not starting
  with `wb-`), except the font sizes and colors below. Keep one `--hi` emphasis.
- `viewBox` is 560 wide and 260-360 tall. The drawing fills its box, with no empty band taller than 1/4 of the viewBox height.
- Label size floor: hero text must render at 12px or more on a 375px phone. So `font-size` is at
  least 22 units at a 560-unit viewBox width (scale with the viewBox width). Use few, short labels
  taken from the idea sentence. Center each label under or on its shape (`text-anchor="middle"`, within 28 units), no `dx`.
  Checker: `hero-text-size` (scored).
- Hero palette: the hero background is always dark. Text placed directly on it uses `var(--hero-ink)`
  for labels and `var(--hero-muted)` for support text. Text inside a filled shape uses the page
  tokens of that shape (`var(--ink)` on `--a-soft` and so on). Faint fills use base tokens (`--a`, `--hi`,
  `--ok`) with `fill-opacity`, never `*-soft` tokens and never element `opacity`.
- Drawn objects need a recognizable silhouette, not UI controls. Draw the real thing: a road is a
  wide band with lane dashes in perspective, not a slider bar with knobs. Markers are signs or pins,
  not round handles. Test: hide every label; you should still recognize each object.
- Every control and every relationship in the idea sentence has a visible link. A switch has a
  leader line to what it switches. In the hero, dashed means "not yet"; in the flow chart it means "runs alongside". Never use dashes for "optional".
- The picture never repeats the idea sentence in words: no title text inside the SVG.
- Always give `role="img"`, an `aria-label` of 8+ characters that states the idea, and a `viewBox`. With `hero_links`, the builder changes the role to `group`. `idea-hero-visual` tests the role and the label only.
- Optional motion classes: `hv-in` fades an element in, `hv-draw` draws a path and keeps your dash
  pattern. Put no `transform` or `opacity` on an `hv-in` element; put them on a parent `g`.
- The caption is one short line that names the relation the labels cannot show, never a list of labels, or is left out. Good: "Road open, houses
  not built." Bad: "Phase 0 is safe."
- Checker: `idea-hero-visual` (scored, not a must rule).

## Spec format

The file is JSON, pure ASCII. Create it with a file-write tool, never a shell heredoc. Each block is an object with exactly one key.

### Top-level keys

| Key | Meaning | Example shape |
|---|---|---|
| `title` (required) | Page title and hero heading. | `"AppHost 7 - Phase 0"` |
| `steps` (required) | The step list, 6-14 items. | `[ {step}, ... ]` |
| `glossary` (required) | Term and one-sentence meaning pairs. | `[["Router", "Sends each user to the old or new page."]]` |
| `answers` (required) | The answer sheet. See Questions. | `{"questions": [...]}` |
| `opening` (required) | The opening points. | `["Phase 0 prepares the move."]` |
| `idea` | One-sentence idea shown in the hero. | `"Phase 0 builds the road, not the houses."` |
| `hero_visual` | One picture of the idea in the hero. See Hero picture. | `{"svg_file": "hero.svg", "caption": "Road first, houses later."}` |
| `hero_links` | Up to 5 hero svg element ids that jump to a step on click. | `{"hv-switch": "s8"}` |
| `decision` | Today's ask. Shown in the hero and the opening. | `"Approve phase 0."` |
| `subtitle` | Line under the title. | `"PROJ-824 - the plan, step by step."` |
| `eyebrow` | Small label above the title. | `"Walk-through - PROJ-824"` |
| `key` | Storage key for saved comments. Default is the title. | `"proj824-phase0"` |
| `categories` | Step colour groups. Steps use `cat` to pick one. See below. | `[{"id": "a", "label": "Measure and prepare"}]` |
| `opening_title` | Opening heading. Default "Why we are here". | `"Why we are here"` |
| `flow_title`, `flow_lead` | Chart section heading and lead sentence. See below. | `"The flow of phase 0"` |
| `flow_caption` | One string or a list, shown under the chart. | `["Opened steps turn green."]` |
| `chart_label` | Accessible label for the chart. | `"The 12 steps."` |
| `reference` | Extra reference sections after the answer sheet. | `[{"id": "ref-steps", "title": "All steps", "blocks": [...]}]` |
| `glossary_title` | Heading of the glossary section. | `"Words used here"` |

### Step keys

Step ids must be `s1`, `s2`, ... in order. The checker finds steps by that pattern.

| Key | Meaning | Example shape |
|---|---|---|
| `id` | Anchor id. `s1`..`sN`. | `"s3"` |
| `name` | A claim (see Text length limits). | `"Every decision gets a record"` |
| `sub` | A short hint. | `"answers come after step 12"` |
| `cat` | One of the `categories` ids. | `"a"` |
| `lead` | First sentence of the step. | `"Every decision becomes a one-page record."` |
| `blocks` | The visuals and points. | `[{"bullets": ["..."]}]` |
| `takeaway` | The Remember box. | `"Records keep the reason, not only the choice."` |
| `analogy` | Think-of-it-like-this text. | `"A diet starts with stepping on the scale."` |
| `check` | Check yourself question and answer. | `{"q": "Is it final today?", "a": "No, step 5 confirms it."}` |
| `edge_note` | Short label on the arrow to the next step. | `"logs arrive"` |
| `alongside` | Optional, 1 to 4 words, 24 chars max. Needs a step before and after it in the same column (the desk chart puts the first half of the steps, rounded up, in column 1); not first or last in a column, not before the decision, not next to another alongside step. Draws a dashed box, a stub ending in an open circle, and a solid bypass arrow. | `"while others go on"` |
| `outcomes` | Last step only, and that step is the decision. Makes the diamond. | `[{"label": "Go", "tone": "ok", "note": "-> start"}]` |

Outcome tones: `ok`, `warn`, `change`, `a`, `b`, `info`.

`flow_lead` is one sentence that says how the steps add up to the idea. Example: "Twelve steps lead to
one go, change or stop decision." Never write a UI instruction such as "click a box". The checker warns
(`idea-flow-lead`) when it does.

Category ids are `a`, `b`, `c`, `d`: `a` teal (measure, prepare), `b` copper (build), `c` violet-slate
(a third phase), `d` green (decide or done). An unknown id falls back to `a`.

### Block types

| Block | Meaning | Example shape |
|---|---|---|
| `bullets` | Short points. | `{"bullets": ["The team writes the criteria."]}` |
| `numbered` | Ordered points. | `{"numbered": ["Back up.", "Deploy."]}` |
| `h3` | Small heading inside a step. | `{"h3": "Final today"}` |
| `table` | Comparison table. Cells may hold links. | `{"table": {"head": ["Question", "Why"], "rows": [["[4 Stack](#q4)", "Used for years."]]}}` |
| `chips` | Sequence with arrows. Chips and arrows mean "then", so never list alternatives here. | `{"chips": ["Plan", "Build", "Test"]}` |
| `note` | Callout. Tone `info`, `warn`, `ok`, `change`. | `{"note": {"tone": "warn", "title": "Open risk", "text": "The log may be late."}}` |
| `analogy` | Analogy box inside the blocks. | `{"analogy": "Like a road before houses."}` |
| `svg_file` | One SVG file next to the spec. ASCII, one `<svg>` only. | `{"svg_file": {"file": "flow.svg", "caption": "How a click is routed."}}` |
| `svg` | Same, with the SVG inline. | `{"svg": {"svg": "<svg ...></svg>", "caption": "..."}}` |
| `done` | Checklist of finish conditions. | `{"done": ["Decisions are written."]}` |
| `ba` | Before and after columns, for change. Add `"kind": "options"` for alternatives: it shows "or" and no arrow. | `{"ba": {"before_title": "Today", "after_title": "After", "before": ["..."], "after": ["..."]}}` |
| `stats` | Big numbers. Every value shows as a static number, with no count-up. Ranges and decimals ("2.5M-3.5M", "1.5M") are fine. | `{"stats": [{"value": "18", "label": "questions"}]}` |
| `html` | Raw HTML. A last resort: use any other block first. | `{"html": "<div>...</div>"}` |

Inline text (points, cells, lead, takeaway) supports `[text](#id)` links, `**bold**`, `` `code` `` and the tags
`(suggestion)`, `(recommended)`, `(for expert discussion)`. Link to a step with `[Step 5](#s5)` and to a
question with `[Question 4](#q4)`. Question ids are `q1`..`qN` in the order you list them.

### Questions (the `answers` object)

| Key | Meaning | Example shape |
|---|---|---|
| `title` | Heading of the answer sheet. | `"Answer sheet for Acme"` |
| `lead` | One sentence under the heading. | `"Each answer becomes a decision record."` |
| `bullets` | How to fill it in, 3-4 points. | `["Pick one choice per question."]` |
| `respond_title` | Title of the copied summary. | `"Phase 0 - answers"` |
| `questions` | The question list. | `[ {question}, ... ]` |

A question has `title` (short), `ask`, `why` (why it matters), optional `when` (a deadline such as "Final today.") and optional
`choices`. Leave `when` out unless the source gives a value. The sheet shows nothing for an omitted `when`. Each choice is `{"text": "...", "tag": "recommended", "effect": "what happens if chosen"}`.
With no `choices` (omit it or set `"choices": null`, for example `{"title": "Owner", "ask": "Who signs off?", "why": "A named owner avoids delay.", "choices": null}`), the sheet shows a free-text box. Every question also gets "Other" and a note box.

## Build and check

Write the spec next to the page (`<path minus .html>.walk.json`), then run:

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/personal-htsw/walk/walk-build.py" <spec.json> --out <path>
python "${CLAUDE_PLUGIN_ROOT}/skills/personal-htsw/walk/walk-check.py" <path> --spec <spec.json>
```
If `CLAUDE_PLUGIN_ROOT` is unset, use `plugins/ping-personal` from the repo root.

The builder exits with a message when the spec is missing a key, has a bad block, or holds a non-ASCII
character. Fix the spec and rebuild. The checker prints one PASS, FAIL or MISS line per rule and a final
SCORE line. Exit code 0 means every must rule passed.

When walk-check fails:

1. Read each FAIL line. The detail names the offending text, step or missing target.
2. Fix the spec, never the built HTML, then run both commands again.
3. Repeat until every must rule passes. Do not hand over a page with a FAIL.
4. MISS lines are idea rules. Fix the cheap ones (a missing takeaway, check or analogy). Report any left.

## Checks

`walk-check.py` groups its rules. "Must" rules fail the build. "Idea" rules only score. Numbers: see Text length limits.

| Group | Rule ids | Must |
|---|---|---|
| Page order | order of opening, chart, steps, answer sheet, Reference divider | yes |
| Content | `opening-40-110-words`, `chart-text-no-overlap`, `lead-takeaway-short`, `no-placeholder-text`, glossary, semicolons, stray paragraphs, a lead per step | yes |
| Chart | box per step, diamond, legend, scroll box | yes |
| Navigation | menu, name match, Back/Previous/Next, links | yes |
| Answers | why, Other, note, comments, Respond, floating button | yes |
| Look and Motion | `unique-ids`, ASCII, theme, type tokens, focus rings, fonts, reduced motion, animation library | yes |
| Idea | `idea-claim-names`, `idea-lead-is-claim`, `idea-lead-not-name`, `idea-takeaway-not-echo`, `idea-analogy-cap`, `idea-flow-lead`, `idea-mechanism-svg`, `idea-hero-visual`, `hero-text-size`, `svg-font-tokens`, `svg-emphasis`, takeaway, check, glossary hovers, visual coverage, text length rules | no |
