---
name: personal-critic-gate
model: sonnet
description: Adversarial-review gate (critic vote). Fires a 5-seat panel (ms-mario, amanda, rhea+coin, domain seat, codex/iris) before high-risk actions, 3-of-5 majority. Two operating modes -- interactive PAUSE (default) and autonomous AUTO-RESOLVE. Triggers on /personal-critic-gate [artifact-or-diff].
---

# /personal-critic-gate

Adversarial-review gate before shipping a plan, diff, or artifact. Wraps a
5-seat panel with a 3-of-5 majority resolver and a PAUSE-for-confirmation
contract so the driver does NOT auto-merge after findings come back.

Two operating modes:

- **interactive** (default): after the vote tally is printed, PAUSE for
  explicit user confirmation before any durable step.
- **autonomous**: after the vote tally is printed, auto-resolve per the
  majority-vote winner WITHOUT pausing -- EXCEPT when any stay-paused
  condition is detected (see Stay-Paused List below), which always halts
  for human regardless of mode.

Mode is determined at invocation time from the goal beacon (see Mode
Discovery below). Default is interactive when no beacon is found.

---

## When to use

Right before you would otherwise commit, push, or hand off a deliverable:

- "I am about to merge feature/X to main -- run /personal-critic-gate first"
- "/personal-critic-gate docs/plans/<slug>-plan.md"
- "/personal-critic-gate current diff" (review the staged changes)
- In autonomous mode (T3): a subagent returned BLOCKED with 2+ recovery
  paths -- vote on which path to take.
  (T5, a panel at every phase boundary, is STRUCK -- see Trigger Set.)

---

## Argument

`$ARGUMENTS` is one of:

- An artifact path (e.g. `docs/plans/<slug>-plan.md`, a code file, a skill
  SKILL.md). The agent reviews the file contents.
- The literal string `current diff`. The driver runs `git diff` and
  `git diff --staged` first and feeds the output into the review brief.
- Empty. The driver asks the user what artifact to review before
  dispatching.
- A planning-time recommendation block (see Planning-Time Artifacts below).

Flags:

- `--all`: force Seat 5 (codex/iris review-only) even on trivial
  artifacts that the matrix would normally skip (e.g. single-file typo fix).
- `--critic-only`: revert to single-reviewer behavior -- `ms-mario`
  only, no vote tally, no Seat 5 dispatch.
- `--quiet`: suppress the cost-estimate narration (use in autonomous mode
  where the cost envelope is pre-authorized).

---

## Planning-Time Artifacts

The gate also votes on a planning-time recommendation block (`TYPE:
planning-time-recommendation` with OPTIONS / RECOMMENDATION / RATIONALE /
CONTEXT). Seats vote an OPTIONS label or ABSTAIN; 3+ on one option wins, else
ms-mario's dissenting pick wins. Block shape and tie rule:
`references/planning-time.md`.

---

## Reviewer Matrix

| Artifact type | Seat 1 (ms-mario) | Seat 2 (amanda) | Seat 3 (rhea) | Seat 4 (domain) | Seat 5 (codex/iris) |
|---|---|---|---|---|---|
| Plan / spec (no code yet) | YES | YES | YES | maggie | YES |
| Code diff (any language) | YES | YES | YES | vex default | YES |
| New feature / architecture change | YES | YES | YES | maggie | YES |
| Release/migration script | YES | YES | YES | vex | YES |
| Data/parser/SQL artifact | YES | YES | YES | vex | YES |
| Design/architecture/UI artifact | YES | YES | YES | maggie | YES |
| Single-file typo or constant fix | YES (lightweight) | YES (lightweight) | YES (lightweight) | NO | NO (use `--all` to override) |
| Planning-time recommendation | YES | YES | YES | vex or maggie | YES |

ms-mario ALWAYS fires. Seat 5 (codex/iris) fires for any artifact with
enough substance to merit an out-of-house second opinion -- the only
exception is trivial single-file fixes.

### Seat 4 Domain Routing Table

Seat 4 selects the domain reviewer by artifact keyword matching:

| Keyword present in artifact text or path | Seat 4 reviewer |
|---|---|
| `.sql`, `.py`, `parser`, `csv`, `json schema`, `data contract`, `ingestion`, `migration script`, `ddl` | vex |
| `.tsx`, `.ts`, `.css`, `component`, `design`, `architecture`, `layout`, `chart`, `token`, `ui`, `ux` | maggie |
| `plan`, `spec`, `feature`, `phase`, `goal` (no code keywords above) | maggie |
| Ambiguous (no keywords match, or mixed) | vex (default) |

Document the routing decision in the tally block so the reviewer knows why
Seat 4 was assigned.

### Framing for Seat 5 (codex/iris) task description:

- Line-level diffs: "Perform a line-level code review. Focus on: unguarded
  type conversions, missing error handling, logic bugs, off-by-one errors.
  Do NOT fix; do NOT edit; review-only."
- Design artifacts (plans, specs, architectures, planning-time
  recommendations): "Challenge the implementation approach and design
  choices. Question whether the chosen approach is the right one, what
  assumptions it depends on, and where the design could fail under
  real-world conditions. Do NOT fix; do NOT edit; review-only."
- Release/migration scripts: combine both framings above.

---

## Voting Model (5 seats, majority 3-of-5)

The proposer no longer votes. The 5 seats review the proposer's artifact.

---

## Fast-lane mode (single-seat, for /personal-loop)

When invoked by `/personal-loop` as the per-tick gate, the panel runs in
FAST-LANE mode: a SINGLE seat (the resolved FAST_CRITIC) reviews the tick
output and votes one of `PASS | FIX | ESCALATE`. ESCALATE means "fire the
full 5-seat panel now." ESCALATE is valid ONLY in fast-lane mode -- the
5-seat tally stays PASS/FIX/BLOCK and raises ValueError on ESCALATE.
Parse a fast-lane vote with `lib/vote_parser.py --fast-lane`.

---

Each seat casts ONE VOTE returning a final JSON object:

```
{"VOTE": "PASS|FIX|BLOCK", "why": "one sentence"}
```

(For planning-time artifacts: `"VOTE"` value is one OPTIONS label or `"ABSTAIN"`.)

| Seat | Reviewer | Focus |
|---|---|---|
| 1 | ms-mario (chief critic) | defects, contradictions, missing acceptance criteria |
| 2 | amanda (intent-match) | does the artifact match the original plan / user intent; reads the plan/spec referenced by the beacon |
| 3 | rhea (quality + security + MASTER OF COIN) | tests, security boundaries, token cost vs value; recommends pause/defer when spend is not justified |
| 4 | domain seat (vex or maggie -- see routing table) | data/parser/SQL artifacts -> vex; design/architecture/UI -> maggie |
| 5 | codex via Agent tool (`subagent_type: "codex:codex-rescue"`) or iris when codex unavailable | fresh-context skeptic review; all existing Vote-3 dispatch text, read-only guard lines, and balanced-scan parse rule apply EXACTLY as documented |

Vote values (diff/plan artifacts):

- `PASS` = no blocking findings; ready to merge/ship. (Legacy alias: `SHIP`)
- `FIX` = CRITICAL or HIGH findings that must be addressed before ship.
- `BLOCK` = fundamentally wrong-shape; discard and re-plan. (Legacy alias: `ABORT`)

Automatic-FIX rule (all seats, both modes, including fast-lane): an artifact
that claims done/PASS without Gate 4 evidence at the layer of the claim (see
personal-fable-mode) gets a `FIX` vote -- unverified done is a HIGH finding by
definition. Evidence means the check that was run plus its quoted output, not
the claim that a check was run.

Canonical parse/tally implementations:
- `lib/vote_parser.py` -- quote-aware balanced-scan extraction of the LAST
  valid vote JSON from reviewer text. `python lib/vote_parser.py < textfile`
- `lib/tally.py` -- takes 5 seat votes (JSON lines or --votes args), outputs
  verdict PASS/FIX/BLOCK by majority 3-of-5. `python lib/tally.py --votes ...`

Tally format (print verbatim):

```
Seat 1 (ms-mario):         FIX  -- {"VOTE":"FIX","why":"..."}
Seat 2 (amanda):           PASS -- {"VOTE":"PASS","why":"..."}
Seat 3 (rhea+coin):        FIX  -- {"VOTE":"FIX","why":"..."}
Seat 4 (vex, data route):  PASS -- {"VOTE":"PASS","why":"..."}
Seat 5 (codex, RO):        FIX  -- {"VOTE":"FIX","why":"..."}
Verdict: FIX (3 of 5)
```

Decision: outcome with 3+ seats wins. If no outcome reaches 3 (no majority):
FIX (safe default). See `lib/tally.py` for full tie/insufficient handling.

---

## Preflight Codex Probe (before dispatching Seat 5 on a real artifact)

Before dispatching Seat 5 to `codex:codex-rescue` on a real artifact, fire a
trivial read-only dry-run Agent call (e.g. "List top-level directory structure;
read-only; no edits"). If this probe fails:

1. Announce immediately: "codex unavailable -- Seat 5 = iris (fresh-context
   skeptic)."
2. Proceed with the full panel. Dispatch iris as Seat 5.
3. Record "codex_available: false" in the tally block.

If the probe succeeds: dispatch codex as Seat 5 as documented below.

---

## How to Dispatch (step-by-step)

1. **Resolve the artifact.** Resolve `$ARGUMENTS` to concrete artifact text
   (file contents, diff output, or planning-time block). If unresolvable,
   STOP and ask the user.

2. **Detect stay-paused conditions (autonomous mode).** BEFORE dispatching
   any reviewers, check whether the proposed action involves any
   stay-paused path (see Stay-Paused List). If any match: write the status
   file, append to beacon Agent Activity Log, HALT for human -- do NOT
   proceed regardless of what the vote would be.

3. **Print the mode line and validate the phase** exactly as Mode Discovery
   steps 5-6 say (halt on a phase mismatch).

4. **Run preflight codex probe** (see Preflight Codex Probe above). Determine
   whether Seat 5 is codex or iris.

5. **State the cost estimate** (unless `--quiet` is set):
   "Firing 5-seat panel. Estimated MEDIUM bucket
   (~150-400K tokens). Proceed? [auto-yes in autonomous mode; PAUSE in
   interactive mode]"

6. **Determine the reviewer matrix.** Look up the artifact type. If
   `--critic-only` is set, only run ms-mario (skip steps 7-10).
   Determine Seat 4 reviewer from the domain routing table.

7. **Dispatch Seat 1 (ms-mario)** via the Agent tool with
   `subagent_type: "ms-mario"`. Brief:
   - The artifact text (path + contents OR the diff).
   - "Adversarial review before ship -- find what is wrong, do not praise.
     Apply the Honesty Protocol (EXTRACTED / INFERRED / UNKNOWN labels
     with one-sentence basis)."
   - "Apply Code-Reading Pre-Flight: before producing ANY finding about
     code claims, open and read the cited code files."
   - "Output a markdown findings list (CRITICAL / HIGH / MEDIUM / LOW /
     Could Not Assess)."
   - "At the end of your findings, add a final JSON object on its own line:
     `{\"VOTE\": \"PASS\"|\"FIX\"|\"BLOCK\", \"why\": \"one sentence\"}`.
     Apply Code-Reading Pre-Flight BEFORE drafting your vote."

8. **Dispatch Seat 2 (amanda)** via the Agent tool with
   `subagent_type: "amanda"`. Brief:
   - The artifact text.
   - "Intent-match review. Your ground truth is the OWNER'S REQUIREMENT, not the plan.
     Read the beacon's `## Requirement` section and judge the artifact against those
     words. The plan is a derived document and may itself be the thing that drifted --
     measuring the work against it would find a drifted plan faithfully implemented."
   - Requirement conditional (REQUIRED -- do not skip):
     - If the beacon has a `## Requirement` section and `requirement_status: provided`:
       judge every phase and deliverable against a quoted line of it. **A phase the
       requirement does not ask for is a BLOCK finding, not a FIX** -- FIX implies the
       work should be repaired, and unrequested work should be deleted, not repaired.
     - If `requirement_status:` starts with `none --`: the goal was armed without an
       ask, for the recorded reason. Judge against plan + Purpose as before, and say
       "no verbatim requirement" in your vote's `why` so the tally records the absence.
       Downgrade any scope judgement to "Could Not Assess" rather than guessing.
   - "Check the `## Detours` table. A detour whose `Origin` is `phase-<n>` means an
     earlier phase of this same goal created the blocker. That is drift, not a detour:
     the remedy is reverting that phase's mechanism, not building on top of it."
   - Vision-path conditional (REQUIRED -- do not skip):
     - If the discovered beacon has a non-empty `vision_path:` frontmatter field:
       amanda MUST read that vision doc and judge intent against the WHY (the goal's
       deeper purpose and motivation), not only the plan's WHAT. Include in the brief:
       "The beacon declares a vision doc at <vision_path>. Read it and evaluate whether
       this artifact serves the WHY described there, not just the plan tasks."
     - If `vision_path:` is absent or blank:
       amanda judges against plan + Purpose section as normal. She MUST note "no vision doc"
       in her vote's `why` field so the tally records the absence.
   - "Find intent drift, scope creep, or missing deliverables."
   - "At the end, add a final JSON object: `{\"VOTE\": \"PASS\"|\"FIX\"|\"BLOCK\",
     \"why\": \"one sentence\"}`."

9. **Dispatch Seat 3 (rhea)** via the Agent tool with
   `subagent_type: "rhea"`. Brief:
   - The artifact text.
   - "Quality + security + MASTER OF COIN review. Check: test coverage,
     security boundaries, token cost vs value for this artifact's scope."
   - "As MASTER OF COIN: if the spend implied by this artifact is not
     justified by the value delivered, recommend pause or defer."
   - "At the end, add a final JSON object: `{\"VOTE\": \"PASS\"|\"FIX\"|\"BLOCK\",
     \"why\": \"one sentence\"}`."

10. **Dispatch Seat 4 (domain reviewer)** via the Agent tool with
    `subagent_type: "vex"` or `subagent_type: "maggie"` (per routing table).
    Brief: standard domain review. At the end, add a final JSON object:
    `{"VOTE": "PASS"|"FIX"|"BLOCK", "why": "one sentence"}`.

11. **Dispatch Seat 5 (codex or iris)** -- if the matrix says YES for this
    artifact and `--critic-only` is NOT set.

    **If codex available:**
    Invoke the Agent tool with `subagent_type: "codex:codex-rescue"`.
    Do NOT invoke Seat 5 via the Skill tool and do NOT type the
    `/codex:rescue` slash command: both re-enter the command and HANG the
    session. The Agent-tool path is the only programmatic route.

    The subagent's prompt MUST begin with the literal token `--fresh` so
    the forwarder skips its "resume prior Codex thread?" AskUserQuestion
    (that prompt stalls an autonomous run). The prompt body:

    ```
    --fresh [Framing per matrix above]

    Artifact:
    <artifact text here>

    Return your findings in prose. The FINAL LINE of your output MUST be a
    single JSON object on its own line in exactly this form (no trailing
    whitespace, no line break inside the JSON):
    {"VOTE": "PASS"|"FIX"|"BLOCK", "why": "<one sentence>"}
    (for planning-time artifacts, use the OPTIONS label or "ABSTAIN" instead
    of PASS/FIX/BLOCK)
    Do NOT fix. Do NOT edit any files. Review-only.
    ```

    **Cross-vendor text strip (REQUIRED, no escape hatch).** Seat 5 runs on a
    different vendor, so the owner's words must not leave the boundary. Before
    emitting the prompt, remove any `## Requirement` section (substitute
    `[requirement withheld from cross-vendor seat]`) and replace any
    `ASK:<fragment>` Source cell with `ASK:[withheld]`. amanda (Seat 2) owns
    requirement-matching, so Seat 5 loses nothing it needs.

    **Read-only guard.** The forwarder defaults to a write-capable run and stays
    read-only only because the brief reads as review-only, so the "Do NOT fix.
    Do NOT edit any files. Review-only." line MUST stay verbatim.

    **If codex unavailable (probe failed):**
    Invoke the Agent tool with `subagent_type: "iris"`. Brief:
    - The artifact text.
    - "Fresh-context skeptic review. You are Seat 5 of a 5-seat critic panel.
      Approach this artifact with fresh eyes -- no prior context. Find
      assumptions the other reviewers may have taken for granted."
    - "Do NOT fix. Do NOT edit any files. Review-only."
    - "At the end, add a final JSON object: `{\"VOTE\": \"PASS\"|\"FIX\"|\"BLOCK\",
      \"why\": \"one sentence\"}`."

    Seat 5 vote parsing -- `lib/vote_parser.py` is the canonical implementation:
    - Do NOT use "last non-empty line": the Agent harness appends an
      `agentId: ...` footer after the JSON.
    - Extract with a quote-aware balanced `{...}` scan and take the LAST span
      that parses with a top-level `"VOTE"` key. A flat regex is NOT sufficient.
    - The `VOTE` value MUST be one of `PASS` / `FIX` / `BLOCK` (aliases `SHIP`,
      `ABORT`), or an OPTIONS label / `ABSTAIN` for planning-time artifacts.
      Anything else is a parse failure, never coerced.
    - On failure retry once; on a second failure Seat 5 = ABSTAIN and 3-of-4
      applies.
    Full rules, evidence and residual risk: `references/seat5-dispatch.md`.

12. **Wait for all seat reviewers** (seats 1-5, if dispatched). Collect all
    results before computing the tally.

13. **Compute and print the tally** per the format above. Use `lib/tally.py`
    as the reference implementation. Record Seat 4 routing decision.

14. **Mode-dependent resolution:**

    **Interactive mode (default):**
    - PAUSE for explicit user confirmation. The winning vote is a
      RECOMMENDATION, not an auto-decision. The driver must say one of:
      - "ship anyway" -- proceed with the original action.
      - "fix C-1 first" (or similar) -- loop back to implementation.
      - "abort" -- discard the planned action.
    - Only after the user responds may the driver take the next durable
      step.

    **Autonomous mode (AUTO-RESOLVE):**
    - Auto-resolve per the majority vote winner WITHOUT pausing.
    - 3-of-5 majority auto-resolves. Any Stay-Paused-List hit still
      hard-pauses regardless of votes.
    - If the winner is PASS: proceed to the next action.
    - If the winner is FIX: pause the goal, write a status file under
      `.claude/tmp/` describing the findings + proposed fix path, append
      to the beacon Agent Activity Log. Halt for human.
    - If the winner is BLOCK: same as FIX -- halt for human with status
      file.
    - Append the vote tally to the beacon Agent Activity Log in all cases.

---

## Mode Discovery

At invocation time, determine operating mode from the goal beacon:

1. Find the beacon: locate the most recently modified
   `*-audit-tracker.md` file in the current working tree under `docs/`.
   (Suggestion: if a `GOAL_SLUG` env var is set, use it to find the
   matching tracker directly instead of mtime.)

2. Determine the current phase number from the beacon's "Last Known Good
   Checkpoint" section (the "Last completed phase" field). Current phase =
   last-completed + 1.

3. Look up the phase-mode YAML field in the beacon frontmatter:
   - Current phase = 1: use `phase_1_mode`.
   - Current phase >= 2: use `phase_2plus_mode`.
   - If the field is absent: default to `interactive`.

4. If no beacon is found at all: default to `interactive` mode.

5. Always print one of:
   - `"Mode: <mode> (from beacon <slug>)"`
   - `"Mode: interactive (default; no beacon found)"`

6. Validate the inferred phase number against the Phase Status table in
   the beacon. If the computed "current phase" does not match an entry in
   the Phase Status table that is in Pending or In Progress state, print:
   `"WARN: phase mismatch -- beacon says phase N but Phase Status shows
   <actual state>; refusing to auto-resolve until mismatch is resolved."`
   and HALT.

The `--critic-only` and `--all` flags override the matrix but do NOT
override the mode.

---

## Stay-Paused List (MINIMUM; not exhaustive)

In autonomous mode, the gate ALWAYS halts for human (regardless of vote
tally) when the proposed action involves ANY of:

- Any `git push --force` to `main`, `master`, or `feature/*`.
- Any SQL `DROP TABLE` or other schema-destructive DDL.
- Any mutation of `.gitignore`, `.claude/settings.json`,
  `.claude/settings.local.json`.
- Any write to environment files (`.env*`).
- Any mass rewrite of lockfiles (`package-lock.json`, `yarn.lock`,
  `Cargo.lock`, `pnpm-lock.yaml`, etc.).
- Any mutation of release/deploy directories (e.g. `Releases/`, `dist/`,
  `build/`, `out/`).

This is the project-agnostic baseline. Extend it in your own project's
CLAUDE.md or in a fork of this skill if your repo has additional
irreversible-mutation categories (infrastructure config, secrets vaults,
production DB seeds, etc.).

Stay-paused detection: scan the proposed artifact text and the proposed
next action for these path strings and command patterns. This is a
heuristic scan (INFERRED: pattern-matching on path strings; not a
filesystem intercept). If any match is found, halt immediately.

When a stay-paused condition fires:

1. Write a status file under `.claude/tmp/` with a name of the form
   `critic-gate-paused-<TIMESTAMP>.md` describing: the detected condition,
   the proposed mutation, the vote tally (even if vote hasn't completed
   yet -- note "vote not computed").
2. Halt the goal awaiting human input.
3. Append the detection note + vote tally to the goal beacon's Agent
   Activity Log.

This list is the safety-net floor and MUST NOT be shrunk without explicit
user approval. It MAY be extended as new irreversible-mutation categories
surface.

---

## Trigger Set (T3 only; T5 STRUCK, T1 DEFERRED)

In autonomous mode, the gate self-fires at:

- **T3 -- BLOCKED-Recovery.** When a subagent returns `BLOCKED` with 2 or
  more visible recovery paths, fire `/personal-critic-gate` to vote on which
  path to take. The artifact is a planning-time recommendation block listing
  the recovery paths as OPTIONS.

- **T5 (phase boundary) STRUCK**, **T1 (AskQuestion swap) DEFERRED**. Do not add
  T2 (every option-set: cost runaway) or T4 (prior-critic carryover: redundant,
  phase scope is enforced in code by `advance.py` / `finalize.py`). Reasons and
  costings: `references/history.md`.

---

## Optional dependency -- the Codex plugin

Seat 5 routes through the `codex:codex-rescue` subagent (the worker behind
the `/codex:rescue` command). This requires OpenAI's `codex` plugin to be
installed and enabled, and the `codex` CLI to be on PATH and authenticated.
Without it, the Preflight Codex Probe swaps in iris, so the panel always
keeps 5 votes.

`codex:codex-rescue` is the only Codex review path Claude can invoke (the
`/codex:review` commands disable model invocation); why, and when to revisit:
`references/history.md`.

---

## Trigger phrases

"critic gate this", "gate this before ship", "adversarial review then
pause", "/personal-critic-gate [artifact]", "vote on this before we
proceed", "run a critic vote on this", "5-seat review", "panel review".

---

## Do NOT use for

- Mid-design brainstorming critique. Dispatch `ms-mario` directly
  via the Agent tool -- no pause, no Seat 5, no vote tally.
- Implementing the fixes the critics find. The gate identifies; the
  fixer fixes. Dispatch a separate `/codex:rescue` (in fix mode, not
  review-only) or a follow-up implementation agent after the gate
  returns and the user authorizes the fix.
- Researching existing code as the primary task.
