# Eval plan - personal-big-project

## Target behavior

Given a requirement, a done command and the owner's caps, the skill sets up an unattended run that
asks every question before the owner leaves and none after, takes pass only from the done
command, keeps baselines and side effects inside their limits, reports to the phone in plain
words, fixes what it can, defers with evidence what it cannot, and stops itself when nothing
actionable is left.

- LEVER (versioned): SKILL.md, references/*, scripts/*.
- SUBJECT (graded): the state folder a run leaves behind (run log, reports, the STATUS.md Tasks section,
  side-effects log, baseline hashes, OWNER-REPORT.md, coordinator transcript), plus the generated
  tick prompt and stage scripts.

## Failure modes -> graders

| # | Failure mode | Grader | Type |
|---|---|---|---|
| 1 | A rule drops out of SKILL.md in an edit (Opus gate, ask-at-door, done-only pass, baseline, caps, fix/defer/stop, done rule, no-progress stop, context 70%) | `skill_rules` invariant list + mutation calibration | code |
| 2 | SKILL.md names a file or agent that does not exist | `referential_integrity` | code |
| 3 | Task table (STATUS.md Tasks section) loses or reorders rows, overwrites the coordinator's text around it, double-counts fix rounds, wrong times | `build_table` (test_build_table.py, real journals) | code |
| 4 | Generated tick or stage script has an unfilled placeholder, bad escaping, invalid JS, >3 parallel | `generate` (test_generate.py, node --check) | code |
| 5 | Estimated timestamps in the run log | `check_run` log-times | code |
| 6 | Ids, hashes or run codes in the owner's phone report | `check_run` report-plain | code |
| 7 | A planned task vanishes from the STATUS.md Tasks section | `check_run` table-rows | code |
| 8 | Side effects over their caps | `check_run` side-effects | code |
| 9 | Baseline re-taken from new code | `check_run` baselines (sha256) | code |
| 10 | Agent deferrals hidden from the verdict line | `check_run` verdict | code |
| 11 | AskUserQuestion while the owner is away | `check_run` no-questions (transcript) | code |
| 12 | Pre-flight passes a wrong model, low quota, full disk, missing state, or a done command that already passes | `preflight` calibration | code |
| 13 | Non-ASCII characters | `ascii` | code |
| 14 | Retro numbers wrong or made up (tokens, stages, pauses, owner messages, late questions) | `retro_metrics` against real-run journals + late-question mutation | code |
| 15 | Feedback loop or alignment interview drops out of SKILL.md | `skill_rules` invariants (GOAL-BRIEF, friction log, retro folder) | code |
| 16 | Next-action rules wrong: defer stops a stage, retry replays a cached failure, a second pause, no-progress never stops, weekly cap, handoff | `python self-tests` (test_run_state.py) | code |
| 17 | check_run passes with missing evidence, malformed rows or a verdict that does not match outcomes | `python self-tests` (test_check_run.py) | code |
| 18 | A push lands on the target branch of an open review request (it can merge the request) | `python self-tests` (test_log_row.py push refusal) + `generate` (protectedBranches shape) | code |
| 19 | Two tasks share one check, or a task's check is the full done command, so the first task always fails | `generate` (shared-check refusal, sharedCheck escape) | code |
| 20 | Copilot reports only paraphrase the copilot skill, or chat gets a digest instead of the report | `generate` (tick and reporter brief text) | code |
| 21 | Status split over two files; the coordinator's STATUS.md text lost on rebuild | `build_table` (section rewrite) + `check_run` table-rows (section only) | code |
| 22 | A saved owner rule silently loses to a skill step; review replies sent before the fixes | `skill_rules` invariants (memory rule, reply order) | code |
| 23 | A send happens before its row is logged, or a cap stops the run silently with no owner question | `python self-tests` (test_log_row.py send / usage / raise-cap) + `generate` (tick and worker text) | code |
| 25 | A run's quality is not comparable across runs: no score, a self-graded score, a missing owner score hidden, the best run graded low | `python self-tests` (test_scorecard.py: bands, rates, coverage, SAFETY, calibration, scrub; test_retro_metrics.py: metrics.json; test_check_run.py: owner-feedback, owner-score) | code |
| 24 | A read-only critic or judge cannot run inside a stage, or its findings are lost | `generate` (review step) + `python self-tests` (test_run_state.py reviews/<id>.md) | code |

No model judge: every failure above is checkable by code. The quality of the coordinator's
judgement in a live run is NOT graded here (the GREEN scenario run was dropped by owner decision
1h); each real run's RETRO.md and the improve mode are the only check on it.

## Calibration

- `check_run`: fixtures/good-run must PASS; seven breaks (one per rule, applied to a temp copy)
  must each FAIL with that rule's name.
- `preflight`: good inputs print PREFLIGHT SCRIPTED CHECKS PASS; bad inputs fail all five
  scripted checks.
- `skill_rules`: a mutant SKILL.md with one invariant renamed must be detected.
- build_table and generate tests were mutation-checked when written (label grouping, JS escaping,
  placeholder refusal).

## Ship gate

`pwsh plugins/ping-personal/skills/personal-big-project/evals/eval.ps1` prints
`EVAL PASS personal-big-project (9)` and `pwsh plugins/ping-personal/evals/run-all.ps1` prints
`ALL EVALS PASS`.
