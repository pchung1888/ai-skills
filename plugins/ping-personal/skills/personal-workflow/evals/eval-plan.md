# Eval Plan: personal-workflow

> Follows the agent-evals-playbook. Mirrors the approved shape from
> `personal-htsw/evals/`. This skill already ships a full test harness
> (`tests/smoke.ps1`, 10 deterministic tests); this eval **wraps** that harness
> (do not duplicate) and adds the frontmatter + script-presence checks.

## Target Behavior

Given a goal / plan / TODO-list, personal-workflow discovers the host project's
skills+agents, routes each phase to the best capability, classifies every proposed
action through the fence (`fence.py`: ALLOW / PAUSE-ALWAYS / PAUSE-ACK-ONCE), fans
out via /workflows only when safe, and records real token costs against the
personal-goal beacon. The conductor logic is markdown; the load-bearing code is
`lib/discover.py` (capability discovery) and `lib/fence.py` (the safety gate).

## Failure Modes

| ID | Failure | Why It Matters | Grader |
| --- | --- | --- | --- |
| F01 | fence UNDER-pauses (lets a destructive cmd through) | a `DROP TABLE` / `git push --force` slips past the gate | code (smoke) |
| F02 | fence OVER-pauses a safe command | every safe commit stalls; conductor becomes unusable | code (smoke) |
| F03 | multiline/schema-qualified SQL smuggles past the no-WHERE guard | bypass of the destructive-SQL rule | code (smoke) |
| F04 | discover.py mis-parses a SKILL.md description / confidence | wrong capability map -> wrong routing | code (smoke) |
| F05 | SKILL.md loses the roles block or the 5 loop steps | the conductor contract silently degrades | code (smoke) |
| F06 | routing.md cites an agent that is not on disk | routes a phase to a non-existent agent | code (smoke) |
| F07 | a load-bearing lib script (discover/fence) goes missing | the conductor cannot run | code |
| F08 | frontmatter name/description corrupted | skill stops triggering | code |

## Eval Cases

| ID | Input | Expected Behavior | Must Not Happen |
| --- | --- | --- | --- |
| E01 | the full `tests/smoke.ps1` suite | all 10 tests PASS, exit 0 | any smoke test red |
| E02 | `SKILL.md` frontmatter | name=personal-workflow + description present | mode/name corruption |
| E03 | `lib/` directory | discover.py and fence.py both present | a load-bearing script deleted |

## Graders

### Code Graders (`eval.ps1`)

- `skill_frontmatter`: SKILL.md declares name=personal-workflow + a description.
- `lib_scripts_present`: lib/discover.py and lib/fence.py exist.
- `smoke_suite_passes`: runs the existing `tests/smoke.ps1` in a child shell;
  requires exit 0 (this is the bulk grader -- 10 fence/discover/structure tests).

### Model Judge

- None. Everything this skill must guarantee is deterministic (a safety gate and a
  parser); per the playbook, deterministic failures get code graders, not judges.

## Baseline Run

- date: 2026-05-31
- agent version: personal-workflow @ plugin 0.5.0
- result summary: `eval.ps1` -> frontmatter + lib present + tests/smoke.ps1 exit 0.

## Ship Gate

- `eval.ps1` exits 0 (which requires the wrapped smoke suite to be fully green).
- No fence under-pause is the highest-severity gate (F01) -- a safety regression blocks ship.
