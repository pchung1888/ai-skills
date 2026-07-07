---
goal_slug: blocked-example
accept_cmd: pwsh -NoProfile -Command "Write-Host 'ALL EVALS PASS'"
accept_match: ALL EVALS PASS
accept_shell: pwsh
---

## Last Known Good Checkpoint

| Field | Value |
|---|---|
| Last completed phase | Phase 1 - Data migration |
| Last successful commit | def002 |
| Next action | Investigate blocked phase 2 then re-dispatch |

## Phase Status

| Phase | Source | Title | Status | Commit | Subagent |
|---|---|---|---|---|---|
| 1 | conductor | Data migration | OK Done | def002 | driver |
| 2 | conductor | Integration wiring | BLOCKED Blocked | -- | driver |
| 3 | conductor | Final validation | ⬜ Pending | -- | -- |

## Subagent Token Cost Log

| # | Phase | Subagent | Task | Tokens | Duration | Outcome | Notes |
|---|---|---|---|---|---|---|---|
| 1 | 1 | driver | phase work | 9500 | 6 | PASS | - |
| 2 | 2 | driver | phase work | 18000 | 12 | BLOCKED | dep not deployed |

## Agent Activity Log

| Timestamp | Phase | Outcome | Commit |
|---|---|---|---|
| 10:00 | 1 | PASS | def002 |
| 11:30 | 2 | BLOCKED | -- |

## Failure Log

| # | Phase | Subagent | What failed | Recovery | Lesson candidate |
|---|---|---|---|---|---|
| 1 | 2 | driver | dep not deployed -- service unavailable | Deploy dep first then re-dispatch phase 2 | Verify infra prereqs before dispatching |
