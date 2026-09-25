---
name: personal-workflow
model: inherit
description: Autopilot conductor over the personal-goal beacon. Hand it one goal, plan, or TODO-list; it discovers the host project's skills+agents, routes each phase to the best one, fans out via /workflows when safe, pauses at the hard-rule fence, verifies high-stakes claims, and records real token costs. Triggers on /personal-workflow <goal | --plan path | --list>.
---

# /personal-workflow

A thin **conductor**. It is the *driving session* `personal-goal` always required (see
`personal-goal` SKILL "After /personal-goal returns") -- it does NOT modify `personal-goal`; it
drives it with a richer loop. Ports DART's `/dart-workflow` (see
`docs/personal-workflow/2026-05-29-personal-workflow-port-design.md`).

## Roles block (the main LOGIC port-time edit)
```
BEACON      = personal-goal               # the durable git-committed beacon (plugin skill)
BRAINSTORM  = superpowers:brainstorming   # shared superpowers skill (model context, not on disk)
RESEARCHER  = iris                         # ping-personal read-work agent (subagent_type=iris)
IMPLEMENTER = bunny                        # ping-personal write-work agent (subagent_type=bunny)
CRITIC      = ms-mario / personal-critic-gate   # adversarial review + 3-vote ship gate
```
These delegates are **plugin-context entities the model folds in** (the `ping-personal:*` skills
and agents, `superpowers:*`) -- they are NOT discovered by `discover.py` (which reads only the
host project filesystem). See "Discovery" below.

**Honest port checklist:** re-pointing the roles above is the only *logic* edit. A port to another
repo ALSO re-points host-specific *path constants* -- the `tests/smoke.ps1` `$RepoRoot` depth and the
`personal-goal` lib path used by the beacon-reuse test -- per the design doc FIX-1/FIX-2. No conductor
logic changes; `discover.py` / `fence.py` are project-agnostic and read the host's own registry/rules.

## Invocation
`/personal-workflow <bare goal>` | `/personal-workflow --plan <path>` | `/personal-workflow --list [.claude/TODO.md]`
(plus personal-goal pass-through: `--accept-cmd / --accept-match / --accept-regex / --unverifiable / --area / --branch`)

## Startup (every run)
1. **Discovery = two-source merge.** A subprocess cannot read the model's skill registry, so:
   - `python <skill-dir>/lib/discover.py` -> the PROJECT half (the HOST project's filesystem
     `.claude/skills/*/SKILL.md` + `.claude/agents/*.md`) as JSON. Run it under
     `PYTHONIOENCODING=utf-8` on Windows hosts (cp1252 console guard).
   - The **model folds in** the plugin/built-in skills+agents it already has in context
     (`ping-personal:*` incl. the BEACON/RESEARCHER/IMPLEMENTER/CRITIC roles above, `superpowers:*`,
     `gstack`, `deep-research`, `verify`, ...) -- `discover.py` never sees these.
   - Merge both into the capability map. (In a plugin-dev repo with no `.claude/skills`, the
     project half is empty and the map is entirely model-folded -- expected, not a bug.)
2. **Load the fence.** `python <skill-dir>/lib/fence.py --action "<proposed action>"` classifies any
   action: exit 0 ALLOW / 2 PAUSE-ALWAYS / 3 PAUSE-ACK-ONCE. Contextual hard rules (no-PII-in-commit,
   host branch policy) are applied by judgment. The fence's baseline mirrors `personal-critic-gate`'s
   Stay-Paused List, so the conductor and the gate agree.
3. **Operating mode** (reuse personal-goal): Phase 1 interactive, Phase 2+ autonomous by default.

## Brainstorm gate
- Goal underspecified/creative -> invoke the BRAINSTORM role; ask until understood.
- Concrete plan/list -> **do not skip to phasing.** A document that merely *looks*
  like a plan is not a warrant: a findings inventory, a previous session's phase
  table, and a review output all look exactly like a plan. That shape-equals-
  authority assumption is how a past ticket turned research output into six phases without
  the owner ever seeing them.
  Run THE ONE QUESTION instead (personal-goal SKILL.md step 6b): print the
  requirement, print the phase titles, ask "which of these neither serves the ask
  nor unblocks it?", delete what the owner names, then phase.
  The ONLY skip is a phase list the owner approved **in this conversation** -- the
  test is owner participation, never who typed it. A plan the conductor authored
  itself is the highest-risk case, not an exempt one.
  Re-run this whenever the phase list GROWS: a `--list` backlog ingest, a detour, a
  FAIL/retry re-scope. A check that fires only at arm time never sees the drift,
  because drift arrives mid-flight.

## Spine (personal-goal, UNCHANGED)
Invoke `/personal-goal` (the slash command -- NOT a hardcoded lib path; that keeps the conductor
version-independent) to write the beacon + TODO + initial commit. For `--list`, dedupe by normalized
item text: skip any item already a beacon phase or under `## In Progress` / `## To Be Tested` in
`.claude/TODO.md` (items under `## Backlog` stay eligible).

## Per-phase conductor loop
For each pending phase:
1. **ROUTE** -- match phase intent to the capability map (see `references/routing.md`); announce the
   pick + basis; ask the operator on a high-stakes tie or a `confidence=low` lead candidate.
2. **MODE** -- apply the FANOUT 3-rule (`references/fanout-and-verification.md`). Eligible AND
   `/workflows` available -> `parallel([...units])`; else sequential one-shot Agent. Codex /
   no-workflows -> always sequential. Cap fan-out <= 8 concurrent (process-budget discipline);
   fan-out units MUST be idempotent.
   **Every unit brief is built from `personal-goal/agent-dispatch-template.md`**, the same
   template the sequential path uses, with the per-unit slice in `{{phase_brief}}` and one
   extra line naming what is out of scope for THAT unit. Until this was written down the
   parallel path referenced the template nowhere, so N agents ran with strictly less context
   than the single agent doing the same work -- the dispatch mode with the highest multiplier
   was the one mode that shipped a brief with no requirement attached. Cost: the quoted ask plus the fixed
   prose this adds to every brief is ~250-400 tokens per unit, so ~2-3K per 8-unit
   phase against a measured 230-789K phase -- under 0.5%. (An earlier version of this
   line said ~400 tokens per PHASE by counting only the quoted ask and ignoring the
   prose around it; a cost line in a governance doc should not be off by 8x.)
   A unit that cannot trace its task to the requirement returns BLOCKED; it does not widen.
   **Quota-scale before fanning out:** read the real band with
   `pwsh -NoProfile -File "${CLAUDE_PLUGIN_ROOT}/skills/personal-quota/plan.ps1" -Tasks "fanout:heavy" -Json`
   (a fan-out is heavy) and size the dispatch to it: PROCEED -> full fan-out (<= 8); CONSERVE ->
   halve concurrency + prefer the mid model tier; LIGHT_ONLY -> sequential + haiku workers;
   STOP -> do NOT fan out -- invoke `personal-handoff` and hand off. This real-quota band
   OVERRIDES the static `token_budget_total` whenever it is the tighter limit.
3. **FENCE** -- run the proposed action through `fence.py`. Exit 2 -> PAUSE, ask, wait. Exit 3 ->
   ask once per run, then allow. Exit 0 -> proceed. Also apply the contextual rules by judgment.
4. **VERIFY** -- before recording any "PASS / genuine-defect / works" claim, re-check it against the
   evidence its claim-type requires (`references/fanout-and-verification.md` evidence map). Downgrade
   to "unverified" if it does not hold; never write an unverified claim as fact. For high-stakes
   ship/merge decisions, route through the CRITIC role (`/personal-critic-gate`).
5. **RECORD** -- invoke `/personal-goal-next <slug> --phase N --outcome PASS --tokens <T>
   --commit <SHA> --subagent <A> --verify "<Gate 4 evidence: check run + one quoted
   output line>"` (the slash command). `--verify` is REQUIRED on PASS (advance.py
   refuses an unverified done, exit 2); reuse the evidence from step 4's VERIFY. For a fan-out phase, `<T>` = the `/workflows`
   completion `<usage>.subagent_tokens` (aggregate; record agent count + run-id too, and say it is
   aggregate). For inline driver work, record an honest inline estimate labelled as such. The DRIVER
   commits + timestamps (the workflow script cannot run git / Date.now()).

After the last phase: run the acceptance command -> `/personal-goal-next ... --finalize`.

## Recovery & interrupt
The beacon (git-committed by `/personal-goal-next` per phase) is the only cross-session safety net;
`/workflows` runId journals die on `/clear`. The loop is interruptible at any phase boundary --
re-invoke on the slug to resume from the last committed phase.

**On resume, before re-entering the loop, read in this order:**

1. the beacon's `## Requirement` section -- the owner's words, first, before any plan;
2. `## Decisions` -- what is already settled, so you do not reopen it;
3. `## Detours` -- any row still `open`. An open detour means the goal is parked on a
   side quest; resume at the phase its `Blocks` column names, not at whatever was most
   recently in motion. That is the difference between coming back to the goal and
   letting the detour become the project.

Then re-run the justification check over every remaining pending phase rather than
trusting a verdict a previous session recorded. A phase row is evidence of what a
session decided, not evidence that the owner agreed. A fresh session inherits the
previous session's conclusions with all their supporting evidence and none of their
doubts -- maximum confidence, minimum context -- and re-deriving is the only cure.

## Budget inheritance

When fanning out via the Workflow tool, read `token_budget_total` and the Cost
Log token sum from the beacon (both are available after the beacon is written by
`/personal-goal`).  Compute:

```
remaining = token_budget_total - cost_log_sum
```

Pass `remaining` as the budget cap to the fan-out so subagent fleets inherit
the ceiling.  If `token_budget_total` is 0 or the field is absent, apply no
constraint -- the fan-out runs without a budget cap.

This ensures that a goal-level token budget set via `beacon_writer.py
--token-budget N` is respected end-to-end: the conductor enforces it at the
Workflow dispatch boundary, and `advance.py` enforces it at the
`/personal-goal-next` record boundary (exit 5 on overage; pass
`--override-budget` to proceed with a logged note).

`token_budget_total` is a STATIC per-goal cap you set at arm time; the REAL-quota band from
`personal-quota/plan.ps1` (see MODE) is the LIVE gate and wins whenever it is tighter. Read both
and apply the smaller headroom -- a fresh static budget does not license a fan-out when the live
5h/weekly window is nearly exhausted.

## Effort routing

Reasoning effort is a per-dispatch knob, separate from the model tier: the
Workflow tool's `agent()` accepts `opts.effort` ('low' | 'medium' | 'high' |
'xhigh' | 'max'), while SKILL.md frontmatter only sets `model:`. Route effort
the way personal-fable-mode's effort dial prescribes -- deep reasoning at plan /
attack / verify, mechanical effort for mechanical steps:

| Phase type | effort |
|---|---|
| Mechanical fan-out (scan, list, rename, format, port) | `low` |
| Implementation / research phases | `low` |
| Verify / judge / adversarial-critic seats | `low` (default); `medium` only when the operator asks for a deeper pass on a named stage |

**Default is `low` for EVERY Workflow agent, including ultracode runs** (owner
decision 2026-09-09). Measured on a past ticket: a 5-agent review/verify fan-out at
`effort: 'high'` on the session model cost 789K subagent tokens and pushed the 5h
quota from 31% to 80% in one phase; the 2-agent pass before it cost 230K. Effort
multiplies quota burn per agent, so pass `effort: 'low'` explicitly in every
`agent()` call (do not omit it -- omitted means "inherit the session effort",
which on a Fable session is high). Never dispatch `high`, `xhigh` or `max`
unless the operator names the stage and accepts the cost in the same turn.
State the planned effort tier and agent count in the cost line before launching.
The plain Agent tool has no effort parameter, so for Agent-tool dispatches the
only routing knob is `model`; effort routing applies to Workflow dispatches.

See spec: `docs/personal-workflow/2026-05-29-personal-workflow-port-design.md`.

## --babysit mode

Invocation: `/personal-workflow --babysit`

A **report-only** sweep of every GOAL entry under `## To Be Tested` in
`.claude/TODO.md`.  It never writes to TODO.md, beacon files, or any other
file -- it only prints a markdown table to stdout.

### What it does

1. Parses `## To Be Tested` for lines matching
   `- **[GOAL <date> <slug>]**`.
2. Locates each beacon via the `Beacon:` fragment on that line (falling
   back to a glob of `docs/` for `*<slug>*audit-tracker.md`).
3. Reads beacon frontmatter (`accept_cmd`, `accept_shell`, `accept_match`,
   `accept_regex`, `accept_status`, `branch`).
4. Reports staleness: beacon file mtime older than `--max-age-days` (default
   14) -> `STALE`.
5. Reports unpushed branches: if the beacon's `branch` field exists locally
   but has commits ahead of its upstream (or has no upstream), flags
   `UNPUSHED` or `no-upstream`.
6. Reports gate: without `--run-acceptance` the gate column shows `not run`;
   with `--run-acceptance` it executes `accept_cmd` and reports
   `PASS` / `FAIL` / `UNVERIFIABLE`.

### Output columns

| column | meaning |
|---|---|
| slug | goal slug from the TODO line |
| beacon | beacon filename (NOT FOUND if missing) |
| gate | `not run` / `PASS` / `FAIL` / `UNVERIFIABLE` |
| staleness | `fresh` / `STALE` / `n/a` |
| branch state | `ok` / `UNPUSHED` / `no-upstream` / `branch-missing` / `n/a` |

### Under the hood

The conductor calls `python <skill-dir>/lib/babysit.py --todo .claude/TODO.md
--docs-root docs/ [--run-acceptance]`.  The operator decides what to promote
or close based on the report -- the tool never mutates state.
