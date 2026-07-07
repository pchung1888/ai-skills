# Eval plan: personal-cs-client-question

## Target behavior (the contract)

`cs-metric-write.ps1` atomically writes a metric row + markdown sidecar,
validates against `cs-metric-schema.json`, enforces the cross-field rules
(suggestion required unless escalated, dev_concern required when INFERRED),
rejects unresolved `{{...}}` placeholders, ignores caller-supplied
`host_override`, and GCs orphan sidecar files. SKILL.md's frontmatter and
schema/skill-name references must stay in sync with the schema file's enum.

## Failure modes -> graders

| # | Failure | Grader |
|---|---|---|
| 1 | Frontmatter drift | code: frontmatter check |
| 2 | Referenced files missing on disk | code: referential_integrity |
| 3 | Wrapper writes a row that fails schema validation | code: schema_valid_row |
| 4 | Missing `suggestion` on a non-escalated row is silently accepted | code: reject_missing_suggestion |
| 5 | Missing `dev_concern` on an INFERRED row is silently accepted | code: reject_missing_dev_concern |
| 6 | Unresolved `{{...}}` placeholder ships in the sidecar | code: reject_unresolved_placeholder |
| 7 | `cs-metric-schema.json` skill enum drifts from the 3 shipped skill names | code: schema_enum_matches_skills |

## Eval cases

No external fixtures needed -- each test drives `cs-metric-write.ps1`
directly with `CS_METRIC_ROOT_OVERRIDE` pointed at a temp dir, then cleans
up.

## Ship gate

eval.ps1 exits 0 AND run-all.ps1 prints ALL EVALS PASS.
