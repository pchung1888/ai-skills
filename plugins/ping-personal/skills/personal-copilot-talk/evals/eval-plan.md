# Eval plan: personal-copilot-talk

## Target behavior (the contract)

While the mode is on, each reply walks the user through one step on a box the agent cannot reach.
The reply is a stack of bold-headed blocks split by `---` lines. It holds one step and ends
with a "Tell me:" block. Sentences have 20 words or fewer. There are no markdown `#`
headings, no Insight block, no mechanism section and no TL;DR. Everything is ASCII.

## Failure modes -> graders

| # | Failure | Grader |
|---|---|---|
| 1 | Frontmatter drift, or the description takes "walk me through" from personal-wizard | code: skill_frontmatter |
| 2 | A talking-style rule is edited out of SKILL.md | code: skill_contract |
| 3 | The grader rejects a good reply or accepts a bad one | code: calibration (fixtures/good-*.md, fixtures/bad-*.md) |
| 4 | A grader rule is dead and never fires | code: grader_live (one mutant per rule, matched to its message) |

## Grading a live reply

`pwsh eval.ps1 -ReplyFile <reply.md>` grades one saved reply with the shape rules.

## Ship gate

eval.ps1 exits 0 AND run-all.ps1 prints ALL EVALS PASS.
