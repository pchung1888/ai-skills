# Pre-flight checks (start step 4)

Run every check in the session that will go unattended, while the user is still present. Each check
ends with one line `PASS <name>` or `FAIL <name>: <what to do>`. Any FAIL: fix it or tell the user the
exact command to run, then re-run that check. Never go unattended with a FAIL, because nobody can
fix it later.

Checks 1, 6, 7, 8 and 11 are scripted. Run them first; each parameter is explained at the top of the
script:

```text
pwsh -NoProfile -File ${CLAUDE_SKILL_DIR}/scripts/preflight.ps1 -RepoPath <repo> -StateDir <state-dir> `
  -DoneCommand "<done command>" -PassLine "<pass line>" -Disks C:,D: -MinGB 1 -WeeklyCap 85
```

Then run checks 2, 3, 4, 5, 9, 10, 12 and 13 yourself with the real tools, because a permission prompt,
a cron fire or a phone buzz can only be seen from inside the session.

| # | Check | PASS when |
|---|---|---|
| 1 | Coordinator model | `model` in `~/.claude/live-usage/<sessionId>.json` names Opus |
| 2 | Permissions, allowed | With no prompt: a delete in a scratch folder through Bash and through PowerShell, the plan's build command, one read on each data store the plan uses, a Write to a state file, `git push` to a scratch ref (the one push allowed outside the target branch; delete the ref right after) |
| 3 | Permissions, blocked | Against a throwaway local bare repo added as a temporary remote (so nothing real is harmed if a guard is missing): `git push --force`, `git push -f` and a tag push are refused through Bash AND through the PowerShell tool; a write to each never-touch file is refused. If one goes through, the guard is missing: tell the user which deny rule or hook to add (this skill never edits settings). Remove the temporary remote afterwards |
| 4 | Tick fires | A one-shot CronCreate 1 minute out appends a line to `log/run-log.md` |
| 5 | Phone | PushNotification (and the Slack post, if chosen) arrives; the user confirms on the phone |
| 6 | Quota sensor | The live-usage snapshot is under 15 min old, or `quota.ps1 -Provider claude` succeeds; the weekly forecast (stages x measured tokens per stage) stays under the budget cap |
| 7 | Disk | Free space on every listed disk is above its minimum |
| 8 | State folder | STATUS.md and every log file (`run-log.md`, `quota-log.md`, `side-effects.md`, `skill-friction.md`) exist and accept an append |
| 9 | Workflow resume | A toy 2-agent workflow, stopped with TaskStop after agent 1, relaunched with `resumeFromRunId`, returns agent 1's cached result. Also log in `log/skill-friction.md` what its journal file showed after the TaskStop (status, written or not) and after the resume (same runId, rewritten or not): run_state.py assumes the resumed run rewrites the same journal |
| 10 | Git push auth | `git push` to the target branch (or a scratch ref) succeeds without a prompt |
| 11 | Done command is RED | The done command runs and its last line is the failing line (`-FailLine`, by default the pass line with PASS changed to FAIL). Any other last line means the command itself is broken; a goal that cannot fail cannot be proven finished |
| 12 | No blocking popup | Make one deliberate error in each local program the plan drives (a web page, a script host, a DLL call). Each returns an error and no window opens: a script or JIT debugger dialog, or an error box, holds the request until someone clicks it, which stalls an unattended run. If one opens, turn it off with the user's OK and log the setting and its reverse in `log/decisions.md` |
| 13 | Cost estimate | Tokens per agent from check 9's toy (or, without one, 46K to 74K, the averages of the last two runs) x agents per task (2 when the first try passes; up to 9 with a fix, three critic seats and a second check) x tasks in the plan, plus the tasks added during a run (the last run planned 32 and finished 49). Write the low and high numbers into GOAL-BRIEF.md "Cost estimate" and the user accepts them, or trims the scope now. Asking them after the first stage has spent 500K is too late |

After all PASS, tell the user once: the tick lives in this session, so closing Claude stops the run;
STATUS.md holds the resume command for a new session.
