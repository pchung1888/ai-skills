# Unattended setup -- survive the 5h window, auto-resume after reset

`/loop` cannot auto-resume across a quota reset. To run a campaign unattended,
register a Windows Task Scheduler task that re-fires after the reset. Each fire
reads the beacon and continues; a fire blocked by quota exits clean and the
next fire retries.

## Prerequisites (HARD)

1. Campaign must be FULLY SPECIFIED before arming -- headless ticks cannot brainstorm.
2. Fence hard-halts on ALL irreversible actions (push, DROP TABLE, .env writes) -- never auto-executes.
3. Verify on your plan whether `claude -p` draws from separate Agent SDK credits (INFERRED -- Open Q#6).

## Create the Task Scheduler task

Run once in an admin PowerShell (Claude cannot self-elevate):

```powershell
$action  = New-ScheduledTaskAction -Execute "claude" `
  -Argument '-p "/personal-loop --resume <campaign-slug>"' `
  -WorkingDirectory "<repo-root>"
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
  -RepetitionInterval (New-TimeSpan -Minutes 45)
Register-ScheduledTask -TaskName "personal-loop-<campaign-slug>" `
  -Action $action -Trigger $trigger -RunLevel Limited
```

Stop: `Unregister-ScheduledTask -TaskName "personal-loop-<campaign-slug>" -Confirm:$false`

## Secrets-HALT circuit-breaker

Backed by `lib/halt.py` (implemented + eval-covered). If the secrets scan fires
during an unattended run -- at planning time (tick step 3) OR over the staged diff
before commit (tick step 5):
1. `halt.sentinel("secret-detected")` -> `BLOCKED: secret-detected` is written to
   the campaign beacon child-goal state.
2. `halt.write_halt(...)` writes a `.claude/tmp/secret-halt-<TIMESTAMP>.md` status file.
3. On the next fire, `--resume` calls `halt.is_blocked` on the child-goal state and
   REFUSES to re-run the blocked goal without `--force-resume`.
4. Without this, Task Scheduler would re-fire the same goal every 45min indefinitely.

Division of labour: `halt.py` provides the sentinel/status-file/detection
primitives (tested); the driver wires them into the resume path. Secret values are
never echoed -- `secrets_scan.py` redacts to a non-reversible hash.

To investigate: read the status file at `.claude/tmp/secret-halt-*.md`.
To force-resume after manual remediation: `/personal-loop --resume <slug> --force-resume`.

## Fail-closed self-check (before arming)

`--unattended` arms an OS relauncher that runs `claude -p` with full tool authority
on a schedule -- the strongest-authority mode. Before arming, verify the safety
machinery exists and is runnable: `secrets_scan.py`, `halt.py`, and a reachable
`personal-workflow/lib/fence.py`. If any is missing, REFUSE to arm and name the
missing guard. Require BOTH `max_iters > 0` AND `token_ceiling > 0` for headless
runs (a runaway with only one cap is a budget hole).
