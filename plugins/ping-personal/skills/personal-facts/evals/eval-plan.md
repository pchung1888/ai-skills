# Eval plan: personal-facts

## Target behavior (the contract)
Given a fact-finding request, the skill probes read-only and produces
docs/<area>/facts/<date>-<topic>-facts.md where every claim carries one of
CONFIRMED-LIVE / EXTRACTED / INFERRED / UNKNOWN (RESOLVED for settled
discrepancies) with minimum provenance. It must NOT mutate state or emit
unlabeled claims.

## Failure modes -> graders
| # | Failure | Grader |
|---|---|---|
| 1 | Frontmatter drift | code: frontmatter check |
| 2 | A label drops from the taxonomy (downstream docs break) | code: label_taxonomy |
| 3 | Output path/suffix convention lost | code: output_contract |
| 4 | No-unlabeled-claims or 3x-worse honesty rule lost | code: output_contract |
| 5 | Read-only probe boundary lost | code: output_contract |
| 6 | Grader goes dead | code: calibration (copy without RESOLVED must FAIL) |

## Eval cases
- Baseline green; calibration mutation fails.
- Judge (deferred): whether produced facts docs are actually decision-grade
  is judged in use, per-doc, not here.

## Ship gate
eval.ps1 exits 0 AND run-all.ps1 prints ALL EVALS PASS.
