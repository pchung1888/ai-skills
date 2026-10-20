# Eval plan: personal-grill-me

## Target behavior (the contract)

The skill keeps its core rules as listed below, stays model-invocable so its aliases can
forward to it, and stays ASCII.

## Failure modes -> graders

| # | Failure | Grader |
|---|---|---|
| 1 | Frontmatter drift, or it becomes manual-only and breaks its aliases | code: skill_frontmatter |
| 2 | design tree, frontier rounds, a recommended answer each, yes accepts it is edited out | code: interview_rules |
| 3 | look facts up yourself, put decisions to the user, confirm before acting is edited out | code: facts_vs_decisions |
| 4 | options named by what they do, speech-to-text check is edited out | code: ping_rules |
| 5 | with docs runs personal-domain-modeling into docs/glossary/ is edited out | code: with_docs_mode |

## Ship gate

eval.ps1 exits 0 AND run-all.ps1 prints ALL EVALS PASS.
