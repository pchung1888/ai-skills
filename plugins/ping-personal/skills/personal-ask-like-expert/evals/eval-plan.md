# Eval plan: personal-ask-like-expert

## Target behavior (the contract)

Given a question from someone new to a field, the skill answers the four expert questions,
glosses the field terms, and returns one pasteable prompt that is deeper, not bigger. It logs
The user's rating to a retro log and has an improve mode that reads that log.

## Failure modes -> graders

| # | Failure | Grader |
|---|---|---|
| 1 | Frontmatter drift or non-ASCII bytes | code: skill_frontmatter |
| 2 | One of the four expert questions is edited out | code: four_questions |
| 3 | The "deeper, not bigger" rule is lost (scope creep) | code: deeper_not_bigger |
| 4 | Retro log or improve mode is lost (no way to learn from use) | code: retro_loop |
| 5 | Honesty labels are lost, so guessed methods read as fact | code: honesty_labels |
| 6 | Rubric or fixtures go missing, so the metric cannot run | code: metric_files |
| 7 | The rewrite is not actually better | judge: judge-rubric.md, mean total over fixtures/questions.md |

## Ship gate

eval.ps1 exits 0 AND run-all.ps1 prints ALL EVALS PASS. The judge metric runs on demand, not
in run-all, because it needs a model.
