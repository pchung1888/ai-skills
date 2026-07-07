# Judge Rubric: personal-md-to-html (taste dimension)

> Use ONLY for what `eval.ps1` cannot measure. The code grader (via tests/smoke.py) already
> checks structure: self-contained output, golden render-diff, no external refs, validator
> negatives. This rubric judges whether a rendered spread is *actually* readable and on-theme.
> Reason-first scoring per the agent-evals-playbook (Step 8): observations BEFORE the score.

## When to run this judge

- After rendering a NEW Markdown doc (no golden exists yet) -- the code grader can only
  confirm it is structurally valid, not that it looks good.
- As a before/after check when changing the arc theme or a component (pairwise, below).
- As a calibration spot check on `examples/claire-arc.html` (a known-good render).

## What it judges (the failure mode code cannot reach)

- **F06** output is structurally valid but visually ugly, cluttered, or off-theme.

## How to run

Render the Markdown to HTML, open it (or pass the HTML source / a screenshot) as
`<artifact>`. For theme/component changes, prefer the pairwise form (old render vs new).

## Single-artifact Judge Prompt (reason-first)

```text
You are a strict visual-design evaluator of an arc-theme "magazine spread" HTML page.
Judge ONLY the supplied render. Do not reward a page for being valid HTML if it reads badly.

Task the render was trying to do:
Turn one Markdown doc into a single, self-contained, readable arc-theme spread (cream paper,
brick-orange accent, serif headlines, clear hierarchy, timeline rails, tasteful inline SVG).

Artifact (HTML source or screenshot):
<artifact>

Rubric (anchors):
- 0: unreadable -- overlapping text, broken layout, or nothing rendered.
- 1: renders but cluttered/inconsistent -- weak hierarchy, cramped spacing, off-theme colors.
- 3: clean and on-theme -- clear headline/body hierarchy, comfortable spacing, accent used
     with restraint, visuals support the content.
- 5: as 3, plus the layout genuinely aids reading (scannable, well-paced) and the SVG/sparkline
     touches add real signal, not decoration.

Rules:
- Do not reward missing content. If a section is empty or a visual failed to render, say so.
- Judge hierarchy, spacing, color restraint, and clutter -- not whether you like the topic.
- If you only have HTML source (no screenshot), flag any layout claim as inferred.
- List observations BEFORE choosing the score.

Return JSON:
{
  "positive_evidence": ["..."],
  "negative_evidence": ["..."],
  "missing_or_unclear": ["..."],
  "readable_hierarchy": true | false,
  "on_theme": true | false,
  "clutter_problems": ["..."],
  "score": 0,
  "verdict": "pass" | "fail" | "needs_review",
  "actionable_fix": "..."
}
```

## Pairwise Judge Prompt (theme/component change)

```text
Compare render A (before) and render B (after) of the SAME Markdown, for arc-theme quality.

Criteria, in priority order:
1. Readability / hierarchy
2. Spacing and density
3. Accent + color restraint (on-theme)
4. Visual signal vs decoration

First evaluate A, then B, then choose a winner.

Return JSON:
{ "a_strengths":[], "a_weaknesses":[], "b_strengths":[], "b_weaknesses":[],
  "winner":"A"|"B"|"tie", "confidence":"low"|"medium"|"high", "reason":"..." }
```

## Ship interpretation

- `verdict: fail` or `readable_hierarchy: false` -> the render regressed readability; fix before
  treating it as a good output, even though the code grader is green.
- `on_theme: false` -> the arc theme broke; check the theme/component change.
- Pairwise `winner: A` (the old render) after a "tidy-up" change -> the change made it worse; revert.
- A model-judge score is a signal, not truth -- spot-check a real render by eye before shipping a
  theme change (playbook Step 7 calibration).
