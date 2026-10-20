# Eval plan: personal-teach

## Target behavior (the contract)

A manual-only, stateful teaching skill. It keeps a learning workspace (mission, resources,
glossary, learning records, lessons, reference pages) outside any code repo. Lessons are
Markdown rendered with personal-md-to-html, tied to the mission, sourced, and end with
retrieval practice.

## Failure modes -> graders

| # | Failure | Grader |
|---|---|---|
| 1 | Frontmatter drift, or the skill becomes model-invoked and starts workspaces unasked | code: skill_frontmatter |
| 2 | A format file goes missing, unlinked, or gains non-ASCII | code: format_files |
| 3 | Lessons get written into a code repo such as the main product repo | code: never_in_a_code_repo |
| 4 | The md-to-html path breaks, so lessons stop rendering | code: lessons_render_with_md_to_html |
| 5 | The learning-science rules (mission, retrieval, sources) are edited out | code: learning_science |

## Ship gate

eval.ps1 exits 0 AND run-all.ps1 prints ALL EVALS PASS.
