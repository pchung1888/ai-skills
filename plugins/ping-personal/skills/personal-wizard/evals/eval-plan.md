# Eval plan: personal-wizard

## Target behavior (the contract)

SKILL.md tells the agent to scope a manual procedure and write its stages into a copy of
`template.ps1`. The template's library must parse, stay ASCII for Windows PowerShell 5.1, and
save captured values without duplicating keys. The shared-server rule (back up, approval,
confirm before overwrite) must stay in the skill.

## Failure modes -> graders

| # | Failure | Grader |
|---|---|---|
| 1 | Frontmatter drift or the template goes missing | code: skill_frontmatter |
| 2 | A non-ASCII character or a syntax error lands in the template | code: template_ascii_and_parses |
| 3 | A library helper the skill documents is renamed or deleted | code: template_library_intact |
| 4 | Save-Value appends a second line for the same key | code: save_value_upserts |
| 5 | The shared-server safety rules are edited out | code: shared_server_rule |

## Ship gate

eval.ps1 exits 0 AND run-all.ps1 prints ALL EVALS PASS.
