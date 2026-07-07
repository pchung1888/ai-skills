# Eval plan: personal-jira-sync

## Target behavior (the contract)
Given an issue key (or a branch that implies one), the skill syncs shipped
work onto the Jira ticket via Atlassian MCP (description section, comment,
subtask split) with evidence-traceable claims, degrading to a PASTE-READY
block when the MCP is absent. It must NOT transition status, clobber the
description, or put unverified claims on a client-visible ticket.

## Failure modes -> graders
| # | Failure | Grader |
|---|---|---|
| 1 | Frontmatter drift | code: frontmatter check |
| 2 | Status-transition ban lost | code: sync_contract |
| 3 | Degraded (no-MCP) mode lost -> skill useless offline | code: sync_contract |
| 4 | MCP preflight tool names lost | code: sync_contract |
| 5 | Description-preservation / honesty rules lost | code: sync_contract |
| 6 | Grader goes dead | code: calibration (copy without transition ban must FAIL) |

## Eval cases
- Baseline green; calibration mutation fails.
- Live MCP behavior is untestable headlessly (interactive auth); accepted
  blind spot, covered by the degraded-mode contract.

## Ship gate
eval.ps1 exits 0 AND run-all.ps1 prints ALL EVALS PASS.
