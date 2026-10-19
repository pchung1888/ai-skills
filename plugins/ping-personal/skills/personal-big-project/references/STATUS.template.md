# <GOAL> -- live status (every agent reads this first)

<!-- <GOAL> : short goal name. Example: PROJ-123 invoice fixes -->
Every task appends one line to `log/run-log.md` and rewrites the "Now" block below.
Times: `Day MM-DD HH:MM` local, from a real clock command, never estimated.

## Binding rules (newest last; each dated, with author; overrides any task text)

<!-- One bullet per steering rule added during the run. Example: - MAIL CAP (Fri 10-16 20:55, coordinator): max 40 sends per run, 300 total. -->
- Never ask the owner while unattended; use the critic gate and record the decision below.
- Never take a baseline from the new code's output; baselines are captured before change and never edited.
- Never loosen an assertion without predicted vs observed written here and a reviewer's sign-off.
- Run names are unique; NOT-RUN is never PASS.
- No test-only changes in shipped code.
- No tag pushes; push only to <TARGET_BRANCH>.
<!-- <TARGET_BRANCH> : the only branch agents may push. Example: topic/123-invoice-fixes -->
- Side-effect caps: the "caps" object in inputs.json; write the log/side-effects.md row before acting.

## Now

- Stage: <stage> -- running since <Day MM-DD HH:MM>, workflow run <run id>
- Resume in a new session: /personal-big-project resume <STATE_DIR>
  (it appends the session id, runs generate.py tick, re-creates the tick and asks run_state.py next)
<!-- <STATE_DIR> : this state folder, repo-relative. Example: docs/proj-123/autopilot -->

## Decisions taken without the owner

Critic-gate outcomes and deferrals. The coordinator's other decisions go to log/decisions.md.

| id | When | Decision | How to reverse it | Decided by (critic votes) |
|---|---|---|---|---|

## Owner decisions (verbatim)

| When | Owner said | Applied as |
|---|---|---|

## Stage plan

| Stage | What | State |
|---|---|---|
