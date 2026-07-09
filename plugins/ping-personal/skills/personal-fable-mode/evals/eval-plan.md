# Eval plan: personal-fable-mode

Failure-mode map for the deterministic grader in eval.ps1. The skill is a
method skill (behavior-shaping, no file output), so the graders protect the
parts that make it load and bind correctly, not a data contract.

## What breaks this skill

| # | Failure mode | Why it matters | Grader |
|---|---|---|---|
| 1 | Frontmatter name drifts or description lost | Skill stops resolving as /personal-fable-mode; description is the only trigger surface | skill_frontmatter |
| 2 | "fable mode" trigger phrase dropped from description | The activation phrase Ping actually says stops routing here | skill_frontmatter |
| 3 | model key changed away from inherit | The whole point is upgrading the RUNNING model; a fixed model tier silently defeats it (e.g. fable-mode forcing sonnet) | model_inherit |
| 4 | A gate renamed or deleted | The five-gate loop is the spine; smells table and ecosystem notes reference gates by name and number | five_gates |
| 5 | Contract lines edited out (verification layer rule, Honesty Protocol labels, smells section, effort dial) | These are the load-bearing behaviors the skill exists to transfer | contract_lines |
| 6 | Non-ASCII sneaks in (em-dash, smart quotes, unicode arrows) | User-scope CLAUDE.md hard rule; PS 5.1 cp1252 fallback turns em-dashes into parser poison in downstream copies | ascii_purity |
| 7 | Dead-metric grader (mutation passes) | A grader that cannot fail is not a grader | calibration_* |

## What is deliberately NOT graded here

Behavioral delta on live models. A 2026-07-08 RED/GREEN pass showed the
no-skill baseline in THIS environment already passes honesty traps (missing
config.json, dirty CSV) because the user-scope CLAUDE.md Honesty Protocol
covers them; the skill's marginal value is the process gates on multi-step
work, which a cheap deterministic eval cannot measure. Compliance (a sonnet
subagent reads the skill and reports per-gate) was verified manually at
authoring time. Re-run that manual check after any structural rewrite.
