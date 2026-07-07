# NON-UI mode -- comparison-document artifact

In non-UI mode there is nothing to "mock up" visually -- the feature is backend, CLI,
data, API, schema, algorithm, or infra. The HTML artifact is a **decision document**:
a clear, scannable comparison of the N approaches so the choice is obvious on sight.

## What the document contains

1. **Header** -- the feature in one sentence + the question being decided.
2. **Context / research** -- 2-4 lines on how this is commonly built and the key
   constraint that splits the options apart (from phase 2 research).
3. **Decision matrix** -- the core. An HTML table:
   - one row per option,
   - columns: Option name | Summary | Pros | Cons | Cost (S/M/L) | Risk.
   - color the Cost cell (green S / amber M / red L) so effort reads at a glance.
4. **Per-option detail** -- below the matrix, each option's "how it works" in 2-4
   sentences, plus a short code sketch or pseudo-API if it helps (e.g. the shape of a
   function signature, a sample request/response, a schema fragment).
5. **Recommendation** -- which option, the one-paragraph why, and what would change
   the call (the condition under which a different option wins).

## Style

- One self-contained `.html` file, ASCII source, no external requests.
- This is a reading artifact -- optimize for fast scanning: a sticky/clear matrix,
  generous whitespace, monospace for code sketches. You may reuse the
  `personal-md-to-html` aesthetic by authoring the doc as Markdown with its dashboard
  blocks (`kpi`, `rules`, `callout`) and rendering it, or write plain clean HTML
  directly -- either is fine; pick the faster path.

## Distinctness

Options must differ in mechanism, not naming. Genuinely distinct examples: polling vs
webhook vs queue; a denormalized table vs a join vs a materialized view; sync request
vs background job vs streaming; a regex parser vs a grammar vs an LLM extractor.

## Iterating (phase 5)

Each pass: open in `/browse`, screenshot, ask "is the matrix honest and is the
recommendation actually defensible from the cells above it?" Tighten the weakest
column or sharpen a vague pro/con, re-preview. Stop when a pass adds nothing.
