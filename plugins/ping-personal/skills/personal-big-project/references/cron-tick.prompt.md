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
<!-- <PROJECT_STEPS> : inputs.json projectSteps, one numbered line each, or "none". Example: 1. After s1-plan has a RESULT, run personal-critic-judge on plan.md -->

```text
<GOAL> <EVERY>-minute tick (unattended). Never ask the owner anything and never wait for them; the only
exception is the cap question in step 3, sent by phone while the run keeps going. Follow these steps in order.

1. Quota: run_state.py reads ~/.claude/live-usage/<SESSION_ID>.json itself and refreshes a stale one with
   <QUOTA_PS1>; never type meter numbers into the command.
2. Run python "<SKILL_DIR>/scripts/run_state.py" next --state-dir "<STATE_DIR>" --usage ~/.claude/live-usage/<SESSION_ID>.json
   It logs the quota row, rebuilds the STATUS.md task table and TIMELINE.md, checks the machine, and
   prints one JSON action. Before the action, read three fields of that JSON:
   - "refresh" not "ok" and not "skipped...": fix the cause (it names the error) and add a log/skill-friction.md row.
   - "box"."new" not empty: PushNotification each new line in one plain sentence, plus its HINT line when
     there is one (a command the owner may run; never run a HINT yourself).
   - "cost"."warn" true: PushNotification "Cost: <spent> spent, about <projected> projected against the
     estimate <estimate> (<ratio>x). Reply trim <what>, or go." Add a log/decisions.md row and keep going;
     never wait for the answer. When the user answers, copy their words into STATUS.md "Owner decisions".
   Then do exactly that action:
   - WAIT: nothing.
   - PAUSE: TaskStop the running workflow if any; CronCreate ONE one-shot (recurring false) at the
     returned time with the prompt '<GOAL> resume: relaunch - run the tick steps 1-4 now'; then
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
     commit with git ls-remote; then run_state.py record final --done-line "<the final stage check's lastLine>" and write
     OWNER-REPORT.md with the verdict line it prints.
   - CHECK: run python "<SKILL_DIR>/scripts/check_run.py" --state-dir "<STATE_DIR>" --transcript <this session's .jsonl>.
     PASS -> run_state.py record checked pass. FAIL -> fix only what can be fixed honestly (never
     re-take a baseline), run it once more, then record checked pass, or record checked fail <names>
     and put the names in OWNER-REPORT.md.
   - STOP: TaskStop the stage the action names, if any; run_state.py record final --stopped <reason>;
     write OWNER-REPORT.md with that verdict and the reason; then do CHECK; then run_state.py record close <reason>.
   - CLOSE: write RETRO.md (SKILL.md "Feedback loop"), PushNotification "DONE" with the verdict (a verdict
     starting FAIL or carrying RUN CHECK FAIL: "NOT DONE:" and the open items instead), and CronDelete this tick.
   A workflow that died or was stopped outside a PAUSE: run_state.py record interrupted <stage>.
   Every decision you make that the script did not dictate goes into log/decisions.md; a stop or hold
   you chose on your own because work was risky or overdue starts with "self-stop:".
   After any rewrite of the STATUS.md Now block, run python "<SKILL_DIR>/scripts/log_row.py" status --state-dir "<STATE_DIR>".
3. Owner messages: log each message the user sent since the last tick, as it arrives, with
   python "<SKILL_DIR>/scripts/log_row.py" owner --state-dir "<STATE_DIR>" --class <class> --skill <skill> --missed "<what>" --quote "<their words>"
   (rule 12). A fix, complaint or premature row also files a skill-friction row by itself.
   Caps: run python "<SKILL_DIR>/scripts/log_row.py" usage --state-dir "<STATE_DIR>". For a new WARN or FULL
   line, PushNotification it in one plain sentence. When a task stopped with "cap reached: <kind>", also
   PushNotification the question "<kind> cap <cap> reached. Reply raise <kind> to <n>, or stop." and keep
   the rest of the run going; never wait for the answer. When the owner answers, run log_row.py raise-cap
   --state-dir "<STATE_DIR>" --kind <kind> --to <n> --note "<their words>", copy their words into STATUS.md
   "Owner decisions", and add the stopped task back as an ADDED task for the next stage.
4. Report: if the action says report true, get the report text into <STATE_DIR>/log/report-draft.md: dispatch
   the reporter in the background (agentType ping-personal:amanda, model sonnet, effort low) with the brief in
   "<SKILL_DIR>/references/reporter-brief.md", plus two lines: "Now: <Day MM-DD HH:MM from a clock command>"
   (she has no shell) and "Report shape: <REPORT_SHAPE>"; or, at a 15-minute interval, write it yourself
   from the same state files. Then, whoever wrote it, run
   python "<SKILL_DIR>/scripts/log_row.py" report --state-dir "<STATE_DIR>" --file "<STATE_DIR>/log/report-draft.md".
   REFUSED names the codes: rewrite them in plain words and run it again. Post only the SAVED file: paste the
   full report text and its path in chat (never a digest), PushNotification its first sentence as one plain human
   sentence, post it to the owner's Slack channel if one is set, and run run_state.py record reported
   <run-log rows>. If the report starts with "copilot talk did not load", add a row to log/skill-friction.md.
   If report is false, send nothing. The task table and timeline are rebuilt in step 2 either way.
5. Project steps the user set at start (do each when its condition holds, then log it in log/decisions.md):
<PROJECT_STEPS>
```
