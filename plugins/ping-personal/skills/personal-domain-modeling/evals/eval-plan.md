# Eval plan: personal-domain-modeling

## Target behavior (the contract)

An instruction-only skill that keeps `docs/glossary/GLOSSARY.md` and `docs/glossary/decisions/` current while designing.
Its two format files must exist and stay ASCII. Decision notes are offered only when all three tests
pass. Glossary updates happen inline, hold no implementation details, and are checked
against the code.

## Failure modes -> graders

| # | Failure | Grader |
|---|---|---|
| 1 | Frontmatter drift | code: skill_frontmatter |
| 2 | A format file goes missing, unlinked, or gains non-ASCII | code: format_files |
| 3 | The three decision tests are loosened, so decision notes pile up | code: decision_three_tests |
| 4 | The glossary turns into a spec or a batch job | code: glossary_discipline |
| 5 | A re-sync brings back docs/adr/ instead of docs/glossary/ | code: docs_glossary_home |

## Ship gate

eval.ps1 exits 0 AND run-all.ps1 prints ALL EVALS PASS.
