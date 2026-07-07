# Agent Dispatch Brief Template

Fill in each `{{placeholder}}` before dispatching. The return-contract block at the bottom is REQUIRED verbatim -- do not trim it.

## Context

- Goal: {{slug}}
- Phase: {{phase_n}} of {{total_phases}}
- Beacon: {{beacon_path}}
- Soft budget: {{soft_budget_tokens}} tokens (surface to driver if exceeded; default 100K per preflight rule 8)
- Operating mode: {{phase_n_mode}} (interactive|autonomous -- from beacon frontmatter)
- Trigger set: {{auto_mode_triggers}} (default: [T3, T5]; T1 is deferred)

If operating mode is autonomous and you encounter any of the following, invoke
/personal-critic-gate BEFORE taking the next action:
- T3: you are about to return BLOCKED with 2 or more visible recovery paths.
  Pass a planning-time recommendation block listing the recovery paths as OPTIONS.
- T5: you are at a phase-boundary decision (prior phase delivered; proceed or abort?).
  Pass a summary of the prior phase output + acceptance evidence as the artifact.

Do NOT invoke /personal-critic-gate for every option set (T2 rejected -- cost runaway) or
for prior-critic-carryover checks (T4 rejected -- redundant with T5).

If operating mode is interactive: proceed normally; the driving session handles
/personal-critic-gate invocations when needed.

Stay-paused list (always halt for human, regardless of mode or vote tally):
- Any `git push --force` to `main`, `master`, or `feature/*`
- Any SQL `DROP TABLE` or schema-destructive DDL
- Any mutation of `.gitignore`, `.claude/settings.json`, `.claude/settings.local.json`
- Any mass rewrite of lockfiles (`package-lock.json`, `yarn.lock`, `Cargo.lock`, etc.)
- Any mutation of release/deploy directories (e.g. `Releases/`, `dist/`, `build/`)
- Any write to environment files (`.env*`)

The stay-paused list is the project-agnostic baseline. Extend it in your own
project's CLAUDE.md or in the calling /personal-critic-gate skill if your repo has
additional sensitive paths (e.g. infrastructure config, secrets vaults).

## RETRY CONTEXT (omit on first attempt)

If this brief is a retry after a prior phase FAIL, fill in this section with the distilled
failure facts. Remove this entire section on a first-attempt dispatch.

- What failed: {{retry_what_failed}}
- What was tried: {{retry_what_was_tried}}
- What must NOT be repeated: {{retry_must_not_repeat}}

---

## Phase work

{{phase_brief}}

## Return contract (STRICT -- per preflight rule 4)

At the end of your work, return a fenced YAML block containing:

```yaml
total_tokens: <integer reported by your runtime or -1 if unknown>
surprises: <free text -- list anything unexpected discovered>
blocked_vs_done: blocked|done
commit_sha: <sha of your last commit, or empty if you produced no commit>
```

## Useful patterns

- Tiny-finishing-edit (preflight rule 3): if your work ends with <=10 trivial lines remaining, return `blocked_vs_done: blocked` AND describe the tiny fix in `surprises`. The driving session may finish inline rather than re-dispatching a full agent.
- Cascading normalization (preflight rule 6): when ambiguous semantics share a syntax, try cheapest match first; escalate only on miss.
- Honesty protocol: label every factual claim as EXTRACTED, INFERRED, SUGGESTION, or UNKNOWN. Confident wrong answers are worse than admitted gaps.
