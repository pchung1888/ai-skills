# Eval plan: personal-rea

Failure-mode map for the deterministic grader in eval.ps1. The skill is a thin
router over the REA MCP server and its own `reverse-engineer-anything` skill, so
the graders protect what makes it load, stay safe and stay honest.

## What breaks this skill

| # | Failure mode | Why it matters | Grader |
|---|---|---|---|
| 1 | Frontmatter name drifts or trigger phrases lost | Skill stops resolving as /personal-rea or on "use rea" | skill_frontmatter |
| 2 | model key changed away from inherit | Reverse engineering needs the strongest running model | model_inherit |
| 3 | Authorization step deleted | Skill would analyze client or commercial binaries without asking | safety_lines |
| 4 | "ask before runtime capture" deleted | Runtime capture runs the target with the user's permissions | safety_lines |
| 5 | Routing table copied in instead of delegated | Goes stale on every REA release | delegates_routing |
| 6 | Honesty labels dropped from the report format | Decompiled guesses get reported as fact | report_labels |
| 7 | Non-ASCII sneaks in | User-scope CLAUDE.md hard rule | ascii_purity |
| 8 | Dead-metric grader | A grader that cannot fail is not a grader | calibration_* |

## What is deliberately NOT graded here

Live REA calls. They need the MCP server, a target and minutes of runtime; a
smoke run of `analyze-javascript-application` was checked by hand at authoring time.
