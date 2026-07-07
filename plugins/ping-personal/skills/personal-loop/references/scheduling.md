# Scheduling guide -- /personal-loop cadence

## Which primitive to use

| TRIGGER | Primitive | Notes |
|---|---|---|
| `on-demand` (default) | inline turn-by-turn loop | runs in current session; Esc stops it |
| `every <interval>` | built-in `/loop <interval>` | **default cadence**; fires while session open + idle |
| dynamic interval | `ScheduleWakeup` | model picks 60s-3600s; max 1h per wakeup |
| `--unattended` / "while I sleep" | Windows Task Scheduler + `claude -p` | only shape that auto-resumes across a 5h reset |

## Two separate problems

**Problem 1 -- not losing work when session dies at the 5h wall.**
SOLVED by the beacon. Every phase is git-committed. Any fresh start reads
the beacon and resumes from the last committed checkpoint.

**Problem 2 -- auto-restarting after the 5h window RESETS, while away.**
NOT automatic with `/loop` (verified; GitHub issue #36320 is an open feature
request as of 2026-06-16). The restart trigger must live where quota cannot
block it: the operating system.

## Verified platform facts (2026-06-16)

| Fact | Label |
|---|---|
| `/loop` fires only while Claude session is open + idle | EXTRACTED (scheduled-tasks docs) |
| `/loop` has no "wait for quota reset and continue" -- open feature request #36320 | EXTRACTED |
| Cloud routines share the same 5h quota pool; rejected when exhausted | EXTRACTED (routines docs) |
| Cloud routines have NO local file access (fresh clone each run) | EXTRACTED |
| `claude -p` may draw from a separate Agent SDK credit pool (June 15 2026 billing change) | INFERRED -- VERIFY on your plan before relying on it |

## The hybrid design

- DEFAULT: `/loop` for attended, within-window runs.
- OPT-IN (`--unattended`): Windows Task Scheduler relauncher (see unattended-setup.md).
