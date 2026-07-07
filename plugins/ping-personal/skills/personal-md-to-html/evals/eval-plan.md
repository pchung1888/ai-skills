# Eval Plan: personal-md-to-html

> Follows the agent-evals-playbook. Mirrors the approved shape from
> `personal-htsw/evals/`. This skill already ships a smoke harness
> (`tests/smoke.py`: validator self-test + golden render-diff + 6 negative tests);
> this eval **wraps** that harness and adds frontmatter + script-presence checks.
> It is a "taste-heavy" skill, so it also has a `judge-rubric.md` (added in Phase 4).

## Target Behavior

Given one Markdown file, personal-md-to-html renders a single **self-contained**
styled HTML "magazine spread" in the arc theme (cream paper, brick-orange accent,
serif headlines, timeline rails, inline SVG). The render is deterministic: the same
input must produce byte-stable canonical HTML (golden render-diff against
`examples/claire-arc.html`). `md-to-html-check.py` validates output structure.

## Failure Modes

| ID | Failure | Why It Matters | Grader |
| --- | --- | --- | --- |
| F01 | renderer output drifts from the golden (render-diff non-empty) | silent visual/structure regression | code (smoke) |
| F02 | validator stops rejecting malformed HTML (negative tests pass-through) | grader regresses to measuring nothing | code (smoke) |
| F03 | output is not self-contained (external CSS/JS/image refs) | page breaks when shared / opened offline | code (smoke) |
| F04 | a load-bearing script (renderer or validator) goes missing | the skill cannot run | code |
| F05 | frontmatter name/description corrupted | skill stops triggering | code |
| F06 | output is structurally valid but visually ugly / cluttered | passes code, still bad to read | judge (Phase 4) |

## Eval Cases

| ID | Input | Expected Behavior | Must Not Happen |
| --- | --- | --- | --- |
| E01 | `tests/smoke.py` full suite | validator self-test + render-diff + 6 negatives all pass, exit 0 | any smoke layer red |
| E02 | `SKILL.md` frontmatter | name=personal-md-to-html + description present | name/desc corruption |
| E03 | skill root | md-to-html.py + md-to-html-check.py both present | a load-bearing script deleted |

## Graders

### Code Graders (`eval.ps1`)

- `skill_frontmatter`: SKILL.md declares name=personal-md-to-html + a description.
- `scripts_present`: md-to-html.py and md-to-html-check.py exist.
- `smoke_suite_passes`: runs `python tests/smoke.py`; requires exit 0 (the bulk
  grader -- validator self-test, golden render-diff, 6 negative tests).

### Model Judge (`judge-rubric.md`, added Phase 4)

- `visual_quality`: is the rendered spread readable, uncluttered, and on-theme?
  (F06 -- the taste code cannot measure.)

## Baseline Run

- date: 2026-05-31
- agent version: personal-md-to-html @ plugin 0.5.0
- result summary: `eval.ps1` -> frontmatter + scripts present + tests/smoke.py exit 0.

## Ship Gate

- `eval.ps1` exits 0 (requires the wrapped smoke suite, incl. golden render-diff, green).
- A non-empty render-diff (F01) blocks ship -- the golden is the locked regression case.
