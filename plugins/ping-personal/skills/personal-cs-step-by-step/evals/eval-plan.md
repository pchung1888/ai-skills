# Eval plan: personal-cs-step-by-step

## Target behavior (the contract)

SKILL.md declares the right frontmatter name, calls
`personal-cs-client-question` internally rather than duplicating its
location logic, and its documented metric-JSON shape uses field names that
actually exist in `cs-metric-schema.json` -- so a metric line this skill
emits will pass schema validation.

## Failure modes -> graders

| # | Failure | Grader |
|---|---|---|
| 1 | Frontmatter drift | code: frontmatter check |
| 2 | Skill stops delegating to personal-cs-client-question (duplicated logic) | code: referential_integrity |
| 3 | Documented metric field names drift from the shared schema | code: metric_shape_matches_schema |

## Eval cases

Static checks against SKILL.md text and the sibling schema file -- no
runtime fixtures needed (this skill has no bundled script).

## Ship gate

eval.ps1 exits 0 AND run-all.ps1 prints ALL EVALS PASS.
