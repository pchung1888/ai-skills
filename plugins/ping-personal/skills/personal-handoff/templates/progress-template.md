# [Task Name] Progress -- Handoff File

**Branch:** `<branch-name>`
**Plan:** `docs/plans/<plan-file>.md`
**Issue:** `<ticket-id>` (Jira / GitHub Issue / etc.)
**Last updated:** YYYY-MM-DD | **PR/MR:** `<repo>#<N>` -> `<target-branch>`

---

## Status Summary

| Task | Title | Status |
|---|---|---|
| Task 0 | [description] | `[done]` Complete (commit `<hash>`) |
| Task 1 | [description] | `[wip]` In Progress -- stopped at Step N |
| Task 2 | [description] | `[todo]` Not started |

---

## Blocker / Stopping Reason

[Why we are stopping: context limit hit / end of session / blocked on X]

---

## Quota at Handoff

Real usage when this handoff was written (from `personal-quota/quota.ps1 -Json`; write
`UNKNOWN` if the sensor could not read it -- never guess a number):

| Meter | Used | Resets |
|---|---|---|
| 5h session | `<N>%` | `<local time>` |
| Weekly | `<N>%` | `<local time>` |
| Context | `<N>%` | -- |

- **Band:** `<PROCEED / CONSERVE / LIGHT_ONLY / STOP>` (from `plan.ps1`).
- **Deferred work + resume:** `<task>` deferred until `<deferUntil>`; wake via
  `<schedulewakeup | task-scheduler>`. Omit this line if nothing was deferred.

---

## The ask (verbatim)

> [The owner's own words. Copy from the beacon's `## Requirement` section, or from
>  what they actually said. Never paraphrase -- next-session will plan against
>  whatever is written here, so a summary becomes the new requirement.]

---

## What I am unsure about

REQUIRED -- do not delete this section, and do not write "nothing".

A handoff that carries only conclusions hands the next session maximum confidence
and minimum context, which is backwards. Doubts are exactly what does not survive a
handoff document unless they are written down on purpose.

- **Least confident claim:** [what I asserted that I would check first if I were starting fresh]
- **What I would challenge:** [the load-bearing assumption in this work that deserves a second look]
- **What I did not verify:** [claims made from reading rather than running]
- **Where I might be wrong about scope:** [anything I built that the ask above may not actually cover]

---

## Open detours

Work opened to unblock the goal that has not closed yet. Copy from the beacon's
`## Detours` table. If there are none, write "none".

| id | Origin | Blocks | Proof | Resume at |
|---|---|---|---|---|
| DET-n | pre-existing / external / phase-N | phase N | [failing test or error] | phase N |

**If any row's Origin is `phase-N`,** an earlier phase of this goal created that
blocker. That is drift, not a detour, and the remedy is to revert that phase's
mechanism rather than build further on it. Say so here explicitly.

---

## Next Steps (resume here)

1. [Exact next action -- file, command, or step from plan]
2. [Second action]
3. [Third action if known]

---

## Key Findings

[Critical facts discovered this session that the next session MUST know before touching any code]

### [Subsection if needed -- e.g., "Function Signatures", "Page State"]

- Fact 1 (source: `path/to/file.ext:line`)
- Fact 2

---

## Environment State

| Item | State |
|---|---|
| Runtime / server | Restarted / Not restarted / N/A |
| DB migrations | Applied / Pending / N/A |
| Last test result | PASS / FAIL / Not run |
| Uncommitted changes | None / List files |

---

## Provenance

- **Source tier:** <what this doc was generated from -- e.g. live git state + plan file + this session's tool output>
- **Freshness:** Generated YYYY-MM-DD | reflects `<branch-name>` @ commit `<hash>`
- **Read-back:** <who confirmed the verbatim ask and open-detour proofs are safe to
  commit, and when -- or `not reviewed: <why>`. This file lands in docs/progress/,
  which is tracked in some host repos.>
- **Trust:** Factual claims follow the Honesty Protocol -- `EXTRACTED` = observed in code/tool output, `INFERRED` = reasoned from context.
