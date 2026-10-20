---
name: personal-big-project
model: inherit
disable-model-invocation: true
argument-hint: "start <requirement.md> | resume|status|stop|retro <state-dir> | improve"
description: Hands a large multi-stage engineering goal to this Opus session to run unattended for hours or days (Friday night to Monday) - plan, test first, build, install, verify, commit - with a 30-minute phone report and self-imposed limits on quota, context, disk and side effects. Every run ends with a process retro that feeds the next version of the skill. Use when the user types /personal-big-project to start, resume, check, stop or retro such a run, or to improve the skill from past retros.
---

# /personal-big-project

The user hands over a big goal before leaving. This session stays open as the coordinator: it makes
every decision while they are away, one background Workflow per stage does the work, a 30-minute
Cron tick asks `scripts/run_state.py` what to do next, and state files let any new session pick
the run back up. Claude Code runs the skill (it needs Workflow and session Cron); Codex serves as a
critic seat when it is available, and `agents/openai.yaml` stops Codex from starting this skill on
its own.

## Rules that hold in every mode and every agent

1. **Ask only while the user is present.** Before they leave, ask everything (start step 2). After they
   leaves, never ask: the coordinator decides, or a critic gate votes; the choice is built to be easy
   to reverse, logged, and named in the next report. A question nobody answers freezes the run.
2. **Pass comes only from the done command's output,** run by a verifier agent that did not do the
   work, never from a worker saying "passed". NOT-RUN is never PASS.
3. **Baselines are captured before any change and never re-taken from new code's output.**
   Loosening an assertion needs predicted vs observed written down and a reviewer's sign-off.
   The stage check also runs `python <critic-gate>/lib/floor_guard.py --base <baseCommit>`
   (the personal-critic-gate floor-guard reference); a hit is a regression unless a
   `log/decisions.md` row signs it off.
4. **Side effects have hard caps** (inputs.json `caps`: mail, pushes, deploys, API calls). Write the
   side-effects row before acting. Never push a tag. Push only to the target branch.
5. **The user's explicit asks are inputs, not proposals.** Offer a cheaper option once; the default
   stays what they asked for.
6. **Every timestamp comes from a real clock.** Owner-facing text uses `Day MM-DD HH:MM` local.
7. **Owner-facing text is plain words in the run's own vocabulary:** the words in
   [references/glossary.md](references/glossary.md), never ids, hashes, stage codes or agent names;
   12 lines max. Agents use the same words, because a shared vocabulary, not "be concise", is what
   keeps reports short and unambiguous.
8. **At most 3 agents at once:** parallel groups hold at most 2 tasks, leaving room for the
   reporter; critic seats run one after another; exclusive resources (a
   database, IIS, one browser) are declared per task and never shared inside a parallel group.
9. **State lives in files.** STATUS.md and run-state.json are enough to resume after a crash, a
   compaction or a new session. Only `run_state.py` writes run-state.json.
10. **Log every decision and every workaround.** Each decision the coordinator makes that a script
    did not dictate goes into `log/decisions.md` (`| Day MM-DD HH:MM | decision | options | why | cost |`);
    each time a template, rule or step of this skill does not fit, a row goes into
    `log/skill-friction.md` (`| Day MM-DD HH:MM | skill step | what did not fit | what I did instead |`).
    The retro and the next version of the skill learn from these rows; an unlogged one is lost.
11. ASCII only in every file. Agent findings carry EXTRACTED / INFERRED / UNKNOWN labels.

## The shape (fixed parts; the coordinator decides inside them)

| Part | What it is | Why |
|---|---|---|
| Coordinator | This session. It must be Opus; pre-flight refuses otherwise. It launches stages, reads journals, edits STATUS.md and answers the user, and never does heavy work itself. | The user can ask the running session anything; its context grows only by tick text |
| Next action | `scripts/run_state.py next` decides launch, retry, resume, pause, wait, handoff, final, stop or close from run-state.json, quota and disk | The stop, skip, no-progress and quota rules are tested code, so they hold after a compaction |
| Stages | One background `Workflow` per stage, generated from [references/stage-workflow.template.js](references/stage-workflow.template.js) by `scripts/generate.py` | `resumeFromRunId` replays finished agents after an interruption |
| Tick | Session `CronCreate` every 30 minutes, prompt from [references/cron-tick.prompt.md](references/cron-tick.prompt.md) | One heartbeat; it does only what run_state.py says |
| State | `docs/<goal-slug>/autopilot/` in the target repo, from [references/STATUS.template.md](references/STATUS.template.md) | Survives everything the session does not |

The tick dies if Claude exits. Pre-flight warns the user, and STATUS.md always holds the resume command.

## Which agent for which job

The coordinator picks per task and may use any installed agent or built-in type that fits better;
`generate.py` refuses an agent that does not exist and a committing task given to an agent without
a shell.

| Job | Default agent | Model / effort |
|---|---|---|
| Plan writing, 30-minute report, boss report, retro draft | ping-personal:amanda (no shell: never give her a commit) | sonnet, low for reports |
| Code, scripts, tests, fixes | ping-personal:bunny | workerModel (sonnet), or inherit for hard tasks |
| Parsers, data contracts, SQL, ingestion | ping-personal:vex | workerModel |
| Research, discovery, fresh-eyes review | ping-personal:iris | sonnet, low |
| Verifier (re-runs the done-check), QA, test strategy | ping-personal:rhea | sonnet, low |
| Critic seats | ping-personal:ms-mario, ping-personal:rhea, and the domain critic (codex:codex-rescue when available; codex is never a task agent) | low |
| UI, design, charts | ping-personal:maggie | workerModel |
| Git: commit, push, tag check, PR | ping-personal:dora | sonnet |

Worker effort: `low` on Fable, inherit on Opus. Helper effort (reporter, verifier, critic seats,
reviewer) is always `low`. Tokens are logged per stage, so the choices can be measured.

## start

Copy this checklist into the reply and tick it off. The user is present for steps 1-6.

```text
Start progress:
- [ ] 1 Inputs collected into inputs.json; every cap and fence has a value
- [ ] 2 Alignment at the door: grilled to shared understanding; GOAL-BRIEF.md approved by the user
- [ ] 3 State folder created; run_state.py init done
- [ ] 4 Pre-flight: every check in references/pre-flight.md prints PASS. If one fails, fix it and return to step 4
- [ ] 5 Plan stage launched and recorded; tick created
- [ ] 6 User told: keep this session open, how to resume, when the first report arrives
- [ ] 7 Unattended from here: rule 1 now means never ask. Write the current UTC time (ISO, ending in Z) as "unattendedSince" in inputs.json
```

**Step 1. Inputs.** Ask for anything missing, then save `<state-dir>/inputs.json` (shape at the top
of `scripts/generate.py`, including `caps` and `sessions`). Record the fixed point the whole run is
judged against: `baseCommit` from `git rev-parse HEAD`, and `remoteTagsAtStart` / `remoteHeadsAtStart`
from `git ls-remote --tags <remote>` and `git ls-remote --heads <remote>`; the regression rule, the
final review and check_run all diff against them. Done when each row has a value.

| Input | Example shape |
|---|---|
| Requirement, verbatim | path to a .md file |
| Done command | a command whose last line is `ALL ... PASS` only when everything passes, and `ALL ... FAIL` otherwise |
| Away window | Fri 19:00 -> Mon 08:00 |
| Phone channel | PushNotification on, Slack channel name or none |
| Scope fences | files never to touch; what counts as shipped code; protected branches |
| Side-effect caps | {"mail": 300, "push": 20}; push target branch; no deploys |
| Resources | exclusive resources; disks to watch with minimum free GB |
| Budget | weekly % at which to stop starting new stages |

**Step 2. Alignment at the door.** A 30-hour run on a misread goal wastes the whole weekend, and
this is the last moment the user can be asked anything. Read the requirement and the code it touches,
then interview them in rounds. Treat the open questions as a dependency graph: each round asks only
the questions whose prerequisites are answered, numbered Q1, Q2, ..., each with a recommended safe
default, so they can answer by voice ("Q1 agree, Q2 change it to ..."). Answers unlock the next round;
stop when no decision is left that a worker would have to guess. Call the Skill tool with grill-me
when a branch needs deeper questioning. Cover what done looks like to them on Monday, what is out of scope, and what would
disappoint them even if every test passes. Then write `GOAL-BRIEF.md` in the state folder: the goal
in their words, done-on-Monday, out of scope, disappointments to avoid, every decision with its
answer, and the line `Corrections before approval: <n>`. Show it and ask them to approve or correct
it; each correction round adds one to n. Copy the decisions verbatim into STATUS.md "Owner
decisions". Done when the user approves the brief.

**Step 3. State folder.** Create STATUS.md from the template, `plan.md`, `tasks.csv` (header
`id,stage,what,estimate,added`), `reports/`, and `log/` with `run-log.md`, `quota-log.md`, `side-effects.md`,
`skill-friction.md`, `decisions.md` (header rows as in rule 10 and the template), then run
`python ${CLAUDE_SKILL_DIR}/scripts/run_state.py init --state-dir <state-dir> --stages s1-plan,...`.
Done when every file exists and is writable.

**Step 4. Pre-flight.** Run each check in [references/pre-flight.md](references/pre-flight.md).
On any FAIL, fix it or tell the user exactly what to run, then re-run that check. Never go unattended
with a FAIL.

**Step 5. Launch.** Write the plan stage's task sections into `plan.md` first (discover, plan,
critics, revise, commit, each with its done-check), because every agent executes its section of
plan.md and an empty section means a guaranteed failure. Write its spec to `stages/s1-plan.json`,
run `python ${CLAUDE_SKILL_DIR}/scripts/generate.py stage --state-dir <state-dir> --spec <spec>`,
launch the printed `.js` with Workflow `scriptPath` in the background, and record it with
`run_state.py record launch s1-plan <runId>`. Run `generate.py tick --state-dir <state-dir>` and
pass `tick-prompt.txt` to CronCreate (`7,37 * * * *`, recurring). Never hand-edit the templates;
a GENERATE FAIL names what to fix. Write the run id and the resume command into the STATUS.md Now
block.

**Step 6. Tell the user** in at most 5 lines: what runs, when the first report arrives, keep the
session open, and the resume command for a new session.

## Stages (default; the plan may add or split)

1. Plan: discover (up to 3 in parallel) -> plan with task ids, done-checks, agent per task -> 3 critics -> revise -> dora commits.
2. Harness first: backups, test tools, pre-change baseline (hashes into baseline-hashes.txt), RED proof, adversarial and fresh-eyes review -> commit.
3. Build: spikes, parallel work on independent files, critic and TDD gate -> commit.
4. Install and verify: full done command, fix rounds until run_state.py stops them, rollback rehearsal.
5. Final: fresh-eyes review of the evidence, one verdict, OWNER-REPORT.md, final commit verified on the remote.

The plan writes, per stage, a task table that the coordinator turns into each stage's spec: id,
agent, phase, needs, commits, resources, and two required fields:

- `check`: the task's own fast check (one test file, one script). The verifier runs it after the
  task. The full done command is slow (one full run took 3 h 42 m on the run this skill is built
  from), so it runs once per stage as `stageCheck`, never per task. A retry spec for a failed stage
  check carries the same `stageCheck` again, or that item can never resolve.
- `estimateK`: expected context in thousands of tokens, at most 100. Quality drops past about 140K,
  so a bigger task is split before launch; generate.py refuses it otherwise.

The last stage sets `finalReview: true`: two fresh reviewers, one after the other, report on two
separate axes that are never merged: Spec (amanda: the diff from baseCommit against GOAL-BRIEF.md)
and Standards (ms-mario: the repo's standards and conventions). The final critic-gate verdict must
carry `Reviewed: <sha>`; refuse a PASS whose sha is not HEAD (`tally.py --final --sha <sha> --expect-head`, exit 2 = stale; an owner's "ship anyway" on a FIX is
not blocked). A stage that tests code adds the
tests before the code.

## Fix, defer or stop (per failing item)

Each task runs `run()` from the template: worker -> verifier re-runs the done-check -> one
root-cause fix -> verifier -> critic gate (seats one at a time, 2 agreeing votes needed). The goal
is a finished run, not a perfect one: fix what can be fixed, hand back what cannot, and never spend
tokens repeating an attempt that already failed the same way.

| Situation | Action |
|---|---|
| A bug the run can find | Fix it (superpowers:systematic-debugging). A failure in code this run changed is never deferred: that is a regression |
| The fix needs an owner decision or business knowledge | Defer with a safe default, AGENT-DEFERRED; the stage carries on with the next task |
| Something outside the repo is missing (data, server, credential, access) | Defer, AGENT-DEFERRED, with what the user must provide |
| The second attempt fails with the same root cause | Critic gate votes retry (only with a new root cause), defer (never for a regression) or stop; with no 2-vote quorum the item is deferred, never the run stopped |
| A task needs a deferred task | It is deferred too ("blocked by"), so no retry burns tokens on it |
| A stage ends with failed items | run_state.py retries only those items in a fresh stage; 2 attempts in a row with no new pass stop the run |

A deferred item carries its failing output, the root cause found so far and how to resume it.
Only the user shrinks the scope, so every AGENT-DEFERRED item is counted in the verdict line and
listed in OWNER-REPORT.md for them to confirm or reverse.

## When the run is done

`run_state.py next` returns FINAL when every stage is done, meaning every task passed or was
deferred; this outranks every quota and disk check, so a finished run always closes cleanly.
FINAL: dora commits the state folder, pushes, and verifies the commit with `git ls-remote`; then
`run_state.py record final` prints the verdict, for example
`PASS (51 of 53 tasks; 2 deferred, 1 by agents)`, and OWNER-REPORT.md gets that exact line plus
the "## Evidence" and "## Merge danger" sections from [references/reporter-brief.md](references/reporter-brief.md).
The next action is CHECK: run
`python ${CLAUDE_SKILL_DIR}/scripts/check_run.py --state-dir <state-dir> --transcript <this session's .jsonl>`
(every required state file present, inputs valid, real-clock log times, plain reports, no table
row lost, side effects within caps, baselines untouched, verdict matching the outcomes, no question
asked while away) and record `checked pass` or `checked fail <names>`. A failed check is never
hidden: the verdict gains "RUN CHECK FAIL (<names>)". Then CLOSE: write RETRO.md (Feedback loop),
push one phone message and delete the tick, because later ticks would only repeat "done" and
spend tokens.

run_state.py stops the run early when any of these holds; the coordinator stops the running stage,
records `final --stopped <reason>` (verdict `STOPPED (...)`), writes OWNER-REPORT.md, runs CHECK
and the same closing actions:

- no new item has passed across 2 stage attempts in a row (more retries only burn tokens);
- weekly quota reaches the budget cap (the running stage finishes first);
- the critic gate votes stop;
- free disk falls below the minimum.

Not a stop: the 5-hour window. At 90%, or when the burn rate would run it out before the next
tick, run_state.py returns PAUSE; the coordinator stops the running stage, creates one one-shot
cron for 5 minutes after the reset, and the run resumes with `resumeFromRunId`. Also not a stop:
coordinator context at 70% returns HANDOFF once per crossing; write the handoff into STATUS.md and
keep running.

## resume, status, stop

- **resume `<state-dir>`:** append this session's id to inputs.json `sessions`, read STATUS.md top to
  bottom, run `generate.py tick` and re-create the tick, then run the tick's step 2 once by hand.
- **status `<state-dir>`:** answer from `run_state.py status`, the newest report and STATUS.md; do
  not dispatch agents.
- **stop `<state-dir>`:** TaskStop the running stage, `run_state.py record close owner-stop`, write
  OWNER-REPORT.md and RETRO.md, delete the tick.
- **retro `<state-dir>`:** The user is back. Ask them two questions: how well the result matched what
  they wanted (1 missed to 5 exactly), and what surprised them. Add both answers, verbatim, to RETRO.md
  under "Did it match what the owner wanted", then copy RETRO.md again to the retro folder.
- **improve:** run in the plugin repo. Read every file in `~/.claude/big-project-retros/`, group
  the friction rows, decision rows and proposed changes by skill step, and rank them by how many runs
  hit them and what they cost. Then use the skill-creator-plus skill in REFINE mode on this skill,
  changing nothing until the user picks which changes to make.

## Feedback loop (every run)

Each run is also a test of this skill, so each run leaves evidence for the next version:

1. During the run: rule 10's decision and friction rows, plus critic votes and steering rules in STATUS.md.
2. At the closing actions: run `python ${CLAUDE_SKILL_DIR}/scripts/retro_metrics.py --state-dir
   <state-dir> --transcript <this session's .jsonl>`. Agents rarely report their own friction, so
   one fresh ping-personal:iris reads the transcripts in its "Transcript sample for the retro"
   list and reports the friction nobody logged. Then amanda drafts RETRO.md from
   [references/retro-template.md](references/retro-template.md) around the numbers, the two logs and
   that sample. Keep it about the process only, never the project's content, so the plugin repo can
   read it. RETRO.md only proposes; the user picks what changes (improve mode), because an automated
   fixer chases false positives.
3. Copy RETRO.md to `~/.claude/big-project-retros/<YYYY-MM-DD>-<goal-slug>.md`, outside every repo,
   so retros from all projects collect in one place.
4. End OWNER-REPORT.md with one line: run `/personal-big-project retro <state-dir>` to rate this run.
5. When the user has a few retros, they run `improve` in the plugin repo.

## Reporting

- The tick rebuilds PROGRESS.md with `scripts/build_table.py` (from tasks.csv, every session's
  journals, run-state.json and the run log) at no token cost; contract in
  [references/reporter-brief.md](references/reporter-brief.md).
- The reporter is amanda, fresh each time, on sonnet at low effort, reading only state files, and
  runs only when run_state.py says the run log changed.
- In chat, paste a 3-line digest and the report's path; PushNotification the first sentence; post the
  full report to the user's Slack channel when one is set.

## References

| File | Open when |
|---|---|
| [references/pre-flight.md](references/pre-flight.md) | start step 4, and after any pre-flight FAIL |
| [references/stage-workflow.template.js](references/stage-workflow.template.js) | reading what a generated stage does |
| [references/cron-tick.prompt.md](references/cron-tick.prompt.md) | creating or re-creating the tick |
| [references/STATUS.template.md](references/STATUS.template.md) | start step 3 |
| [references/reporter-brief.md](references/reporter-brief.md) | each report; boss report on request |
| [references/retro-template.md](references/retro-template.md) | closing actions; retro mode |
| [references/glossary.md](references/glossary.md) | writing any report, prompt, log row or spec |
