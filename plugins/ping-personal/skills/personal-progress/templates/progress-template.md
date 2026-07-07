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
- **Trust:** Factual claims follow the Honesty Protocol -- `EXTRACTED` = observed in code/tool output, `INFERRED` = reasoned from context.
