# Eval plan: personal-unslop

## Target behavior (the contract)

SKILL.md is a rewrite checklist the model may invoke on its own
(`disable-model-invocation: false`). It must keep the upstream rule ids
(other skills cite them by number), stay pure ASCII, and keep the local rule 13:
em and en dashes are banned, a spaced ASCII hyphen (" - " or " -- ") is allowed
and must not be rewritten away.

## Failure modes -> graders

| # | Failure | Grader |
|---|---|---|
| 1 | Frontmatter drift (name, description, model-invocable flag) | code: skill_frontmatter |
| 2 | Non-ASCII byte lands in SKILL.md (upstream used a Unicode arrow) | code: ascii_only |
| 3 | A re-sync from upstream restores the "no hyphen-as-dash" wording | code: rule13_allows_spaced_hyphen |
| 4 | A rule id is renumbered, dropped, or a retired gap is reused | code: rule_ids_stable |

## Eval cases

No fixtures. Every grader reads SKILL.md directly.

## Ship gate

eval.ps1 exits 0 AND run-all.ps1 prints ALL EVALS PASS.
