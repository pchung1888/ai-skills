---
goal_slug: {{slug}}
goal_owner: {{owner}}
started: {{timestamp_est}}
branch: {{branch}}
spec_path: {{spec_path}}
plan_path: {{plan_path}}
accept_cmd: {{accept_cmd}}
accept_shell: {{accept_shell}}
accept_match: {{accept_match}}
accept_regex: {{accept_regex}}
accept_status: {{accept_status}}
accept_reason: {{accept_reason}}
phase_1_mode: {{phase_1_mode}}
phase_2plus_mode: {{phase_2plus_mode}}
auto_mode_triggers: {{auto_mode_triggers}}
max_retries: {{max_retries}}
token_budget_total: {{token_budget_total}}
vision_path: {{vision_path}}
---

# Audit Tracker -- {{slug}}

## Purpose

{{purpose_or_placeholder}}

## Last Known Good Checkpoint

| Field | Value |
|---|---|
| Last completed phase | (none yet) |
| Last successful commit | (none yet) |
| Next action | Dispatch phase 1 |
| Pending follow-ups | <status> <owner> -- <next action> |

Token budget rules: per user CLAUDE.md; log actuals in the Cost Log.

## Subagent Token Cost Log

Rollup: total=0 | phases=0 | median/phase=0

| # | Phase | Subagent type | Task description | Tokens | Duration | Outcome | Notes |
|---|---|---|---|---|---|---|---|

## Agent Activity Log

| Timestamp | Phase | Outcome | Commit |
|---|---|---|---|

## Phase Status

| Phase | Source | Title | Status | Commit | Subagent |
|---|---|---|---|---|---|
{{phase_rows}}

## Failure Log

| # | Phase | Subagent | What failed | Recovery action | Lesson candidate |
|---|---|---|---|---|---|

## Self-Improvement Capture

Format: - YYYY-MM-DD [phase N] <lesson> (lesson-candidate: YES/NO)
