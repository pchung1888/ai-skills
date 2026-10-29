# Cron tick prompt (heartbeat every 30 minutes, or the interval the user chose)

`scripts/generate.py tick` fills this; never fill it by hand. CronCreate: the cron line that
generate.py prints (`7,37 * * * *` for 30 minutes), recurring true. The tick runs in the coordinator session, so it can TaskStop and relaunch local
workflows. The decision of WHAT to do comes from `run_state.py next`, not from memory, so the
rules hold after a compaction.

<!-- <GOAL> : short goal name. Example: PROJ-123 invoice fixes -->
<!-- <STATE_DIR> : state folder, repo-relative. Example: docs/proj-123/autopilot -->
<!-- <SESSION_ID> : this session's id (file name under ~/.claude/live-usage/). Example: 7d4f0df1-929c-4862-941e-12ecb5445122 -->
<!-- <QUOTA_PS1> : personal-quota quota.ps1 in the installed plugin. Example: C:/Users/<user>/.claude/plugins/cache/ping-personal/ping-personal/<version>/skills/personal-quota/quota.ps1 -->
<!-- <SKILL_DIR> : this skill's folder (the value of ${CLAUDE_SKILL_DIR} at start). Example: C:/Users/<user>/.claude/plugins/cache/ping-personal/ping-personal/<version>/skills/personal-big-project -->
<!-- <EVERY> : tick interval in minutes, inputs.json report.everyMin. Example: 15 -->
<!-- <REPORT_SHAPE> : report shape the user chose, from inputs.json report. Example: copilot, with the full task list -->

```text
<GOAL> <EVERY>-minute tick (unattended). Never ask the owner anything. Follow these steps in order.

1. Read quota: ~/.claude/live-usage/<SESSION_ID>.json (5h and 7d percentUsed, 5h resetsAt, ctxPct).
   If it is older than 15 min, run pwsh -NoProfile -File "<QUOTA_PS1>" -Provider claude -Json.
2. Run python "<SKILL_DIR>/scripts/run_state.py" next --state-dir "<STATE_DIR>" --five <5h> --week <7d> --reset <resetsAt> --ctx <ctxPct>
   It logs the quota row and prints one JSON action. Do exactly that action:
   - WAIT: nothing.
   - PAUSE: TaskStop the running workflow if any; CronCreate ONE one-shot (recurring false) at the
     returned time with the prompt '<GOAL> resume: relaunch - run the tick steps 1-3 now'; then
     run_state.py record pause <until>. Never create a second one-shot while paused.
   - RESULT: the action's items[0] is the stage's result record,
     ~/.claude/projects/<project>/<SESSION_ID>/workflows/<runId>.json. Run
     run_state.py record result <stage> --journal <that path>. Never pass the task output file or a
     subagent journal: they lack the final status, so the stage would be marked interrupted. Turn open HIGH or CRITICAL review findings
     into ADDED tasks for the next stage and log each in log/decisions.md.
   - LAUNCH or RETRY: write the stage spec (RETRY: only the returned items) from plan.md, run
     python "<SKILL_DIR>/scripts/generate.py" stage --state-dir "<STATE_DIR>" --spec <spec>, launch the
     printed .js with Workflow scriptPath in the background, then run_state.py record launch <stage> <runId>.
   - RESUME: relaunch the same script with resumeFromRunId <runId>, then run_state.py record resumed <stage>.
   - HANDOFF: write a handoff into the STATUS.md Now block (state, next action, resume command),
     run_state.py record handoff, and keep going.
   - FINAL: have ping-personal:dora commit the state folder, push to the target branch and verify the
     commit with git ls-remote; then run_state.py record final and write OWNER-REPORT.md with the
     verdict line it prints.
   - CHECK: run python "<SKILL_DIR>/scripts/check_run.py" --state-dir "<STATE_DIR>" --transcript <this session's .jsonl>.
     PASS -> run_state.py record checked pass. FAIL -> fix only what can be fixed honestly (never
     re-take a baseline), run it once more, then record checked pass, or record checked fail <names>
     and put the names in OWNER-REPORT.md.
   - STOP: TaskStop the stage the action names, if any; run_state.py record final --stopped <reason>;
     write OWNER-REPORT.md with that verdict and the reason; then do CHECK; then run_state.py record close <reason>.
   - CLOSE: write RETRO.md (SKILL.md "Feedback loop"), PushNotification "DONE" with the verdict,
     and CronDelete this tick.
   A workflow that died or was stopped outside a PAUSE: run_state.py record interrupted <stage>.
   Every decision you make that the script did not dictate goes into log/decisions.md.
3. Report: if the action says report true, run python "<SKILL_DIR>/scripts/build_table.py" --state-dir "<STATE_DIR>",
   then dispatch the reporter in the background (agentType ping-personal:amanda, model sonnet, effort low)
   with the brief in "<SKILL_DIR>/references/reporter-brief.md", plus two lines: "Now: <Day MM-DD HH:MM
   from a clock command>" (she has no shell) and "Report shape: <REPORT_SHAPE>". When it returns: paste a 3-line digest
   and the report path in chat, PushNotification the first sentence, post the full report to the
   owner's Slack channel if one is set, and run run_state.py record reported <run-log rows>.
   If report is false, send nothing.
```
