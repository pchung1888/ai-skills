# How To Create An Eval -- A Complete Field Guide

> Distilled from three sources that agree more than they disagree:
> 1. **First principles** -- `agent-evals-playbook.md` (the YouTube-talk distillation).
> 2. **First implementation** -- the ping-personal 13-skill eval suite built this session
>    (`skills/<skill>/evals/`, `run-all.ps1`).
> 3. **The real demo** -- Anthropic's `cwc-workshops/eval-driven-agent-development`
>    (the actual workshop the talk came from), studied by a 6-agent sweep. **Only finished
>    patterns are taken from it; its instructive defects are taught as lessons, not copied.**
>
> Where the demo CONTRADICTS the playbook, that is called out explicitly (Section 11) -- those
> contradictions are some of the most useful lessons here.

---

## 0. The one-sentence definition

An eval is **a decision instrument**: a repeatable measurement that answers "did my change make
the output better, worse, or just different -- and which case regressed?" It is not a final exam
you run once at the end. It is the **thermometer you hold while building**, so you stop guessing
and start measuring.

The prime directive of the whole loop:

> Do not ask "how can I make this better?" Ask **"which measured failure should I remove next?"**

---

## 1. The measurement loop (what you actually do)

```text
define a fixed task set
  -> run the agent/skill to produce artifacts
  -> grade each artifact (code graders + judges)
  -> read the PER-CASE scorecard (not just the average)
  -> inspect the failures
  -> change exactly ONE lever
  -> rerun the SAME tasks
  -> compare deltas against a PINNED baseline
  -> lock any new regression into the eval set
```

Two words carry most of the weight, and the demo makes them concrete in a way the playbook only
gestures at:

- **PINNED baseline.** Deltas compare against a baseline recorded once, *not* against the
  previous run. (`eval-runner.ts:84-88`: "Deltas always compare against the pinned baseline ...
  so re-running the same round shows movement vs. the naive starting point, not noise.") Diffing
  against last-run makes every rerun look like motion; diffing against a frozen baseline shows
  true cumulative drift. **This anchor choice is load-bearing and the playbook never names it.**
- **ONE lever.** Each round changes exactly one thing (a prompt rule, or the model, never both)
  so a delta is attributable. The demo proves this with Round 4: byte-identical naive prompt,
  only the model swapped -- isolating the model lever from the prompt lever.

---

## 2. Anatomy of a real eval system (the demo's architecture)

This is the single most transferable thing the demo teaches that the playbook does not: **how the
pieces are wired.**

### 2.1 Lever vs Subject -- grade the artifact, version the config

The thing you *iterate* (the LEVER) is not the thing you *grade* (the SUBJECT).

- Lever in the demo: `resources/agent.yaml` -- a model name + a system prompt + a tool list.
- Subject: the `output.pptx` the agent produces. The eval never reads the YAML; it runs the
  agent, downloads the artifact, and grades the bytes.

**Transfer:** for a Claude Code skill, grade the *files/output the skill produces*, not the
`SKILL.md` you are tuning. Version the lever (the prompt/skill text); measure the subject (its
output).

### 2.2 The harness/rubric split -- a metric-agnostic runner

The runner knows nothing about slides. It builds one context per case and maps `grade(ctx)` over a
list of grader objects. Adding a metric is appending one object; the harness never changes.

```text
harness (fixed):  build context -> Promise.all(GRADERS.map(g => g.grade(ctx))) -> score.json -> delta -> table
rubric (grows):   GRADERS = [ {grade1}, {grade2}, ... ]   <- you only ever edit this list
```

`eval-runner.ts:94` is literally `GRADERS.map((c) => c.grade(ctx))`. **Keep the run/score/delta
machinery completely separate from the list of metrics.** This is the structural reason you can
grow an eval by editing a data array.

### 2.3 GraderContext -- build the fixture once, grade many

The expensive, grader-independent work (parse the artifact into structural facts, render it to the
modality a judge needs, open the API client) happens **once per case**; every grader receives the
same immutable context and stays a pure function `context -> value`.
(`eval-runner.ts:39-70 buildContext`, `types.ts:42-59 GraderContext`.)

### 2.4 Render-before-judge (when the artifact is visual/binary)

If a judge evaluates a *rendered* form (image, running app, rendered HTML) rather than source, the
harness must (a) render in a **hermetic** step (the demo uses a throwaway Docker container with
LibreOffice + poppler and **pinned metric-compatible fonts** so geometry matches Office), and (b)
**always regenerate** -- `rm -rf render/` before grading. A cached render silently scores the OLD
artifact: the subtlest eval bug there is. (`render.ts`, `eval-runner.ts:60-67`.)

### 2.5 Baseline / delta / show-baseline

- First run with `--baseline` writes `baseline.score.json` next to `score.json`. Same code path,
  one boolean -- so the baseline file format is byte-identical to a normal score file.
- The `--baseline` run **suppresses its own deltas** (`previous: pinBaseline ? undefined`) so it
  never prints `(+0)` against itself.
- `show-baseline` re-prints the stored numbers with **zero re-grading / zero model calls** -- a
  pure file read. This is only possible because `score.json` persists the *headline value* per
  grader, not just raw data.

### 2.6 Reporting -- per-case first, average only the noisy columns

`summarize()` prints **one row per task**, each cell carrying TWO orthogonal signals:

- **Absolute heat** -- a red->yellow->green background from the grader's own declared
  `scale {min,max,good}`.
- **Relative delta** -- a signed `(+N)/(-N)` vs the pinned baseline.

These can disagree: a cell can be **green-but-regressed** or **red-but-improving**. Encoding both
stops you optimizing one while blind to the other. Only `kind:'judge'` columns get an averaged
footer line; deterministic code metrics are shown per-case only -- never collapse a hard metric to
an average that could hide one catastrophic case. (`eval-runner.ts:138-247`.)

### 2.7 The run matrix is 2-D and expensive

Variants x cases. Each cell is one (costly) agent run. The demo's `batch.ts` bounds concurrency on
the costly axis (rounds sequential, the 5 tasks parallel within a round), makes every cell
**resumable** (skip if `output.pptx` exists) and **grade-in-place** (partial results survive a
crash). That is "never just an average" realised as a matrix.

---

## 3. The grader contract (the declarative shape to copy)

Every metric is one object satisfying this interface (`graders/types.ts:13-36`):

```ts
interface Grader {
  name: string;                 // scorecard column header
  kind: "code" | "judge";       // code = deterministic, judge = model call
  description: string;          // one line; doubles as the rubric
  grade(ctx: GraderContext): Promise<number | string> | number | string;
  format?(v: number): string;   // e.g. v => `${v*100}%`
  scale?: { min: number; max: number; good: "high" | "low" | number };
}
```

Three things worth stealing:

1. **`kind` tag.** Lets the harness fan out identically while you reason about cost (judges call a
   model; code does not) and report them in separate regions.
2. **`scale.good` has THREE modes**, not two:
   - `'high'` -- maximize (image-presence, judge scores).
   - `'low'` -- minimize a defect count (emoji, clutter, text-density).
   - a **number** -- hit an exact spec (slide-count `good: 5`); drift in *either* direction reds
     out. This exact-target mode is underused and valuable for "must equal N" contracts.
3. **A grader may return a STRING.** `producedResult` returns `'missing' | 'invalid' | 'ok'`.
   Categorical code graders are first-class, not forced into 0/1.

---

## 4. Code graders (the cheap, deterministic truth -- build these first)

### 4.1 Parse-once, extract-many

Push ALL parsing into one pure extractor that returns typed structural facts (counts, lengths,
sizes, presence flags) and **zero scoring policy**. Then each code grader is a 2-3 line threshold
over those facts. (`parse-pptx.ts` returns `SlideMetrics`; each `code/*.ts` grader is ~15 lines.)
A parsing bug is then fixed in one place, not seven, and graders read like a rubric.

### 4.2 The artifact check has THREE states, not two

The first grader for any artifact-producing skill distinguishes **produced-nothing vs
produced-garbage vs produced-valid** (`missing` / `invalid` / `ok`). Folding "missing" and
"corrupt" into one boolean hides whether the agent *failed to act* or *acted wrongly* -- totally
different fixes. Encode it in the parser's return type so every downstream grader inherits a cheap
short-circuit (no render, no judge, if the artifact is invalid).

### 4.3 The demo's code-grader catalogue (concrete instances of the playbook taxonomy)

| Grader | Type | `good` |
|---|---|---|
| produced-result (missing/invalid/ok) | artifact-exists + valid-container | n/a (categorical) |
| slide-count | count, exact target | `5` |
| slides-with-image | ratio (share %) | `high` |
| text-heavy (>300 chars) | boundary count | `low` |
| cluttered (>20 shapes) | boundary count | `low` |
| small-font (<14pt) | boundary count | `low` |
| emoji-count | count | `low` |

---

## 5. Judge graders (for taste code cannot measure)

### 5.1 Structured output, schema-enforced

Judges call `client.messages.parse({ output_config: { format: zodOutputFormat(schema) } })` with
`ScoreSchema = z.number().int().min(0).max(5)`. The score is bounded **by construction** -- an
out-of-range or non-integer score is impossible, and `resp.parsed_output` is already typed (no
manual JSON parsing, no null guards). Treat a missing structured block as a **drop**, not a zero.

### 5.2 One memoized call, many criteria (cost control)

When several columns derive from the same judgment, make **one** call that emits all dimensions and
fan cheap graders off a memoized result. The demo's `judgeAll` is `memoize`d on the ctx object and
returns text/image/layout/color in one vision call per slide; four judge graders each average their
own field -> 4 columns at 1x model cost. (The playbook's separate usefulness/groundedness judges
can often be one multi-field call.) Memoize per-criterion only when a call is unique to that grader.

### 5.3 Calibration tricks the playbook under-specifies

- **Anti-leniency line:** `"Give scores across the full spectrum (0-5) instead of only good ones
  (3-5)."` LLM judges cluster at 3-5; one sentence restores discriminating power. Cheap, copyable.
- **No-data sentinel:** return `'-'` (a string the aggregator skips), never `0`, when there is
  nothing to judge. "No data to judge" must be distinct from "judged and scored zero," or a missing
  artifact masquerades as a terrible-but-real score and corrupts the average.
- **Anchoring is a spectrum:** none -> endpoints-only -> full 0/1/3/5. Don't tick the "anchored
  rubric" box just because a scale exists. The demo anchors its coherence judge at endpoints
  (0 = different topics, 5 = body answers title) but gives its four aesthetic criteria **no
  per-level anchors at all** -- a real gap, flagged here so you do better.

### 5.4 Guardrails encode a POLICY, not a universal rule

The playbook's flagship example is "no image => image_score must be 0." The demo does the **exact
inverse on purpose**: "Do not penalize the slide if no image is involved." Both are correct -- for
different policies:

- If the modality is **required**, absence = failure (score 0).
- If the modality is **optional**, absence = neutral (full credit), and you track presence with a
  **separate code grader** instead.

**The deeper rule (Section 11): decouple "is the thing present" (a code grader) from "is the thing
good IF present" (a judge).** Never make one judge answer both.

---

## 6. The failure curriculum -- the demo's instructive defects (the real gold)

The playbook says "a grader can be silently wrong" in one line. The demo *shows* it, with file
evidence and a controlled contrast. **These are lessons to internalize, not code to copy.**

### 6.1 Metric scope != intervention scope (the "dense" bug)

`text-heavy` counts `textChars` across **all** runs (title + header + body). Round 1 told the agent
to trim **body** copy only. So a real body reduction moved nothing: `MORNING.md`: *"dense didn't
move; grader counts all text, rule said body only."* The body-only field
(`slideTexts[i].body.length`) existed one field away and went unused. The **same** all-text
extraction was simultaneously **correct** for the emoji grader (rule = "none anywhere").

> **Wrongness is relative to the intervention, not the code.** Test every metric: *"If the agent
> does exactly what this round asks, will THIS number move?"* When you change one thing and an
> expected mover stays flat, **suspect the grader before the agent.**

### 6.2 Dead metric -- never discriminates (the "font<14" finding)

`small-font` reads ~the same value (4.0-5.0) across five very different agent configs:
`MORNING.md`: *"never moves, dead metric."* A column that returns the same value under every
condition is dead weight -- it costs a column and adds zero decision value, whether stuck high or
stuck low.

> **Validate that each metric SPLITS your known-good and known-bad cases before shipping it.** Drop
> or re-threshold any column that stays flat across your easy/edge/regression examples.

### 6.3 A grader that penalizes compliance

Worse: the same `font<14` grader fires on any sub-14pt run, but Round 1's own typography rule
**mandates** "Captions: 10-12pt." So a deck that **obeys** the rubric is guaranteed to trip the
grader -- R1 (which introduced captions) scores **worst** on it. **Co-design the grader and the
prompt rule against the same unit**, or your metric anti-correlates with correctness.

### 6.4 Parser blind spots silently corrupt structural metrics

`small-font` only sees fonts carried as an explicit size attribute; runs that **inherit** size from
the slide master are invisible (`undefined`, dropped before the filter). The count is a floor, not
a true count -- a false-negative generator that looks fine on the scorecard. **Document what your
extractor cannot see.**

### 6.5 Prose guardrails are unreliable -- proven by data

The "do not penalize missing image" guardrail is a sentence in the judge prompt. The three rounds
with zero images scored `jImage` = 0.86 / 0.26 / 2.06 -- same condition, three different scores,
never the value the prose implied. **Express guardrails as deterministic CODE post-processing**
(`if no_image: image_score = 0`), not as advice to the model. The measured spread is the proof.

### 6.6 The unwired-registry trap (the one you warned about)

The demo's *live* registry `src/graders.ts` is a **mid-refactor stub**: one grader plus a literal
`// more graders...` comment. The complete set lives in `src/graders/all.ts` -- which **nothing
imports** (grep-verified). So `npm run eval` as checked in prints a one-column scorecard, and the
10-column `MORNING.md` table was produced by an earlier/presenter-local state that cannot be
reproduced from the commit.

> **Verify the import graph before trusting any registry.** Never quote a stub as "the eval" nor an
> orphaned solution file as "what runs." This is exactly the "don't copy unfinished" hazard: the
> finished grader *objects* (`code/*`, `judge/*`) are excellent references; the *wiring* is not.

### 6.7 Process wins are invisible to artifact evals ("the trace is the show")

Round 3 added a mandatory self-QA loop (the agent rasterizes its own deck, hunts bugs, fixes,
re-renders). The scorecard barely moved -- because Round 2 was already clean -- yet the real win is
in the agent's **transcript** (it finds and fixes its own defects). **Decide up front whether your
eval scores ARTIFACTS or PROCESS, and don't conclude "no improvement" from a flat artifact
scorecard when the lever targeted process.**

---

## 7. The hill-climb loop in practice (the demo's progression)

| Round | Lever changed | Targeted | Result (vs naive baseline) |
|---|---|---|---|
| 00 naive | -- | baseline | emojis 13, img% 0, dense 4.0 |
| 01 polish | + typography/density/anti-AI-tells (prompt) | text, emojis | emojis 13->0; **dense flat (grader bug)** |
| 02 diagram | + "every slide needs a real matplotlib image" (prompt) | img%, jImage | img% 0->100, jImage 0.9->4.1 -- the visible win |
| 03 qa-loop | + self-rasterize-inspect-fix (prompt) | layout, density | marginal on the scorecard; **the trace is the show** |
| 04 model-swap | naive prompt, Sonnet->**Opus** (model) | -- | best jText/jLayout/jColor, **worst** structure (img% 0, coherence tanks), **5x cost** |

The meta-lessons:

- **"Different lever, same eval."** Freezing the task set + graders lets you compare a 5x-cost
  model swap against a free prompt edit on identical axes -- and reveals that **best-taste and
  best-structure can be different agents.** Per-axis reporting (not one average) is what makes the
  tradeoff visible.
- Hold the eval CONSTANT while you vary the agent. The moment the eval set drifts, your deltas are
  meaningless.

---

## 8. Designing the eval SET (the playbook's prescription)

A good eval set is more than happy paths:

- 5 easy (should pass if the thing basically works)
- 5 realistic (representative day-to-day)
- 5 edge (missing data, weird formatting, long context, ambiguous request)
- 5 regression (known past failures that must stay fixed)
- 3 adversarial (inputs likely to expose shortcuts)

> **Honest note:** the demo's *committed* `tasks.json` has only 5 untiered topics and cannot
> reproduce its own published "10-task / 50-deck" numbers. That is a **gap in the demo, not a model
> to copy.** Use the playbook's tiering; treat the demo as the architecture reference.

Record each case with: id, task, input files, expected behavior, must-pass, must-not, graders.

---

## 9. First-implementation patterns (the ping-personal 13-skill suite)

What we actually shipped this session, and why -- the bridge between the playbook and a Claude Code
skill repo (where the "artifact" is often markdown + helper scripts, not a .pptx):

- **The 3-file shape per skill:** `evals/eval-plan.md` (the WHY: target behavior + failure-mode map
  + ship gate), `evals/eval.ps1` (the deterministic red/green grader), and -- only for taste-heavy
  skills -- `evals/judge-rubric.md` (the reason-first model-judge rubric).
- **Calibration fixtures:** every grader is proven against a **known-good** fixture (must pass) AND
  **known-bad** fixtures (must fail). htsw feeds its own checker a conforming rendering + two broken
  ones. *A grader that passes everything is measuring nothing.*
- **Wrap, don't duplicate.** Skills that already shipped a test suite (`personal-workflow`'s
  `smoke.ps1`, `personal-md-to-html`'s `smoke.py`) have evals that **invoke** those suites and add
  only frontmatter/structure checks -- never a re-implementation.
- **Structural graders for instruction-only skills.** With no script to run, grade STRUCTURE:
  frontmatter integrity, required sections present, **referential integrity** (the lesson router's
  4 domains exist on disk; critic-gate's ms-mario agent exists), append-target path matches the
  skill name.
- **The aggregator + PROVE ITS RED PATH.** `run-all.ps1` runs every skill's grader and prints
  `ALL EVALS PASS` only if all are green. Crucially, we proved its **failure** path too: a planted
  failing eval made it print `EVALS FAIL` / exit 1 and *not* falsely pass. The aggregator is itself
  a grader, and "a grader that passes everything measures nothing" applies to it most of all.
- **Evals surface real bugs.** The md-to-html eval immediately found a pre-existing dead test
  (`pos_sample_plan_as_dashboard` referenced a golden that never existed) -- exactly what an eval is
  for. We fixed it by making the optional golden SKIP-when-absent (announced), not hard-fail.

---

## 10. The synthesis -- how to create an eval for ANY skill

### CREATE (a skill has no eval yet)

1. **Name the target behavior** in one plain-English contract: given X, the skill must produce Y
   with properties Z, and must NOT do W.
2. **List the top ~10 failure modes.** This list IS the eval map.
3. **Classify each failure:** code-checkable -> code grader; subjective-but-visible -> judge;
   high-stakes/untrusted -> human spot check. *If code can check it, use code.*
4. **Identify the LEVER vs the SUBJECT.** What do you edit (skill text/prompt/model)? What does the
   user receive (the artifact)? Grade the subject.
5. **Build the extractor first** (parse the artifact into typed facts), then write thin code graders
   as one-object-per-metric in a declarative registry. Include the 3-state artifact check as #1.
6. **Add judges only for what code cannot reach.** Structured-output, bounded score, one memoized
   multi-criteria call, anti-leniency line, no-data sentinel, guardrails as code, reasons-first if
   the judge proves unreliable. Decouple presence (code) from quality-if-present (judge).
7. **Calibrate every grader:** confirm it passes a known-good case and fails a known-bad case, and
   that it SPLITS your examples (no dead metrics).
8. **Build the runner/aggregator** with a pinned baseline, per-case reporting, and a proven RED
   path.
9. **Run the baseline. Change one lever. Rerun. Compare per-case deltas. Lock regressions.** Never
   claim improvement from vibes.

### ENHANCE (a skill already has an eval)

1. **Audit for dead metrics:** which columns never moved across your runs? For each, decide -- true
   null result, or a grader measuring the wrong scope? (Run the "will this number move if the agent
   obeys?" test.) Drop or re-scope.
2. **Audit scope mismatches:** does each grader measure the unit the skill's rule actually controls?
3. **Audit guardrails:** any prose guardrail in a judge -> move it to deterministic code.
4. **Audit anchoring:** upgrade endpoints-only / no-anchor judges toward 0/1/3/5; add the
   anti-leniency line; put the rationale field FIRST if you want reasons-before-score.
5. **Add the missing tiers** from the eval-set design (edge / regression / adversarial) -- especially
   a regression case for every bug the eval has ever caught.
6. **Verify the import graph / wiring:** is every grader you think runs actually registered? (The
   unwired-registry trap.)
7. **Re-baseline only when intended.** Don't let the eval set drift mid-comparison.

---

## 11. Where the demo CONTRADICTS the playbook (read this twice)

| Playbook says | The real demo does | The refined rule |
|---|---|---|
| Judges: **reasons before score** | Score fields first, `comment` last; no reason-first instruction | Reasons-first is a **lever you ADD when a judge proves unreliable**, not a baseline every judge follows. If you want it, put the rationale field first AND instruct it. |
| Guardrail: **no image => score 0** | "Do **not** penalize if no image" (the inverse) | The "0" rule is right only when the modality is **required**. If optional, absence = neutral; track presence with a separate code grader. **Decouple presence from quality.** |
| Judges: **anchored 0/1/3/5** | One judge endpoint-anchored, four judges not anchored at all | "Anchored" is a spectrum; state which level you have. Unanchored taste criteria are a gap to fix, not a template. |
| Eval set: **~23 cases, 5 tiers** | 5 untiered topics; can't reproduce its own numbers | Use the tiering. The demo is the **architecture** reference, not the **eval-set** reference. |
| Every grader is **actionable** | Two graders are dead/mismeasuring **by the workshop's design** | A real suite WILL contain inert/wrong-scope graders. Auditing them is part of the loop. |

The contradictions are not the demo being wrong -- they are the demo being **real**. A shipped eval
makes cheaper choices than the ideal, and a metric that looked fine can be silently broken. That gap
between the tidy playbook and the messy reality is the most valuable thing in this whole study.

---

## 12. Anti-patterns (merged, all three sources)

- Optimizing to a judge you have not validated.
- Writing the change first, then inventing the eval to justify it.
- Looking only at the best output; reporting only an average.
- Letting the eval set drift while you use it to measure progress.
- Treating a model-judge score as objective truth (it is a signal; stack it on a safety boundary at
  your peril).
- Asking a judge for a score before evidence (when bias matters).
- A grader that measures a different scope than the rule it checks (silent wrongness).
- A metric that never moves (dead weight) -- and not noticing.
- A prose guardrail where a code guardrail belongs.
- Trusting a registry without checking its import graph (the unwired stub).
- Concluding "no improvement" from an artifact eval when the lever targeted process.
- A grader that passes everything -- including an aggregator whose red path you never proved.

---

## 13. The rule of thumb (tape this to the wall)

> If the failure can be checked with code, check it with code.
> If it is subjective but visible, use a model judge with anchors and an anti-leniency line.
> If it is high-stakes or the judge is untrusted, use a human on a small calibration set.
> Pin a baseline, change one lever, rerun the same tasks, read per-case.
> **If you cannot explain what a score means, the score is not ready to optimize.**
> And the test that outranks all others: *if the agent does exactly what this round asks, will this
> number move?* If not, fix the grader before you touch the agent.
</content>
