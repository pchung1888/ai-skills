# Eval plan: personal-wait-what

## Target behavior (the contract)

The skill keeps its core rules as listed below, stays model-invocable so its aliases can
forward to it, and stays ASCII.

## Failure modes -> graders

| # | Failure | Grader |
|---|---|---|
| 1 | Frontmatter drift, or it becomes manual-only and breaks its aliases | code: skill_frontmatter |
| 2 | context first, 20-word STE sentences, glossary terms, unslop, the ask last is edited out | code: repitch_rules |
| 3 | keeps every fact and adds none is edited out | code: no_new_facts |

## Ship gate

eval.ps1 exits 0 AND run-all.ps1 prints ALL EVALS PASS.
