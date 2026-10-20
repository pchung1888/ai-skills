# Eval plan: personal-wayfinder

## Target behavior (the contract)

A manual-only planning skill. It charts a map of decision tickets on Jira (company remotes),
GitHub issues (github.com remotes) or local Markdown, and works one ticket per session. Jira
writes need the user's confirmation first. Every skill it calls is a ping-personal skill that
accepts a Skill-tool call, so it keeps working after Matt Pocock's plugin is disabled.

## Failure modes -> graders

| # | Failure | Grader |
|---|---|---|
| 1 | Frontmatter drift, non-ASCII, or it becomes model-invoked and writes tickets unasked | code: skill_frontmatter |
| 2 | The tracker rule is lost, so company work lands on GitHub or the reverse | code: tracker_choice |
| 3 | Jira writes happen without confirmation, with a guessed project key, or in casual register | code: jira_safety |
| 4 | GitHub fallbacks or the local layout go missing, or unconfirmed links get reported | code: github_and_local_ops |
| 5 | A called skill is renamed, deleted or made manual-only, or a Matt-only call survives | code: calls_our_skills |
| 6 | The one-ticket-per-session, claim-first or fog rules are edited out | code: core_discipline |

## Ship gate

eval.ps1 exits 0 AND run-all.ps1 prints ALL EVALS PASS.
