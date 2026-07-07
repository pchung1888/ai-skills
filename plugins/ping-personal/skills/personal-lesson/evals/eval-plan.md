# Eval Plan: personal-lesson (master router)

> Follows the agent-evals-playbook. Mirrors the approved shape from `personal-htsw/evals/`.
> Instruction-only skill (no scripts), so the grader checks STRUCTURE + referential
> integrity: the router still documents its routing contract AND every domain skill it
> routes to actually exists on disk.

## Target Behavior

personal-lesson is the master router for lesson capture. It runs a hard-rule gate,
classifies the lesson into one of four domains, and dispatches to the matching domain
skill (personal-lesson-ui / -parser / -data / -tooling). Browse mode reads the user-scope
lesson files plus each domain skill's seed lessons.

## Failure Modes

| ID | Failure | Why It Matters | Grader |
| --- | --- | --- | --- |
| F01 | frontmatter name/description corrupted | skill stops triggering | code |
| F02 | router references a domain skill that does not exist on disk | a classified lesson is dispatched into a void | code (referential) |
| F03 | a routed domain skill dropped from the docs | that domain becomes unreachable via the router | code |
| F04 | a required section (Capture flow / Classify / Dispatch / Browse) deleted | the routing contract breaks | code |

## Eval Cases

| ID | Input | Expected Behavior | Must Not Happen |
| --- | --- | --- | --- |
| E01 | SKILL.md frontmatter | name=personal-lesson + description present | name/desc corruption (F01) |
| E02 | SKILL.md + sibling skill dirs | all 4 domain skills named AND each `<domain>/SKILL.md` exists | a phantom route (F02/F03) |
| E03 | SKILL.md headings | Capture flow / Step 1 Classify / Step 2 Dispatch / Browse mode present | a section dropped (F04) |

## Graders

### Code Graders (`eval.ps1`)

- `skill_frontmatter`: name=personal-lesson + a description.
- `routes_to_existing_domains`: for each of personal-lesson-{ui,parser,data,tooling}, the
  name is referenced in SKILL.md AND the sibling `<domain>/SKILL.md` exists on disk (F02/F03).
- `required_sections`: Capture flow / Step 1 Classify / Step 2 Dispatch / Browse mode present.

### Model Judge

- None. Routing structure + referential integrity are deterministic; code only.

## Ship Gate

- `eval.ps1` exits 0. F02 (routing to a non-existent domain skill) is the highest-severity
  failure -- a classified lesson would be dispatched into a void.
