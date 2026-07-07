---
name: personal-prototype
model: sonnet
description: Prototype-before-you-commit conductor. Hand it a feature and it generates N genuinely distinct implementation approaches (default 5), researches the problem space, builds an HTML artifact comparing them (live mockup for UI features, decision-matrix doc for non-UI), previews and iterates it with /browse, helps you pick the winner with explicit why/pros/cons/cost, then implements the chosen option, verifies it, matches the host style, and opens a PR with a screenshot. TRIGGER on /personal-prototype or natural phrases like "prototype this feature", "give me N options for", "mock up a few approaches to", "compare implementation options for", "I cannot decide how to build X -- show me choices". Use it whenever the user wants to SEE and COMPARE several ways to build something before committing code, not just one.
---

# /personal-prototype

A thin **conductor**. It does not reimplement browse, loop, or ship -- it sequences
phases and routes each to a tool that already exists. Same house style as
`personal-workflow`: a phase pipeline with a fence and honest verification.

The job: turn "I want feature X" into "here are N ways to build X, here is the one
I recommend and why, and here it is implemented + verified + in a PR."

## Core principle -- fidelity comes from real artifacts, not prose

When you are prototyping against an EXISTING surface -- a screen already in the host
app, a design comp, or the user's reference screenshots -- those real artifacts ARE
the spec: the real markup, the real CSS classes/tokens, the real icons, and the
reference images. Pass those artifact paths to every builder, and builders MUST Read
them (open the files / Read the images), never work from a prose summary. Building a
known surface from a text description produces layouts the user rejects.

This is CONDITIONAL: a greenfield feature (no surface exists yet) has no artifact to
match, so build from the brainstormed intent instead. State which case you are in.

## Invocation

```
/personal-prototype                         # interactive: ask for n + feature
/personal-prototype <feature text>          # n defaults to 5
/personal-prototype <n> <feature text>      # explicit count
/personal-prototype --tournament <feature>  # build real variants + critic-gate vote
```

`<n>` is the number of DISTINCT approaches. Default 5. Clamp to 2..8 (fewer than 2
is not a comparison; more than 8 blows past useful comparison and process budget).

`--tournament` opts into the adversarial selection escalation (see Phase 6): instead
of choosing from paper option cards, the conductor BUILDS a couple of real competing
prototype variants and routes them through `/personal-critic-gate` for a multi-aspect
panel vote. It costs more (real builds + a 5-seat panel), so it is opt-in. Without the
flag the conductor MAY propose it on a high-stakes choice but ASKS first.

## Roles block (the delegates this conductor folds in)

```
BRAINSTORM  = superpowers:brainstorming     # when the feature is underspecified
RESEARCHER  = deep-research / WebSearch      # prior art, common approaches, gotchas
PREVIEW     = /browse                        # render + screenshot the HTML artifact
                                             # (CLAUDE.md: NEVER the chrome MCP)
ITERATE     = inline bounded loop (2-4 passes)  # refine the artifact in-session
                                             # (cross-session runs: see Phase 5)
IMPLEMENTER = bunny (if present) / inline    # write the chosen option into the host repo
VERIFY      = verify / /browse               # prove the feature works, capture evidence
SHIP        = /ship or commit-commands:commit-push-pr   # PR with screenshot
```

These are model-context entities, not discovered from the host filesystem. If a
delegate is unavailable in the current session, fall back to the inline equivalent
and say so.

## Mode detection (UI vs non-UI)

The HTML artifact is built one of two ways. Detect from the feature text:

- **UI mode** -- the feature names a screen, page, component, layout, form, button,
  chart, dashboard, CSS, animation, or any visible surface. The HTML artifact IS a
  set of live, interactive mockups (the prototype itself).
- **NON-UI mode** -- backend, CLI, data pipeline, API, schema, algorithm, infra. The
  HTML artifact is a comparison DOCUMENT: a decision matrix of the approaches plus a
  recommendation. No live mockup -- the HTML exists so you can read and compare.

When the feature is genuinely ambiguous (could go either way), ask once which mode
fits. Do not guess silently. Mode-specific build guidance:
- UI mode -> read `references/ui-mode.md`
- NON-UI mode -> read `references/non-ui-mode.md`

## Per-run pipeline

### 1. PARSE
Extract `n` (default 5, clamp 2..8) and the feature text. If no feature was given,
ask for it before anything else.

### 2. UNDERSTAND + RESEARCH
- Feature underspecified or creative -> invoke BRAINSTORM until the intent is clear.
- Run RESEARCHER on the problem space: how do people usually build this, what are the
  common approaches, what are the known traps. A few targeted searches, not a thesis.
- Detect MODE (above). Announce the detected mode + basis.
- State a cost estimate (research + N-option generation is usually MEDIUM).

### 3. GENERATE N OPTIONS
Produce `n` genuinely DISTINCT approaches -- different in mechanism, not cosmetics.
Two options that collapse to the same idea is a bug: regenerate the duplicate. For
each option, fill the **option card**:

```
### Option <k>: <short name>
- **Summary**: one line -- what this approach is.
- **How it works**: 2-4 sentences -- the actual mechanism.
- **Pros**: bullet list -- where it wins.
- **Cons**: bullet list -- where it hurts.
- **Cost / effort**: rough build size (S / M / L) + one-line basis. Label it as an
  estimate (Honesty Protocol -- this is INFERRED, not measured).
- **Risk**: the thing most likely to bite later.
```

### 4. BUILD HTML ARTIFACT
Follow the mode's reference file. Write to
`docs/personal-prototype/<YYYY-MM-DD>-<feature-slug>.html` (create the dir if absent).
- UI mode: live mockups side-by-side or tabbed, each carrying its option card. Match
  the host design system if one exists (read its tokens/CSS first -- see ui-mode.md).
- NON-UI mode: a clean decision-matrix page (rows = options, columns = the card
  fields) + a recommendation block.
Self-contained HTML, ASCII source, no external network requests. In UI mode matching
an existing surface, apply the Core principle: build from the real markup/CSS/icons +
reference screenshots, base64-embed icons (never substitute text links or emoji).

Enforce self-containment mechanically -- run the bundled checker on the built file:
`python scripts/check_prototype.py docs/personal-prototype/<file>.html [--marker <key label> ...]`
It prints `CHECK-OK` or `CHECK-FAIL: <reasons>` (no external `http` resources, a
base64 `data:` URI present, no `position:fixed`, ASCII-only source, required markers).
Fix any `CHECK-FAIL` before previewing.

### 5. PREVIEW + ITERATE
Preview the artifact with PREVIEW (`/browse`). Then iterate: preview -> critique
against the feature's goal -> refine the HTML -> re-preview. A bounded inline loop, a
few passes (typically 2-4) until the comparison reads clearly and, in UI mode, the
mockups look real. Screenshot each pass so the progression is on record. Stop when a
pass produces no meaningful improvement. If the run must survive across sessions
or be phase-tracked, drive the whole skill under `/personal-workflow` (it records
phases via the `/personal-goal` beacon); `/loop` is a cadence scheduler, not a
bounded refine-N-times primitive.

### 6. RECOMMEND + CHOOSE
Present the comparison with an EXPLICIT recommendation: which option you would pick,
why, its pros/cons, and its cost relative to the others. Then ask the user to choose
(`AskUserQuestion`), default-selecting your recommended option. The user's pick wins
over your recommendation -- record which was chosen.

**Tournament escalation (opt-in -- `--tournament`, or propose-and-ask on a high-stakes
choice).** When the choice is consequential and paper option cards are not enough,
escalate to an adversarial multi-aspect vote:

1. Pick the 2-3 most distinct approaches and BUILD them as real competing variants
   (Phase 4 for each), writing them to
   `docs/personal-prototype/<YYYY-MM-DD>-<feature-slug>-variant-<A|B|C>.html`. Clamp to
   2..3 -- building real variants costs, so this is narrower than the up-to-8 paper
   approaches. State the cost before building.
2. Hand the variants to `/personal-critic-gate` using its **planning-time** mode, so
   the 5-seat panel votes on which variant wins. Pass an inline block of this shape:
   ```
   TYPE: planning-time-recommendation
   OPTIONS: [A: <variant-A name>, B: <variant-B name>, ...]
   RECOMMENDATION: <your pick label>
   RATIONALE: <one paragraph: why you lean that way>
   CONTEXT: <the feature goal; how the variants differ; AND the built variant FILE
            PATHS so each seat READS the real artifact, not this prose>
   ```
   The variant file paths in CONTEXT are load-bearing: the planning-time vote is on
   labels, so without the paths the panel grades your prose instead of the prototypes
   -- the same fidelity-from-artifacts trap, applied to the judge. The 5 seats supply
   the different aspects (ms-mario defects, amanda intent-vs-goal, rhea quality/cost,
   maggie design/UX, codex/iris fresh skeptic); majority of 3-of-5 picks the winner.
3. Surface the panel tally + your own pick + where they agree/disagree, then let the
   user confirm (critic-gate's interactive PAUSE plus this choose fence). The user's
   pick still overrides the panel. Record the chosen variant.

### 7. IMPLEMENT (fence: PAUSE before first write)
Implement the chosen option in the host repo. Read neighboring files first (Edit
Discipline: read -> grep callers -> edit) so the new code matches existing
conventions and style. Delegate heavy writes to IMPLEMENTER (bunny) when available.

### 8. VERIFY
Two SEPARATE gates -- passing one does not satisfy the other:
- **Behavior gate**: run the project's build/tests; use VERIFY (`/verify` or `/browse`)
  to confirm the feature actually works -- interactions fire, no console errors.
- **Visual gate** (UI mode, only when matching an existing surface): Read your captured
  screenshot AND the reference image in the same context and compare region by region
  (toolbar, panels, grids, form columns). "Behavior passed" does NOT mean it looks
  right. Fix and re-capture until they match closely.

Capture a screenshot of the working result. **Driver re-check**: whoever reports
completion to the user must personally Read the final evidence screenshots/output
first -- a subagent's "done" claim is not evidence (full-page captures have hidden
defects a summary misses). Honesty Protocol: quote the evidence -- never write "works"
/ "passing" without the command output. A red result honestly reported beats a green
one claimed without proof.

### 9. SHIP (fence: PAUSE before PR)
Branch properly if still on a shared/unrelated branch. Open a PR via SHIP with the
verification screenshot embedded in the body. Summarize: the N options considered, the
one chosen + why, and the evidence it works.

## Model selection -- spend the frontier model only where it pays off

This conductor dispatches work to subagents (research, build, implement, verify). Most
of that work is mechanical -- gathering, transcribing, following the plan, driving a
browser against pass/fail rules -- and runs fine on a mid-tier model. Match the Agent
tool's `model` option to the phase so a prototype comparison does not cost a fortune in
frontier-model tokens for work a cheaper tier does just as well.

| Dispatch | `model` | Why this tier |
|---|---|---|
| Research, Generate options, Build artifact, Build variants, Preview/iterate, Implement, Verify | `sonnet` | Faithful gathering / following the plan, not deep reasoning. Keep a vision-capable tier so builders can Read reference screenshots. |
| Visual-fidelity compare (UI, vs a reference) | `opus` | Region-by-region "does it look right" is the one genuine taste call. |
| Critic-gate panel (tournament) | seats carry their own models | Judgment is delegated to the panel; do not override its seat models. |
| Driver re-check | the driving session's model | One Read of the evidence -- cost is negligible. |

Rule of thumb: default every dispatch to `sonnet`; upgrade a SINGLE phase to `opus`
only when you can name the judgment that needs it (here, visual fidelity). If a
cheap-model phase produces a rejected result, re-dispatch THAT phase on `opus` -- do
not raise the floor for all of them.

## Fence (high-stakes pauses)

PAUSE and confirm before: the first IMPLEMENT write, and the SHIP PR. These mirror the
`personal-critic-gate` Stay-Paused list. Everything up to and including the HTML
preview is reversible and runs without a stop. Honor process-budget discipline: if a
phase fans out subagents, keep concurrency <= the CLAUDE.md ceiling and say the cost.

## Recovery

The HTML artifact under `docs/personal-prototype/` is the durable record of the
comparison; it survives `/clear`. Re-invoking on the same feature can resume from the
artifact (skip research + regeneration) and go straight to choose/implement.

## Red flags -- STOP, you are about to repeat a known failure

| Rationalization | Reality |
|---|---|
| "The description is detailed enough to build from" | When a reference surface exists, build from the real artifact + screenshots, not prose -- prose-built layouts get rejected. |
| "Behavior works, so it is done" | The visual gate is separate (UI mode matching a reference). Compare captures against the reference region by region. |
| "The subagent said done and committed" | The driver must personally Read the evidence screenshots/output before reporting done. |
| "Close enough, it is just a prototype" | Not pixel-perfect, but a user must recognize an existing surface instantly. |
| "Run every dispatch on the best model to be safe" | Research/build/preview/implement are mechanical -> `sonnet`. Reserve `opus` for the visual-fidelity compare. See Model selection. |
| "The tournament block can just describe the variants" | The panel votes on labels; without the variant FILE PATHS in CONTEXT it grades prose, not prototypes. |
| "More options is always better" | Distinct mechanisms, not cosmetic variants; clamp paper approaches to 2..8 and tournament builds to 2..3. |
