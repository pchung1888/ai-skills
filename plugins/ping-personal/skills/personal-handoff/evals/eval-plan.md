# Eval Plan: personal-handoff

> Follows the agent-evals-playbook. Mirrors the approved shape from `personal-htsw/evals/`.
> Instruction-only skill (no scripts), so the grader checks STRUCTURE: the documented
> capture steps, the progress-vs-handoff distinction, the output path, and templates.

## Target Behavior

personal-handoff captures session state as two linked files in `docs/progress/`. The
`-handoff.md` file is always written and is the entry point: next steps, open decisions and
suggested skills. It links `-progress.md`, which holds history and facts and links back.
Progress = WHAT happened; Handoff = WHAT next. It fires preparatively when a limit
approaches or the user signals an imminent stop.

## Failure Modes

| ID | Failure | Why It Matters | Grader |
| --- | --- | --- | --- |
| F01 | frontmatter name/description corrupted | skill stops triggering | code |
| F02 | the output path `docs/progress/` no longer documented | handoffs land in the wrong place / are lost | code |
| F03 | the progress-vs-handoff distinction removed | the two artifacts collapse; "what next" is lost | code |
| F04 | a required step (Gather / Write Progress / Sibling Handoff / Safety Rules) deleted | the capture procedure breaks | code |
| F05 | the templates/ directory missing | the skill has no scaffold to render from | code |
| F06 | handoff file optional again, Next Steps back in progress, or the cross-links dropped | "read the handoff" misses the history or the next steps | code: handoff_is_entry_point |
| F07 | Suggested skills section dropped, or allowed to invent commands | the next session stops using the goal or workflow, or runs a made-up one | code: suggested_skills_rules |

## Eval Cases

| ID | Input | Expected Behavior | Must Not Happen |
| --- | --- | --- | --- |
| E01 | SKILL.md frontmatter | name=personal-handoff + description present | name/desc corruption |
| E02 | SKILL.md body | references `docs/progress/` AND documents progress-vs-handoff | path/contract drift |
| E03 | SKILL.md headings | Step 0 / Step 2 Write Progress / Step 2.5 Sibling Handoff / Safety Rules present | a step dropped |
| E04 | skill dir | `templates/` directory exists | scaffold missing (F05) |

## Graders

### Code Graders (`eval.ps1`)

- `skill_frontmatter`: name=personal-handoff + a description.
- `output_path_documented`: body references `docs/progress/`.
- `progress_vs_handoff_documented`: both "progress" and "handoff" appear, with the
  WHAT-happened vs WHAT-next distinction.
- `required_sections`: Step 0 / Step 2 Write Progress / Step 2.5 Sibling Handoff / Safety Rules.
- `templates_present`: the `templates/` directory exists.
- `unattended_flag_documented`: an `## Unattended mode` section names `--unattended` and `-audit-tracker.md`.
- `unattended_asks_no_questions`: the unattended rule says to ask no questions.
- `unattended_writes_unknown`: the unattended section writes `Unknown` for unreadable items.
- `unattended_skips_readback`: the unattended section skips the verbatim read-back.
- `unattended_never_commits`: the unattended section says never commit.
- `goal_beacon_per_bound_path`: template and SKILL.md carry `Goal beacon: <path>`, one line per bound path, deduped.

### Model Judge

- None. The capture contract is structural and deterministic; code only.

## Ship Gate

- `eval.ps1` exits 0. F02/F03 (output path or progress-vs-handoff distinction lost) are
  highest severity -- they defeat the crash-recovery purpose of the skill.
