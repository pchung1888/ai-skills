# Eval Plan: personal-create-eval

> Follows the agent-evals-playbook (see ../references/how-to-create-an-eval.md).

## Target Behavior

Given a target skill, personal-create-eval CREATEs a good eval (scaffolds + fills
`evals/eval-plan.md` + `eval.ps1` + calibration fixtures, discoverable by `run-all.ps1`) or
ENHANCEs an existing one (audits for the failure curriculum and fixes it). The LEVER is this
skill's own text + its two `lib/` scripts; the SUBJECT graded here is the skill itself: its
documented modes, its templates, and whether its two scripts actually work (scaffold produces a
valid eval; audit correctly discriminates a healthy skill from an unhealthy one). This is a
dogfood: the eval-maker has an eval, and that eval runs its own scaffold + audit scripts.

## Failure Modes

| ID | Failure | Why It Matters | Grader |
| --- | --- | --- | --- |
| F01 | frontmatter name/description corrupted | skill stops triggering | code |
| F02 | a documented mode (CREATE / ENHANCE) dropped from SKILL.md | callers lose half the skill | code |
| F03 | a template or the field guide goes missing from references/ | CREATE has nothing to scaffold from | code |
| F04 | a lib script (scaffold/audit) goes missing | CREATE/ENHANCE cannot run | code |
| F05 | scaffold_eval.py stops producing a valid eval skeleton | CREATE silently emits nothing usable | code (functional) |
| F06 | audit_eval.py stops discriminating healthy vs unhealthy skills | ENHANCE rubber-stamps a broken eval (the dead-grader trap, on the auditor itself) | code (calibration) |

## Eval Cases

| ID | Input | Expected Behavior | Must Not Happen |
| --- | --- | --- | --- |
| E01 | SKILL.md frontmatter | name=personal-create-eval + description | name/desc corruption (F01) |
| E02 | SKILL.md body | both CREATE and ENHANCE modes documented | a mode dropped (F02) |
| E03 | references/ | field guide + 3 templates present | a reference lost (F03) |
| E04 | lib/ | scaffold_eval.py + audit_eval.py present | a script lost (F04) |
| E05 | scaffold_eval.py --dry-run on fixtures/good-skill | exit 0, prints planned actions | scaffold broken (F05) |
| E06 | audit_eval.py --skill fixtures/good-skill | exit 0 (healthy) | auditor passes everything (F06) |
| E07 | audit_eval.py --skill fixtures/bad-skill | exit 1 (HIGH: no eval.ps1) | auditor misses a broken eval (F06) |

## Graders

### Code Graders (`eval.ps1`)

- `skill_frontmatter`: name=personal-create-eval + a description (F01).
- `both_modes_documented`: SKILL.md documents CREATE and ENHANCE modes (F02).
- `references_present`: field guide + eval-plan / eval-grader / judge-rubric templates exist (F03).
- `lib_scripts_present`: scaffold_eval.py + audit_eval.py exist (F04).
- `scaffold_smoke`: `scaffold_eval.py --dry-run` on the good-skill fixture exits 0 + plans actions (F05).
- `audit_calibration`: `audit_eval.py` on the good-skill fixture exits 0 (healthy) AND on the
  bad-skill fixture exits 1 (HIGH). This calibrates the auditor itself -- a grader that passes
  everything measures nothing (F06).

### Model Judge

- None. The skill's quality is whether the evals it PRODUCES are good; that is judged case-by-case
  by the human running the skill, not generically here. The skill's own machinery is deterministic.

## Baseline Run

- date: 2026-06-01
- agent version: personal-create-eval @ plugin 0.7.0
- result summary: all code graders PASS; scaffold smoke exit 0; audit good->0 / bad->1.

## Ship Gate

- `eval.ps1` exits 0. F06 (the auditor stops discriminating) is the highest-severity failure --
  an auditor that can't tell a broken eval from a healthy one defeats ENHANCE mode entirely.

## Known Limitations

- `scaffold_smoke` exercises `--dry-run` only (the plan path), so it proves scaffold can plan
  but not that it WRITES correctly. Scaffold's actual file-writing was verified by hand at build
  time (it scaffolded this skill's own evals/). A future regression in the write path would not
  be caught by this grader; expanding the test would add write+cleanup side-effects to the grader
  for little gain, so it is recorded here as a known gap rather than tested.
