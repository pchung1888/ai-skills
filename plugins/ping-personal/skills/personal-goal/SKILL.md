---
name: personal-goal
model: inherit
description: Initialize a long-running multi-phase goal with a crash-recovery beacon. Use when starting a goal that may span sessions or survive a crash. Triggers on /personal-goal <slug>.
---

# /personal-goal

## Invocation

`/personal-goal <slug> [--plan <path>] [--vision <path>] [--accept-cmd ...] [--accept-match | --accept-regex ...] [--unverifiable "<reason>"] [--area ...] [--branch ...]`

## The requirement comes first (REQUIRED)

Before anything else, capture the owner's ask **in their own words** and read it
back to them for confirmation before it is written. Never paraphrase it, never
tidy it up, never summarise it into a Purpose sentence -- a summary is the
session's reading of the ask, and later sessions will then plan against the
reading instead of the ask.

`beacon_writer.py` refuses to arm without it (exit 3). Pass one of:

- `--requirement "<their words>"` for a one-liner,
- `--requirement-file <path>` when the ask runs to several lines,
- `--no-requirement "<why there isn't one>"` for a genuine exploratory spike
  (12+ chars; it is recorded in the beacon and the critic gate reads it).

**Read it back before writing -- this is enforced.** The requirement lands in a
git-committed file. In some host repos `docs/` is tracked in git, so a real
ask -- which routinely quotes client names, account identifiers and ticket text --
would enter permanent company-repo history. `beacon_writer.py` exits 8 unless you pass
one of:

- `--text-reviewed "<who confirmed it, when>"` after showing the captured text to the
  owner, or
- `--text-unreviewed "<why no review was possible>"`.

Either way the answer is written to the beacon as `text_review_status` and committed,
so a later session and the critic gate can see whether anyone actually looked.

There is deliberately **no scanner**. A regex sees shape, and the thing at risk -- a
client name, a trader name, a sentence sensitive for what it describes -- has no
shape. A pattern list that cannot recognise a client name but claims to check for one
is worse than nothing, because it licenses skipping the read-back. This is an
acknowledgement, not a detection.

## Procedure

1. Load deferred tools: ToolSearch("select:Agent,TaskCreate,TaskUpdate,SendMessage").
2. Walk `${CLAUDE_PLUGIN_ROOT}/skills/personal-goal/preflight.md` -- confirm each of the 10 rules.
3. Resolve phase list:
   - If --plan: `python ${CLAUDE_PLUGIN_ROOT}/skills/personal-goal/lib/plan_parser.py <path>` and parse output.
   - Else: prompt interactively for phase count + names.
   - If --vision <path> is given, pass it to beacon_writer.py via --vision-path. If --plan is given but
     --vision is absent, ask the user: "Is there a vision or why-doc for this goal? (path or 'none')" --
     a vision doc helps the critic gate judge intent against the WHY, not only the plan's WHAT. If the
     user provides a path, pass it as --vision-path; if they answer 'none', omit the flag (leave vision_path blank).
3a. Determine operating mode (one question, ask once): interactive or
   autonomous, separately for Phase 1 and Phase 2+. Default if unanswered:
   phase_1_mode=interactive, phase_2plus_mode=autonomous (the common case).
   Record both in the beacon frontmatter via beacon_writer.py --phase-1-mode /
   --phase-2plus-mode (auto_mode_triggers = [T3]; T5 struck 2026-09-18).
4. Validate acceptance gate:
   - `python ${CLAUDE_PLUGIN_ROOT}/skills/personal-goal/lib/accept_gate.py --validate <args>`
   - On non-zero exit, surface the error and STOP.
5. Resolve area:
   - `python ${CLAUDE_PLUGIN_ROOT}/skills/personal-goal/lib/area_resolver.py --slug <s> [--area <a>]`
6. Write beacon:
   - `python ${CLAUDE_PLUGIN_ROOT}/skills/personal-goal/lib/beacon_writer.py <args> --requirement-file <path> --out docs/<area>/<slug>-audit-tracker.md`
   - The requirement flag is REQUIRED (see "The requirement comes first" above);
     the writer exits 3 without it.
6b. Triage the phase list with the owner -- THE ONE QUESTION (REQUIRED when the
   phase list came from a plan, a findings pass, a TODO ingest, or any earlier
   session rather than from the owner in this conversation).
   Every parsed phase is written as `PROPOSAL`, and `advance.py` refuses to mark a
   PROPOSAL phase done (exit 6), so the list cannot be executed until this happens.
   Print the requirement, then the phase titles, then ask exactly one question:

   > "Which of these neither serves the ask above nor unblocks it?"

   Do NOT offer a menu of implementations -- every option in such a menu ratifies
   the premise and makes the owner its author. "None of these -- there is a smaller
   way to do this" must be a reachable answer.
   Then set each surviving phase's Source cell to one of:
   `ASK:<quoted fragment>` | `DEC-<n>` | `UNBLOCK:DET-<n>`.
   Re-run this whenever the phase list GROWS later -- a backlog ingest, a detour, a
   retry re-scope. Drift enters when work is added mid-flight, not at arm time.
6a. Stamp starting quota: run
   `pwsh -NoProfile -File "${CLAUDE_PLUGIN_ROOT}/skills/personal-quota/quota.ps1" -Json` and append
   a "Quota at arm" line (session/weekly %, resets, and the band via
   `${CLAUDE_PLUGIN_ROOT}/skills/personal-quota/plan.ps1`) to the beacon, so a goal resumed in a
   later session knows its starting runway. If quota is UNKNOWN/stale, record that honestly rather
   than guessing a number.
7. Mutate .claude/TODO.md:
   - `python ${CLAUDE_PLUGIN_ROOT}/skills/personal-goal/lib/todo_mutator.py --add --slug <s> --beacon <p> --acceptance <a> --todo .claude/TODO.md`
8. `git add -f <beacon> && git add .claude/TODO.md && git commit` covering BOTH
   files in ONE commit. The `-f` is load-bearing: `git add` on a path under an
   ignore rule exits 1 even when it stages successfully, so a plain add leaves
   the beacon uncommitted. This is the only beacon commit that exists before the
   first phase, so losing it loses the whole goal.
9. Print handoff block; STOP.

## After /personal-goal returns

The driving Claude session reads the handoff and runs the per-phase loop.
REQUIRED SUB-SKILL: personal-fable-mode -- the driver runs the five-gate
discipline; a phase `done` advances only with Gate 4 evidence.
Each phase records the live quota reading (`personal-quota/quota.ps1 -Json`) alongside
`/personal-goal-next --tokens`, so the beacon's cost log shows real headroom over time, not only
token estimates.
- For each pending phase: dispatch one-shot Agent using `${CLAUDE_PLUGIN_ROOT}/skills/personal-goal/agent-dispatch-template.md` filled with the phase brief.
- On return: parse agent's structured payload (including `done_check` +
  `verification`), call `/personal-goal-next` per its SKILL.md. On a PASS
  outcome pass the payload's `verification` value as `--verify` (required);
  on FAIL/BLOCKED put the evidence in `--notes` instead.
- After last phase: run acceptance command, call `/personal-goal-next ... --finalize`.

### Forced-amnesia retry rule (REQUIRED)

On a phase FAIL:

- The retry MUST be a FRESH one-shot Agent dispatch. NEVER use SendMessage to continue the
  failed agent -- the failed agent's polluted context would carry over and repeat the same failure.
- The retry brief contains ONLY: the original phase brief + a distilled failure block (what failed,
  what was tried, what must not be repeated). Use the "## RETRY CONTEXT" section in
  agent-dispatch-template.md to hold this distilled block.
- Distill the failure block before dispatching: strip all verbose logs; keep only the 3-5
  sentences that describe the failure cause, the approaches tried, and the hard constraints
  the retry must respect.
- If `/personal-goal-next` advance.py exits with code 4 (RETRY CAP HIT or NO PROGRESS
  DETECTED), do NOT retry. STOP the goal and surface the BLOCKED status to the user for
  human intervention.
