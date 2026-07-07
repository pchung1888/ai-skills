# Eval Plan: good-skill

## Target Behavior

A healthy fixture: the skill declares its name and ships a runnable grader with a real check.

## Failure Modes

| ID | Failure | Why It Matters | Grader |
| --- | --- | --- | --- |
| F01 | frontmatter name corrupted | the skill stops triggering | code |

## Graders

### Code Graders (eval.ps1)

- frontmatter: SKILL.md declares name=good-skill.

## Ship Gate

- eval.ps1 exits 0.
