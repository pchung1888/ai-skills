---
name: personal-goal
model: opus
description: Initialize a long-running multi-phase goal with a crash-recovery beacon. Use when starting a goal that may span sessions or survive a crash. Triggers on /personal-goal <slug>.
---

# /personal-goal

## Invocation

`/personal-goal <slug> [--plan <path>] [--vision <path>] [--accept-cmd ...] [--accept-match | --accept-regex ...] [--unverifiable "<reason>"] [--area ...] [--branch ...]`

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
   --phase-2plus-mode (auto_mode_triggers = [T3, T5]).
4. Validate acceptance gate:
   - `python ${CLAUDE_PLUGIN_ROOT}/skills/personal-goal/lib/accept_gate.py --validate <args>`
   - On non-zero exit, surface the error and STOP.
5. Resolve area:
   - `python ${CLAUDE_PLUGIN_ROOT}/skills/personal-goal/lib/area_resolver.py --slug <s> [--area <a>]`
6. Write beacon:
   - `python ${CLAUDE_PLUGIN_ROOT}/skills/personal-goal/lib/beacon_writer.py <args> --out docs/<area>/<slug>-audit-tracker.md`
7. Mutate .claude/TODO.md:
   - `python ${CLAUDE_PLUGIN_ROOT}/skills/personal-goal/lib/todo_mutator.py --add --slug <s> --beacon <p> --acceptance <a> --todo .claude/TODO.md`
8. git add + git commit covering BOTH files in ONE commit.
9. Print handoff block; STOP.

## After /personal-goal returns

The driving Claude session reads the handoff and runs the per-phase loop:
- For each pending phase: dispatch one-shot Agent using `${CLAUDE_PLUGIN_ROOT}/skills/personal-goal/agent-dispatch-template.md` filled with the phase brief.
- On return: parse agent's structured payload, call `/personal-goal-next` per its SKILL.md.
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
