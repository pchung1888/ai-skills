# <GOAL> -- live status (every agent reads this first)

<!-- <GOAL> : short goal name. Example: PROJ-123 invoice fixes -->
The verifier appends one line per task to `log/run-log.md` with `scripts/log_row.py`; only the
coordinator rewrites the "Now" block below.
Times: `Day MM-DD HH:MM` local, from a real clock command, never estimated.

## Binding rules (newest last; each dated, with author; overrides any task text)

<!-- One bullet per steering rule added during the run. A rule the coordinator wrote after something went wrong names it with incident:, which the scorecard counts as self-caught. Example: - MAIL CAP (Fri 10-16 20:55, coordinator, incident: a re-run sent 8 extra mails): max 40 sends per run, 300 total. -->
- Never ask the owner while unattended; use the critic gate and record the decision below.
- Never take a baseline from the new code's output; baselines are captured before change and never edited.
- Never loosen an assertion without predicted vs observed written here and a reviewer's sign-off.
- Run names are unique; NOT-RUN is never PASS.
- No test-only changes in shipped code.
- No tag pushes; push only to <TARGET_BRANCH>. Never push to <PROTECTED_BRANCHES>: pushing a review request's target can merge it.
<!-- <TARGET_BRANCH> : the only branch agents may push. Example: topic/123-invoice-fixes -->
<!-- <PROTECTED_BRANCHES> : inputs.json protectedBranches from pre-flight check 14, or "none". Example: feature/123, main -->
<!-- Add the next line only when the goal answers review comments; delete it otherwise. -->
- REPLY ORDER: no reply goes out on a review request until every fix is done, its check passed and the code is pushed; then all replies go out together.
- STOP RULES: a stop rule written by the owner or the plan is overridden only by a critic gate vote (2 agreeing seats), never by the coordinator alone. The log/decisions.md row starts with "override:", names the rule, the votes and the reverse step, and the next report says it in plain words.
- Side-effect caps: the "caps" object in inputs.json; run every sending command through `log_row.py send ... -- <command>` (or `log_row.py effect` before an action with no command); REFUSED means do not act; CAP REACHED stops only that task until the owner raises the cap.

## Now

<!-- One line per field. The task table below and TIMELINE.md are rebuilt by run_state.py next on every tick; never by hand. -->
- Stage: <stage> -- running since <Day MM-DD HH:MM>, workflow run <run id>
- Resume in a new session: /personal-big-project resume <STATE_DIR>
  (it appends the session id, runs generate.py tick, re-creates the tick and asks run_state.py next)
- Timeline: TIMELINE.md, every logged event oldest first. Reports: reports/, one file per post, titled with its post time.
<!-- <STATE_DIR> : this state folder, repo-relative. Example: docs/proj-123/autopilot -->

## Decisions taken without the owner

Critic-gate outcomes and deferrals. The coordinator's other decisions go to log/decisions.md.

| id | When | Decision | How to reverse it | Decided by (critic votes) |
|---|---|---|---|---|

## Owner decisions (verbatim)

| When | Owner said | Applied as |
|---|---|---|

## Tasks

Every task from start to end, with the stage budget above it, rebuilt by `scripts/build_table.py` on every
tick (from run_state.py next) and after every verifier row (from log_row.py run); never edit it by hand.
<!-- tasks:begin - scripts/build_table.py rewrites this section every tick; do not edit it -->
<!-- tasks:end -->

## Stage plan

| Stage | What | State |
|---|---|---|
