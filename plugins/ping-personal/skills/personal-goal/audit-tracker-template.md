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
requirement_status: {{requirement_status}}
text_review_status: {{text_review_status}}
---

# Audit Tracker -- {{slug}}

## Requirement -- the owner's own words

<!-- VERBATIM. Never paraphrase, never re-word, never "clean up". Every phase in the
     Phase Status table below must cite a line of THIS section, or a decision id from
     ## Decisions, or an unblock proof from ## Detours. A phase that cites the plan,
     a findings doc, or a research pass is a PROPOSAL, not a requirement. -->

{{requirement_verbatim}}

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

## Decisions

Owner decisions. A phase may cite `DEC-<n>` in its Source cell only if that id
appears here. Written by `/personal-goal-next --decision`.

| id | Date | Decision | Why | Ruled out |
|---|---|---|---|---|

## Detours

Work that does not serve the requirement directly but unblocks it. `origin` is the
discriminator: `pre-existing` / `external` means reality blocked us -- proceed.
`phase-<n>` means an earlier phase of THIS goal created the constraint -- that is
drift, and the default remedy is to REVERT that phase's mechanism, not to build more
on top of it. `already_checked` records what existing mechanism was examined first.
Written by `/personal-goal-next --detour-open` / `--detour-close`.

| id | Opened | Origin | Blocks | Proof | Already checked | Status |
|---|---|---|---|---|---|---|

## Subagent Token Cost Log

Rollup: total=0 | phases=0 | median/phase=0

| # | Phase | Subagent type | Task description | Tokens | Duration | Outcome | Notes |
|---|---|---|---|---|---|---|---|

## Agent Activity Log

| Timestamp | Phase | Outcome | Commit |
|---|---|---|---|

## Phase Status

Source column legal values (enforced by `advance.py`, exit 6):
`ASK:<quoted fragment>` | `DEC-<n>` | `UNBLOCK:<detour id>` | `PROPOSAL` (cannot advance).

| Phase | Source | Title | Status | Commit | Subagent |
|---|---|---|---|---|---|
{{phase_rows}}

## Failure Log

| # | Phase | Subagent | What failed | Recovery action | Lesson candidate |
|---|---|---|---|---|---|

## Self-Improvement Capture

Format: - YYYY-MM-DD [phase N] <lesson> (lesson-candidate: YES/NO)
