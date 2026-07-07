# Eval plan: personal-cs-escalate-to-dev

## Target behavior (the contract)

SKILL.md declares the right frontmatter name, documents both automatic
triggers (low-confidence and DB-touch), never instructs composing a direct
answer to the escalated question, and its documented metric-JSON field
names exist in the shared `cs-metric-schema.json` (or are declared
skill-only extension fields).

## Failure modes -> graders

| # | Failure | Grader |
|---|---|---|
| 1 | Frontmatter drift | code: frontmatter check |
| 2 | Trigger B (DB-touch) rule silently dropped during a future edit | code: db_touch_rule_present |
| 3 | "DO NOT answer directly" anti-pattern silently dropped | code: no_direct_answer_rule |
| 4 | Documented metric field names drift from the shared schema | code: metric_shape_matches_schema |

## Eval cases

Static checks against SKILL.md text and the sibling schema file -- no
runtime fixtures needed (this skill has no bundled script).

## Ship gate

eval.ps1 exits 0 AND run-all.ps1 prints ALL EVALS PASS.
