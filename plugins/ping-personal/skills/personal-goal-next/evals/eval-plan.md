# Eval Plan: personal-goal-next

> Follows the agent-evals-playbook. Mirrors the approved shape from `personal-htsw/evals/`.
> NOTE: advance.py commits via git on success, so this eval only exercises the paths
> that return BEFORE the git step (the refuse-guards) plus unit-tests the pure
> string-transform core (phase_table.update_row). It never creates a commit.

## Target Behavior

personal-goal-next advances the audit-tracker beacon after a phase finishes: it
REFUSES to advance unless the driving session supplies real evidence (`--tokens`,
`--outcome`, `--subagent`; `--commit` when outcome=PASS), then flips the phase row,
appends a cost-log row, updates the checkpoint, atomically rewrites the beacon, and
commits. The honesty contract (preflight rule 4) lives in the refuse-guards; the
beacon mutation lives in `lib/phase_table.py`.

## Failure Modes

| ID | Failure | Why It Matters | Grader |
| --- | --- | --- | --- |
| F01 | advance proceeds with no `--tokens`/`--outcome` | beacon advances with no honest cost/outcome (breaks rule 4) | code |
| F02 | advance with outcome=PASS but no `--commit` is allowed | a "Done" phase with no commit -> recovery cannot verify it landed | code |
| F03 | update_row advances a phase the beacon never declared | writes a phantom phase row | code |
| F04 | update_row re-advances an already-Done phase (duplicate) | double-counts a phase; corrupts the audit trail | code |
| F05 | update_row loses the commit/subagent on the advanced row | recovery loses the "last good commit" pointer | code |
| F06 | a refuse-path accidentally creates a git commit | a rejected advance still mutates history | code |
| F07 | load-bearing lib (advance/phase_table) missing, or frontmatter corrupt | skill cannot run / stops triggering | code |
| F08 | advance with outcome=PASS but no `--verify` is allowed (unverified done) | a "Done" with no Gate 4 evidence -- the fable-mode fail-closed contract breaks | code |

## Eval Cases

| ID | Input | Expected Behavior | Must Not Happen |
| --- | --- | --- | --- |
| E01 | advance --outcome PASS, no --commit | exit 2 (refused), no commit | a "Done" with no commit (F02) |
| E02 | advance with no --outcome | non-zero (argparse), no commit | proceeding (F01) |
| E03 | advance with no --tokens | non-zero (argparse), no commit | proceeding (F01) |
| E04 | update_row on a fresh phase 1 (fixture) | status flips, commit+subagent recorded | losing the commit (F05) |
| E05 | update_row on already-Done phase 2 (fixture) | RuntimeError | duplicate advance (F04) |
| E06 | update_row on undeclared phase 99 | RuntimeError | phantom row (F03) |
| E07 | advance --outcome PASS --commit, no --verify | exit 2 (refused), no commit | unverified done advancing (F08) |
| E08 | advance --outcome PASS --verify "UNVERIFIED: <reason>" | guard passes (escape hatch) | escape hatch silently closed (F08) |

## Graders

### Code Graders (`eval.ps1` + `check_phase_table.py`)

- `skill_frontmatter`: SKILL.md declares name=personal-goal-next + a description.
- `lib_scripts_present`: lib/advance.py and lib/phase_table.py exist.
- `advance_refuses_incomplete`: E01-E03 all exit non-zero AND `git rev-parse HEAD`
  is unchanged across the three calls (no stray commit -- F06).
- `phase_table_guards`: `check_phase_table.py` exits 0, proving E04 (flip + commit
  recorded), E05 (duplicate-advance rejected), E06 (undeclared-phase rejected).

### Model Judge

- None. The honesty contract and the beacon mutation are deterministic; code only.

## Baseline Run

- date: 2026-05-31
- result summary: refuse-guards return exit 2 with HEAD unchanged; check_phase_table.py
  exits 0. All code graders pass.

## Ship Gate

- `eval.ps1` exits 0. F01/F02 (advancing without evidence/commit) and F06 (a refused
  advance still commits) are the highest-severity -- they break the crash-recovery trust model.
