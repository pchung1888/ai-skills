# Eval Plan: personal-goal

> Follows the agent-evals-playbook. Mirrors the approved shape from `personal-htsw/evals/`.

## Target Behavior

personal-goal initializes a long-running multi-phase goal: it validates an
acceptance gate (an empirically testable accept-cmd + match/regex, OR an
`--unverifiable` reason >= 10 chars), resolves the doc area, writes a crash-recovery
beacon (audit-tracker) with the right frontmatter, parses a `--plan` into phases,
and seeds `.claude/TODO.md` -- committing beacon + TODO in one commit. The
load-bearing code is `lib/accept_gate.py` (the gate) and `lib/plan_parser.py` (phasing).

## Failure Modes

| ID | Failure | Why It Matters | Grader |
| --- | --- | --- | --- |
| F01 | accept_gate ACCEPTS an unverifiable goal (no match/regex, no reason) | violates preflight rule 7 -- goals ship with no way to verify "done" | code |
| F02 | accept_gate REJECTS a valid accept-cmd + match | every well-formed goal is blocked | code |
| F03 | accept_gate accepts an `--unverifiable` reason that is too short | the escape hatch becomes a rubber stamp | code |
| F04 | plan_parser drops or mis-orders phases from a `--plan` | phases silently lost from the beacon | code |
| F05 | a load-bearing lib script (accept_gate/plan_parser) missing | the skill cannot initialize a goal | code |
| F06 | frontmatter name/description corrupted | skill stops triggering | code |

## Eval Cases

| ID | Input | Expected Behavior | Must Not Happen |
| --- | --- | --- | --- |
| E01 | accept_gate --validate --accept-cmd ... --accept-match ... | exit 0 (valid gate) | rejecting a valid gate |
| E02 | accept_gate --validate --accept-cmd ... (no match/regex) | non-zero (unverifiable) | accepting it (F01) |
| E03 | accept_gate --validate --unverifiable "x" (1 char) | non-zero (reason too short) | accepting it (F03) |
| E04 | plan_parser on `fixtures/plan-2-phases.md` | output has both phase titles, in order | a phase dropped (F04) |

## Graders

### Code Graders (`eval.ps1`)

- `skill_frontmatter`: SKILL.md declares name=personal-goal + a description.
- `lib_scripts_present`: lib/accept_gate.py and lib/plan_parser.py exist.
- `accept_gate_enforces`: valid gate -> exit 0 (E01); no match/regex -> non-zero (E02);
  short `--unverifiable` -> non-zero (E03). (Covers F01, F02, F03.)
- `plan_parser_parses_fixture`: plan_parser on the bundled 2-phase fixture emits both
  phase titles ("Author three reference notes", "Deploy the notes ...") in order (E04, F04).

### Model Judge

- None. Gate validation and plan parsing are deterministic; code graders only.

## Baseline Run

- date: 2026-05-31
- result summary: `eval.ps1` -> gate accepts valid / rejects both invalid; plan_parser
  emits both phases. All code graders pass.

## Ship Gate

- `eval.ps1` exits 0. F01 (gate accepts an unverifiable goal) is the highest-severity
  failure -- a regression there defeats the whole "verifiable acceptance" preflight rule.
