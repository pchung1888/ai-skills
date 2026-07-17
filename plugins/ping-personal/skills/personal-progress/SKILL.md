---
name: personal-progress
model: haiku
description: Capture current session state as a structured handoff document in docs/progress/YYYY-MM-DD-<task>-progress.md. TRIGGER when (1) agent or user is about to stop mid-task, (2) any limit is approaching (context, session, weekly, daily, or token), (3) user uses preparative phrasing like "I'll need X soon", "going to need", "before we stop", "wrap up", "stopping for today", "stopping soon", or (4) user says "save progress", "handoff", "capture state", "create progress", "create handoff", "write progress", "write handoff", or "/personal-progress". Trigger PREPARATIVELY -- fire NOW even when the user says "soon" or "once we hit a good stopping point" so the artifacts are ready. If the user also asks to park open questions for the next session, ALSO write a sibling docs/progress/YYYY-MM-DD-<task>-handoff.md. Progress = WHAT happened. Handoff = WHAT NEXT-YOU NEEDS TO DECIDE. Do NOT trigger for final commits on complete tasks -- use TODO.md instead.
user_invocable: true
---

# /personal-progress -- Session Handoff Skill

Capture the current session state as a structured progress file so the next
session (or agent) can resume without losing context.

---

## Step 0: Gather State

Before writing anything, collect the following facts. Pull everything a tool
can read yourself; ask the user only for what tools cannot see (runtime
side-effects, test results you did not run). Do NOT leave blanks in the
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
- The sibling handoff file (Step 2.5) is `-handoff.md` on the same base.

Use the bundled template at
`${CLAUDE_PLUGIN_ROOT}/skills/personal-progress/templates/progress-template.md`
as the structure. Fill in ALL sections -- no blanks, no "TBD".

Key rules:

- **Blocker / Stopping Reason:** Be specific. "Context limit hit at Task 3
  Step 2" is good. "Session ended" is bad.
- **Next Steps:** Must be actionable. "Run `npm test -- auth.spec.ts`" is
  good. "Continue work" is bad.
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

## Step 2.5: Sibling Handoff File (if user requested it OR if open decisions exist)

Write a sibling handoff file at
`docs/progress/YYYY-MM-DD-<task-slug>-handoff.md` when ANY of these are true:

- User explicitly mentions both "progress.md and handoff.md" (or equivalent).
- User says "save the questions for next session" / "ask me on the next
  session" / "don't ask me now".
- You have open user-decisions blocking next-session resume that you would
  otherwise ask inline.

The handoff file's purpose is the OPPOSITE of the progress file: progress
describes state; handoff describes pending decisions. Each open question
gets:

- A clear question ("Should we do A or B?")
- 2-4 options with trade-offs (table or list)
- Your recommendation
- The default action you'll take if the user says nothing

End with a "Quick start for next session" section telling next-you (or the
user) what order to resolve questions in before resuming work.

If you are NOT writing a handoff file (no pending decisions, user didn't ask
for one), skip this step entirely.

---

## Step 3: Confirm and Optionally Commit

After writing the file:

1. Show the user the path: `docs/progress/<filename>.md`
2. Ask: "Commit this progress file now, or leave it unstaged?"
   - If commit: `git add docs/progress/<filename>.md && git commit -m "progress: capture state for <task-slug>"`
   - If no commit: leave unstaged (it will not be lost -- just not in history)

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
