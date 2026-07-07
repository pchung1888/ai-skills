# Eval plan: personal-pr-briefing

## Target behavior (the contract)
Given a branch with an open PR/MR, the skill updates the description with a
marker-scoped reviewer briefing (read-first list capped at 3, skim-eligible
tags, the one question) built from the DIFF, not commit messages. It must NOT
touch text outside the markers, open PRs, or merge/approve.

## Failure modes -> graders
| # | Failure | Grader |
|---|---|---|
| 1 | Frontmatter drift | code: frontmatter check |
| 2 | Idempotency markers lost -> duplicated sections on re-run | code: briefing_contract |
| 3 | One forge dropped (gh or glab) | code: briefing_contract |
| 4 | Independence rule lost -> briefing paraphrases author's writeup | code: briefing_contract |
| 5 | Scope creep into merge/approve | code: briefing_contract boundary check |
| 6 | Grader goes dead | code: calibration (copy without end marker must FAIL) |

## Eval cases
- Baseline green; calibration mutation fails.
- Judge (deferred): briefing quality (are the 3 files really load-bearing)
  is taste; revisit if real-use briefings disappoint.

## Ship gate
eval.ps1 exits 0 AND run-all.ps1 prints ALL EVALS PASS.
