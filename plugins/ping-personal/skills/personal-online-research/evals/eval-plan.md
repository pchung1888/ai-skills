# Eval plan: personal-online-research

## Target behavior (the contract)

Given a web-research request, the skill routes to the cheapest sufficient mode
(lookup / brief / storm), fetches via the firecrawl CLI (degrading to
WebSearch/WebFetch with disclosure), labels every claim, and for storm mode
runs the mandatory citation-verification phase with a truthful banner. Subagent
fan-outs are confirmed against the Process Budget rules before dispatch.

## Failure modes -> graders

| # | Failure | Grader |
|---|---|---|
| 1 | Frontmatter drift / trigger phrases lost | skill_frontmatter |
| 2 | A mode disappears (routing table breaks; storm silently becomes the default) | three_modes |
| 3 | firecrawl fetch conventions lost (unquoted URLs, re-scrape waste, whole-file reads) | fetch_contract |
| 4 | Verification contract lost (banner, UNVERIFIED handling, labels, fable-mode anchor) | verification_contract |
| 5 | Budget confirm before fan-out lost (storm dispatches 10 agents unasked) | budget_gate |
| 6 | Non-ASCII sneaks in | ascii_purity |
| 7 | Grader goes dead | calibration_* |

## What is deliberately NOT graded here

Live research quality (did a real storm run produce a good report) -- that is
judged per-deliverable in use, like personal-facts-check docs. The graders
protect the contract text the runtime behavior hangs from.

## Ship gate

eval.ps1 exits 0 AND run-all.ps1 prints ALL EVALS PASS.
