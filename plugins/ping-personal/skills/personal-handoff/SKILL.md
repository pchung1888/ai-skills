---
name: personal-handoff
model: haiku
description: Captures current session state as two linked files in docs/progress/. The handoff file (YYYY-MM-DD-[task]-handoff.md) is the one the next session reads - next steps, open decisions, suggested skills - and it links the progress file (YYYY-MM-DD-[task]-progress.md) with the history and facts (Progress = WHAT happened; Handoff = WHAT next). Use when work is about to stop mid-task, when any limit (context, session, weekly, daily, token) is approaching, when the user signals an upcoming stop ("soon", "wrap up", "before we stop"), or when they ask to save progress, hand off, or capture state (/personal-handoff, /personal-progress). Fire before the stop actually happens so the artifacts are ready. Not for final commits on completed tasks - those go in TODO.md.
user_invocable: true
---

# /personal-handoff -- Session Handoff Skill

Capture the current session state so the next session (or agent) can resume
without losing context. Every run writes two linked files:

| File | Holds | Who reads it |
|---|---|---|
| `-handoff.md` | Next steps, open decisions, suggested skills | The next session, first and only on request |
| `-progress.md` | History and facts: status, the verbatim ask, doubts, findings | The next session, through the link in the handoff file |

The person starts the next session with one line: "read `<handoff path>`". The handoff
file then tells that session to read the progress file before acting.

If the arguments contain `--unattended`, follow "Unattended mode" at the end of
this file instead of asking anything. Otherwise behave as described below.

---

## Step 0: Gather State

Before writing anything, collect the following facts. Pull everything a tool
can read yourself; ask the user only for what tools cannot see (runtime
side-effects, test results you did not run). Do not leave blanks in the
output file.

| Item | Where to find it |
|---|---|
| Current branch | `git branch --show-current` |
| Real quota | `pwsh -NoProfile -File "${CLAUDE_PLUGIN_ROOT}/skills/personal-quota/quota.ps1" -Json` -- session/weekly %, resets, context %; band via `plan.ps1` |
| Plan file path | Check `docs/plans/` for the active plan |
| Issue tracker ID | Branch name usually contains it (e.g. `topic/123-...`, `feature/JIRA-456-...`) |
| Active PR/MR number | `gh pr view --json number,url` (GitHub) or `glab mr view` (GitLab), or ask user |
| Last commit hash | `git log --oneline -1` |
| Uncommitted files | `git status --short` |
| Last test result | Ask user or check most recent output |
| Runtime / server state | Ask user (any service that needs restart? any side-effect uncommitted to infra?) |
| DB / migration state | Ask user (any pending migrations? any seed data added?) |

The last two rows are placeholders -- adapt them to whatever your project's
"side-effects outside the repo" actually are (caches, deployment slots,
external queues, etc.).

---

## Step 1: Build the Status Table

Read the active plan file (from `docs/plans/`) and mark each task
`[done]` (with commit hash), `[wip]` (with the step it stopped at), or
`[todo]`. If no plan file exists, infer tasks from what was done this session.

---

## Step 2: Write the Progress File

Determine the output filename:

- **Format (MANDATORY):** `docs/progress/YYYY-MM-DD-<task-slug>-progress.md`
  -- the literal `-progress.md` suffix is required, today's date, kebab-case
  slug (e.g. `auth-refactor`).
- If a progress file for this task already exists today, overwrite it (this
  is a snapshot, not a log).
- The handoff file (Step 2.5) is `-handoff.md` on the same base. Write the
  handoff file's path on the progress file's `Handoff:` line, so each file links the other.

Use the bundled template at
`${CLAUDE_PLUGIN_ROOT}/skills/personal-handoff/templates/progress-template.md`
as the structure. Fill in all sections -- no blanks, no "TBD".

Key rules:

- **Writing rule:** prose follows the htsw Explaining sentences rules (20 words or fewer per
  sentence, context first) and the personal-unslop pass. The verbatim ask is the exception:
  copy it as the owner wrote it.
- **The ask (verbatim):** copy the owner's own words -- from the beacon's
  `## Requirement` section if a goal is armed, otherwise from what they actually
  said. Never paraphrase. Next-session plans against whatever is written here, so a
  summary quietly becomes the new requirement, and the aim moves one handoff at a
  time.
- **What I am unsure about:** required. Never "nothing". A handoff that carries only
  conclusions hands the next session maximum confidence and minimum context -- the
  intermediate doubts are precisely what does not survive a handoff unless written
  down on purpose. Name the least confident claim, the assumption worth challenging,
  what was asserted from reading rather than running, and where scope may have crept.
- **Open detours:** copy any row still `open` from the beacon's `## Detours` table,
  with the phase each one blocks. Resume at the phase named there, not at whatever
  was most recently in motion -- that is the difference between returning to the goal
  and letting the detour become the project. A detour whose Origin is `phase-N` is
  drift, not a detour; say so.
- **Goal beacon line:** when the session works on a goal whose tracker path is known,
  write `Goal beacon: <path>` on its own line near the top of the file (the HUD's
  resume-bind reads that line). Example: `Goal beacon: docs/goals/x-audit-tracker.md`.
- **Link, do not restate.** Reference the plan, spec and beacon by path. Keep the
  status table (that is live state the plan does not hold) but not the task prose --
  a restated copy diverges from its source, and the daily overwrite then destroys the
  only artifact that would have shown the divergence.
- **Blocker / Stopping Reason:** Be specific. "Context limit hit at Task 3
  Step 2" is good. "Session ended" is bad.
- **Next Steps go in the handoff file, not here.** The progress file holds
  what happened. What to do next lives in one place only (Step 2.5).
- **Key Findings:** Only non-obvious facts. Skip anything derivable from
  reading the code. Include function signatures, page quirks, gotchas,
  production bugs found.
- **Environment State:** Honest snapshot. If you don't know, write
  "Unknown -- verify before resuming".
- **Quota at Handoff:** fill the quota table from
  `pwsh -NoProfile -File "${CLAUDE_PLUGIN_ROOT}/skills/personal-quota/quota.ps1" -Json` and the band
  from `${CLAUDE_PLUGIN_ROOT}/skills/personal-quota/plan.ps1`. If the sensor returns UNKNOWN/stale,
  say so -- never invent a percentage. When this handoff was triggered by a deferred task (a
  personal-loop marginal band), record the `deferUntil` + `wakeMechanism` so resume timing is
  explicit for next-session.

### Provenance footer (fill it -- do not delete it)

The template ends with a `## Provenance` block. Fill all three lines so the
next session can judge how fresh and trustworthy this doc is:

- **Source tier:** what the doc was generated from (live git state, the plan
  file, this session's tool output, user dictation, etc.).
- **Freshness:** the generation date plus the branch and commit it reflects --
  `Generated YYYY-MM-DD | reflects <branch-name> @ commit <hash>`.
- **Trust:** leave the one-line Honesty Protocol note intact so a reader knows
  `EXTRACTED` claims were observed and `INFERRED` claims were reasoned.

---

## Step 2.5: Write the Handoff File (always -- it is the entry point)

Always write `docs/progress/YYYY-MM-DD-<task-slug>-handoff.md`, even when no
decision is open. The next session is told to read this file and nothing else,
so it must lead there. Use the bundled template at
`${CLAUDE_PLUGIN_ROOT}/skills/personal-handoff/templates/handoff-template.md`.
The progress file describes state; the handoff file describes what comes next.

Sections, in this order:

1. **Read first.** The progress file's path, and one sentence on what it holds.
   Tell the next session to read it before acting.
2. **Goal beacon lines.** The same `Goal beacon: <path>` lines as the progress
   file, so a session that reads only this file still binds the goal.
3. **Next Steps (resume here).** Must be actionable. "Run `npm test -- auth.spec.ts`"
   is good. "Continue work" is bad.
4. **Open decisions.** Each open question gets a clear question ("Should we do
   A or B?"), 2-4 options with trade-offs, your recommendation, and the default
   action if the owner says nothing. Write "none" when no decision is open.
5. **Suggested skills.** See the rules below.
6. **Quick start for next session.** The order: read the progress file, settle
   the decisions, then start Next Steps.

### Suggested skills (fill it -- do not delete it)

Name the skills, workflows and goals this session ran that the next session
should keep using. The owner often starts a goal, a loop, an ultracode run or a
Workflow, and wants the next session to carry on with it.

- Scan this session for: `/personal-goal` and its tracker path, `/personal-loop`
  campaigns, Workflow runs and their script path, ultracode, and any other skill
  called more than once or central to the work.
- One row per item: the skill or workflow name, how to start it (the exact slash
  command, tracker path or script path seen this session), and why the next session needs it.
- Never invent an argument or a path. Copy only what this session used.
- Write "none" when this session used no skill worth repeating.

---

## Step 3: Confirm and Optionally Commit

After writing both files:

1. Show the user both paths, the handoff file first, and the line to start the
   next session with: "read `docs/progress/<base>-handoff.md`".
2. **Before offering to commit, read the verbatim ask back.** This file now carries
   the owner's own words, and `docs/progress/` is tracked in some host repos. Show the
   "The ask (verbatim)" section and the open-detour proofs, and ask whether anything
   should be removed before it enters company-repo history. `/personal-goal` enforces
   the equivalent gate in code (`beacon_writer.py` exit 8); this skill has no CLI of
   its own, so the read-back is a required step, not an optional courtesy. Record the
   answer in the Provenance footer.
3. Ask: "Commit these two files now, or leave them unstaged?"
   - If commit: `git add -f docs/progress/<base>-progress.md docs/progress/<base>-handoff.md && git commit -m "progress: capture state for <task-slug>"`
   - The `-f` is load-bearing: `git add` on a path under an ignore rule exits 1
     even when it stages successfully, so a plain `&&` chain short-circuits and
     the handoff silently never commits. This file is the cross-session carrier;
     whether it reaches git must not depend on the host repo's ignore posture.
   - If no commit: leave unstaged (it will not be lost -- just not in history)

---

## Unattended mode (`--unattended`)

Used by the HUD Handoff button: `/personal-handoff --unattended <tracker paths>`.
Without the flag, nothing above changes.

- **Bound trackers:** every other argument token that is a path ending
  `-audit-tracker.md` is a bound goal tracker.
- **Ask no questions:** each place that would ask the user (Step 0 test result,
  runtime state, DB state) writes `Unknown` plus what was unknown instead.
- **Skip the read-back:** skip the Step 3 verbatim read-back.
- **Never commit:** never commit and never ask about committing; leave the file
  unstaged.
- **Goal beacons:** write one `Goal beacon: <path>` line per bound path, deduped,
  in the order given, in both files.
- **Both files:** still write the handoff file. Each open decision keeps its
  default action, since nobody is there to answer.

---

## Safety Rules

- Never overwrite `docs/plans/` files -- progress goes in `docs/progress/`
  only.
- Never delete existing progress files -- overwrite only if same date + same
  slug.
- Never leave a section blank -- write "Unknown -- verify before resuming"
  if unsure.
- The progress file is for the NEXT session, not this one -- write as if
  explaining to a stranger.
