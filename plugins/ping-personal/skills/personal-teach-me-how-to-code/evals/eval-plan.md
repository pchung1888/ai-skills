# Eval plan - personal-teach-me-how-to-code

Run: `pwsh -NoProfile -File evals/eval.ps1` (also discovered by `evals/run-all.ps1`).

## Baseline failures (RED, observed in a real teaching session without this skill)

| Failure | What happened | Guard |
|---|---|---|
| Skipped section | The teacher went from step 8a to 9a and left out 8b (the URL and load logic). | `check_plan.py` fails a plan with a line gap. Test `test_skipped_section_fails_and_names_the_gap`. Red flags table in SKILL.md. |
| Two steps in one reply | A reply mixed the end of one file and the start of the next. | `step_shape` grades fixtures with the personal-copilot-talk grader. `bad-two-steps.md` must fail. |
| Too much talk | The user had to type a lot to learn. | Page mode is the default and builds the walk page with checks inside it. Contract keywords `Page mode (default)`. |
| Lost findings | Findings and the user's decisions lived only in chat. | Contract keywords `Do not duplicate it`, `dated decisions`, and `references/findings-notes.md`. |
| Guessed code | A claim about code without reading the line. | Contract keyword `EXTRACTED, INFERRED or UNKNOWN`. |

## Checks

| Check | Fails when |
|---|---|
| `skill_frontmatter` | The name or description is wrong, the file has non-ASCII bytes, or the description takes the wizard trigger. |
| `references` | A reference file is unlinked, missing or non-ASCII. |
| `reuse` | A reused script or skill moved, or SKILL.md stopped naming it. |
| `skill_contract` | A rule from the real lesson was dropped from SKILL.md. |
| `plan_check` | `check_plan.py` stops catching a gap, a missing file or a range past the end. |
| `step_shape` | The good step fixture breaks the copilot-talk shape, or the bad one passes. |

## Mutation check

Delete the gap loop in `check_plan.py`: `plan_check` must turn red. Restore it.
