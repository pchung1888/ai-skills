# Eval plan: personal-critic-judge

## Target behavior (the contract)

Five reviewers return findings only. One judge rules on every finding: real, in scope, when, and
why, measured against the Main goal and the Subtask. The driver fixes only "fix now" rows. A
safety-floor finding is never ruled "never". The run stops and asks if the Main goal or the
Subtask is missing.

## Failure modes -> graders

| # | Failure | Grader |
|---|---|---|
| 1 | Frontmatter drift, or the description takes personal-critic-gate's triggers | code: skill_frontmatter |
| 2 | A rule is edited out of SKILL.md (inputs, seats, judge rules, floor, verify pass) | code: skill_contract |
| 3 | A judge table breaks the shape or the rules | code: calibration and table_rules (fixtures/) |
| 4 | No VERDICT line, or its counts do not match the table | code: table_rules (bad-verdict-missing, bad-verdict-count) |
| 5 | Explanations in the Real or In scope cells, or a pipe inside a cell | code: table_rules (bad-real-cell-text, bad-pipe-in-cell) |
| 6 | A fix-now or flagged row the judge did not re-read (no EXTRACTED, no UNKNOWN) | code: table_rules (bad-fixnow-not-reread) |

## Grading a real judge table

`pwsh eval.ps1 -TableFile <table.md>` checks one table a judge returned.

## Not covered by code

Whether the judge's calls are right. The user's side-by-side run against personal-critic-gate on
finished host-app work is the acceptance test (design roadmap step 1).

## Ship gate

eval.ps1 exits 0 AND run-all.ps1 prints ALL EVALS PASS.
