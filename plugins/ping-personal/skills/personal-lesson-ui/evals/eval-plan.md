# Eval Plan: personal-lesson-ui

> Follows the agent-evals-playbook. Mirrors the approved shape from `personal-htsw/evals/`.
> Instruction-only skill (no scripts), so the grader checks STRUCTURE: that the skill's
> documented capture/append/browse contract and its seed lessons are intact.

## Target Behavior

personal-lesson-ui captures UI / frontend lessons (React, Next.js, TypeScript TSX, CSS,
layout, hydration, app router). Invoked by the personal-lesson master router (or directly),
it runs a hard-rule gate, a duplicate check, then APPENDS to
`~/.claude/lessons/personal-lesson-ui.md`. Browse mode reads from there plus the seed
lessons embedded in this SKILL.md.

## Failure Modes

| ID | Failure | Why It Matters | Grader |
| --- | --- | --- | --- |
| F01 | frontmatter name/description corrupted | skill stops triggering / the router can't dispatch to it | code |
| F02 | append-target path stops matching the skill name | captured lessons silently go to the wrong file or are lost | code |
| F03 | a required section (Capture flow / Append / Browse / Seed) deleted | the capture or browse contract breaks | code |
| F04 | all seed lessons wiped | the skill loses its accumulated cross-project knowledge | code |

## Eval Cases

| ID | Input | Expected Behavior | Must Not Happen |
| --- | --- | --- | --- |
| E01 | SKILL.md frontmatter | name=personal-lesson-ui + description present | name/desc corruption (F01) |
| E02 | SKILL.md body | references `~/.claude/lessons/personal-lesson-ui.md` | append-target drift (F02) |
| E03 | SKILL.md headings | Capture flow / Step 2 Append / Browse mode / Seed Lessons all present | a section dropped (F03) |
| E04 | SKILL.md | at least one severity-tagged seed lesson (NEVER/CAUTION/NOTE/...) | seeds wiped (F04) |

## Graders

### Code Graders (`eval.ps1`)

- `skill_frontmatter`: name=personal-lesson-ui + a description.
- `append_target_matches_name`: body references `~/.claude/lessons/personal-lesson-ui.md`.
- `required_sections`: Capture flow / Step 2 Append / Browse mode / Seed Lessons present.
- `has_seed_lesson`: at least one `## <SEVERITY> ...` seed lesson exists.

### Model Judge

- None. Structural integrity is deterministic; the quality of a captured lesson is the human
  author's responsibility, not something this skill generates.

## Ship Gate

- `eval.ps1` exits 0. F02 (append-target drift) is the highest-severity failure.
