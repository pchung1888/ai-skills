# Eval Plan: personal-progress

> Follows the agent-evals-playbook. Mirrors the approved shape from `personal-htsw/evals/`.
> Instruction-only skill (no scripts), so the grader checks STRUCTURE: the documented
> capture steps, the progress-vs-handoff distinction, the output path, and templates.

## Target Behavior

personal-progress captures session state as a structured handoff document at
`docs/progress/YYYY-MM-DD-<task>-progress.md` (and, when open decisions exist, a sibling
`-handoff.md`). Progress = WHAT happened; Handoff = WHAT NEXT-YOU NEEDS TO DECIDE. It fires
preparatively when a limit approaches or the user signals an imminent stop.

## Failure Modes

| ID | Failure | Why It Matters | Grader |
| --- | --- | --- | --- |
| F01 | frontmatter name/description corrupted | skill stops triggering | code |
| F02 | the output path `docs/progress/` no longer documented | handoffs land in the wrong place / are lost | code |
| F03 | the progress-vs-handoff distinction removed | the two artifacts collapse; "what next" is lost | code |
| F04 | a required step (Gather / Write Progress / Sibling Handoff / Safety Rules) deleted | the capture procedure breaks | code |
| F05 | the templates/ directory missing | the skill has no scaffold to render from | code |

## Eval Cases

| ID | Input | Expected Behavior | Must Not Happen |
| --- | --- | --- | --- |
| E01 | SKILL.md frontmatter | name=personal-progress + description present | name/desc corruption |
| E02 | SKILL.md body | references `docs/progress/` AND documents progress-vs-handoff | path/contract drift |
| E03 | SKILL.md headings | Step 0 / Step 2 Write Progress / Step 2.5 Sibling Handoff / Safety Rules present | a step dropped |
| E04 | skill dir | `templates/` directory exists | scaffold missing (F05) |

## Graders

### Code Graders (`eval.ps1`)

- `skill_frontmatter`: name=personal-progress + a description.
- `output_path_documented`: body references `docs/progress/`.
- `progress_vs_handoff_documented`: both "progress" and "handoff" appear, with the
  WHAT-happened vs WHAT-next distinction.
- `required_sections`: Step 0 / Step 2 Write Progress / Step 2.5 Sibling Handoff / Safety Rules.
- `templates_present`: the `templates/` directory exists.

### Model Judge

- None. The capture contract is structural and deterministic; code only.

## Ship Gate

- `eval.ps1` exits 0. F02/F03 (output path or progress-vs-handoff distinction lost) are
  highest severity -- they defeat the crash-recovery purpose of the skill.
