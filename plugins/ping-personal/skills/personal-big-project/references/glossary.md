# Big-project glossary

The words every prompt, report, log row and agent of a run uses. One word per idea, so the owner
and every agent read the same thing; the words under _Avoid_ are not used.

## The run

**Run**: one unattended attempt at one goal, from start step 1 to the closing actions.
_Avoid_: job, session, campaign

**Coordinator**: the Opus session that owns the run, makes the decisions and launches stages.
_Avoid_: main agent, orchestrator, dispatcher

**Tick**: the 30-minute Cron prompt that asks run_state.py for the next action and does it.
_Avoid_: heartbeat, loop, cron job

**State folder**: `docs/<goal-slug>/autopilot/`, the files the run lives in.
_Avoid_: workspace, docs folder

**Goal brief**: GOAL-BRIEF.md, the owner-approved statement of what done looks like.
_Avoid_: spec, requirements doc

## The work

**Stage**: one background workflow that runs a group of tasks.
_Avoid_: phase, wave, workflow (for the unit)

**Task**: one unit of work with an id, an agent, a check and an estimate, sized to one fresh context.
_Avoid_: ticket, step, job

**Item**: one thing the done command counts (a report, a page, a test case). A task may cover many items.
_Avoid_: task (for this meaning), case

**Done command**: the command whose last line says the whole goal passes or fails.
_Avoid_: gate, acceptance script, harness (for this meaning)

**Check**: a task's own fast command that proves that task. **Stage check**: the done command, run once at the end of a stage.
_Avoid_: test (unqualified), done-check

**Verifier**: the agent that runs a check and reports its last line; never the agent that did the task.
_Avoid_: tester, QA agent

## Outcomes

**Passed**: the verifier saw the expected last line.
**Deferred**: set aside with evidence, for the owner to confirm. **Agent-deferred**: deferred by an agent or a critic gate; counted in the verdict.
_Avoid_: skipped, dropped, parked

**Regression**: a failure in code this run changed since the base commit. Never deferred.
_Avoid_: new bug, side effect (for this meaning)

**Verdict**: the one line run_state.py prints at the end, for example `PASS (51 of 53 tasks; 2 deferred, 1 by agents)` or `STOPPED (...)`.
_Avoid_: result, status, score

**Critic gate**: up to three reviewer seats asked one after another; two agreeing votes decide retry, defer or stop.
_Avoid_: panel, vote (alone), review

**Judge review**: the last check on the whole run: five reviewers list problems, one judge rules each one fix now, later, flagged for the owner, or never.
_Avoid_: panel, vote, critic gate (for this meaning)

## Limits and records

**Base commit**: the commit HEAD pointed at when the run started; every diff is measured from it.
**Side effect**: anything that leaves the machine or the repo (mail, push, deploy, API call). **Cap**: its allowed total.
**Pause**: a stop for the 5-hour window, resumed automatically after the reset. **Handoff**: the note written at 70% context; the run continues.
**Decision row**: one line in log/decisions.md. **Workaround**: one line in log/skill-friction.md, logged whenever this skill did not fit.
**Retro**: RETRO.md, the process review that feeds the next version of the skill.
