---
name: personal-online-research
model: inherit
description: Web research with verification built in -- from a one-fact lookup to a multi-perspective, citation-verified research report, using the firecrawl CLI as the fetch layer. Trigger on /personal-online-research, "online research", "research this online", "web research", "research report on X", "deep dive on X online", "storm research", "storm report", "scrape and research". Use whenever the deliverable is researched knowledge FROM THE WEB with cited, verified claims. Do NOT trigger for local codebase research (use iris / understand-anything) or for a bare fetch of one known URL with no synthesis (use the firecrawl skill directly).
---

# /personal-online-research

Turn a question into verified, cited knowledge from the live web. Three depth
modes share one contract: every claim traces to a fetched source, every claim
carries an Honesty Protocol label, and nothing ships unverified without being
marked so.

REQUIRED SUB-SKILL: personal-fable-mode. Research is the gate loop applied to
the web: scope the question (Gate 1), fetch before reasoning (Gate 2), attack
the emerging answer with counter-evidence (Gate 3), verify citations against
primary sources (Gate 4), report calibrated with labels (Gate 5).

## Provenance

Fusion of two bases: the official firecrawl CLI skills (installed by
`firecrawl init`; fetch-layer conventions reused verbatim) and the community
"Storm Research" skill (the five-lens adversarial pipeline and mandatory
citation-verification phase), rebuilt on Ping's ecosystem: fable-mode gates,
Honesty Protocol labels, process/token budget discipline, and
personal-md-to-html for rendering.

## Fetch layer

- Primary: the firecrawl CLI. Confirm readiness with `firecrawl --status`
  before real work; on auth/install trouble see the firecrawl skill's
  `rules/install.md`.
- Degrade gracefully: if firecrawl is unavailable and cannot be installed,
  fall back to the built-in WebSearch/WebFetch tools and say so in the report
  (the verification contract does not change).
- firecrawl conventions (from the official skill, non-negotiable):
  - Always quote URLs (shell eats `?` and `&`).
  - Write outputs to `.firecrawl/` with `-o`; keep `.firecrawl/` gitignored.
  - `search --scrape` already returns page content -- never re-scrape those
    URLs; check `.firecrawl/` before fetching again.
  - Never read whole output files; use head/grep/incremental reads.
  - Escalate fetch method: search -> scrape -> map+scrape -> crawl; interact
    only for pages needing clicks/forms; monitor for recurring checks.
  - Respect `FIRECRAWL_NO_SEARCH_FEEDBACK` / `FIRECRAWL_NO_ENDPOINT_FEEDBACK`;
    otherwise send search feedback after use (first feedback refunds a credit).

## Mode routing

| Mode | Question shape | Fetch budget | Agents | Effort |
|---|---|---|---|---|
| lookup | one fact, one page, "what is X" | 1-3 fetches | none | low |
| brief | one topic, one perspective is enough | 3-10 queries, 5-25 sources | none (single context) | inherit |
| storm | contested/consequential topic; multiple viewpoints and fact-checked claims matter | per lens | ~10 (5 lenses + verifiers) | high at verify |

Pick the cheapest mode that answers the question (fable-mode effort dial).
Announce the mode and its cost in one line before starting. Storm mode spawns
parallel subagents: per the Process Budget rules in CLAUDE.md, CONFIRM with
Ping before the lens fan-out and again before the verifier fan-out, with agent
counts named. Never silently upgrade lookup -> storm.

## Mode: lookup

1. `firecrawl search "<query>" --scrape --limit 3` (or `scrape` if the URL is
   known).
2. Answer inline, citing the fetched source URL. Label the claim (EXTRACTED
   from the fetched page vs INFERRED across pages).
3. No file deliverable unless asked.

## Mode: brief

1. Gate 1: state the question, the reader, and 1-3 load-bearing unknowns.
2. Search 3-10 queries from different angles (definitions, implementation,
   market, criticism, primary docs); scrape the best 5-25 sources into
   `.firecrawl/`.
3. Synthesize -- do not list scrape summaries. Deliverable structure:
   Executive Summary; Key Findings (numbered, each with source URL + label);
   Contrarian Views and Risks; Open Questions (UNKNOWNs, each with the probe
   that would kill it); Sources (every URL, one-line note); Rerun Inputs
   (mode, topic, date).
4. Write to `docs/research/<YYYY-MM-DD>-<topic-slug>-research.md`.

## Mode: storm (five lenses + mandatory verification)

The Storm Research pipeline with firecrawl as the fetch layer.

1. **Scope** (Gate 1): one-line topic interpretation + reader's role; derive
   `<topic-slug>`; announce the pipeline and cost; CONFIRM the fan-out.
2. **Five lenses** (Gate 2/3): spawn five parallel general-purpose agents in
   one message -- Practitioner, Academic, Skeptic, Economist, Historian --
   each instructed to do real fetches (firecrawl or WebSearch), return CORE
   POSITION (2 sentences), STRONGEST EVIDENCE (3-5 bullets, each with a
   concrete figure/case + URL), and THE ONE THING only that lens would say,
   under 400 words. The Skeptic builds the steelman bear case -- that lens is
   the built-in Gate 3.
3. **Contradiction map** (inline, no agents): direct conflicts (name the
   clashing claims); strongest vs weakest evidence (peer-reviewed causal >
   official data > single survey > anecdote/analogy > preprint); the one
   resolving question; universal agreement (the load-bearing finding); the
   blind spot (missing 6th lens).
4. **Synthesize** the report: 60-second summary; 5 key findings ranked by
   reliability with confidence 1-10 and supported-by/challenged-by chips;
   hidden connection; missing 6th lens; actionable moves for the reader's
   role; claim safety guide (assert / caveat / avoid); frontier question;
   references with verification-status tags.
5. **Verify every citation** (Gate 4, DO NOT SKIP): CONFIRM the fan-out, then
   one agent per citation cluster (~4-6 agents), each verifying claims
   against the PRIMARY source: exact title/venue/year/URL, the real figure as
   published, peer-review status, strongest counter-source. Verdicts:
   CONFIRMED / PARTIALLY CONFIRMED / UNVERIFIED / FALSE.
6. **Apply corrections**: fix figures, demote thin evidence to a contested
   sidebar, cut or mark UNVERIFIED claims (never paper over -- a wrong claim
   is 3x worse than a blank), and fill the verification banner:
   `N/N checked, X false, Y corrected, Z demoted`. A storm report without the
   banner is not done.
7. Write to `docs/research/<YYYY-MM-DD>-<topic-slug>-storm.md`. Disclose in
   the report that the panel is author-built: convergence across lenses is a
   strong hypothesis, not field consensus.

## Rendering and downstream

- HTML wanted? Run /personal-md-to-html on the deliverable (arc theme) instead
  of maintaining a separate HTML template.
- Knowledge graph wanted? Feed the deliverable to /graphify.
- Facts that later decisions depend on? Promote them into a
  /personal-facts-check doc so they carry re-verifiable provenance.

## Codex runtime note

On Codex (skills shared via ~/.agents/skills junctions) there is no Claude
Agent tool: run storm lenses and verifiers SEQUENTIALLY in one context, keep
every other step identical. See runtime-compatibility.md at the plugin root.

## Anti-patterns

- Answering from training memory with a citation pasted on top (every cited
  claim must trace to a source fetched THIS session).
- Storm mode for a lookup-shaped question (cost without value).
- Skipping the verification phase to save time -- then it is a brief, label
  it as one.
- Re-scraping URLs that `search --scrape` already returned.
- Unquoted URLs in shell commands.
- Presenting lens convergence as independent consensus.
