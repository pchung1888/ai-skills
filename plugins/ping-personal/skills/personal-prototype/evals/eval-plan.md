# personal-prototype -- eval plan

`/personal-prototype` is an orchestration conductor: its real output (N approaches, an
HTML artifact, an implemented + verified feature, a PR) is dynamic and judgment-heavy,
so a behavioral A/B benchmark would be noisy and expensive. Instead the eval is a
**deterministic structural grader** (same shape as `personal-htsw/evals/eval.ps1`): it
guarantees the skill on disk still contains the contract the conductor depends on. If a
future edit silently drops a phase, a delegate, or a mode, the grader goes red.

## Failure modes the grader guards against

| ID  | Failure mode | Check |
|-----|--------------|-------|
| F01 | Frontmatter broken -- skill will not load | `name: personal-prototype` + non-empty `description` present |
| F02 | Default count drifts or is undocumented -- "default 5" is the headline contract | SKILL.md states the default of 5 and the 2..8 clamp |
| F03 | A mode is dropped -- skill can no longer handle UI or non-UI features | both "UI mode" and "NON-UI mode" documented; both reference files exist |
| F04 | A delegate is silently removed -- conductor loses a phase tool | `/browse`, an iterate beat, a durable-run option (personal-workflow/goal), and a ship path are all named in SKILL.md |
| F05 | The choose/recommend beat vanishes -- skill stops helping the user pick | "recommend" + a choose/AskUserQuestion mention present |
| F06 | Verification beat vanishes -- skill ships unverified work | a VERIFY phase + screenshot are documented |
| F07 | chrome MCP creeps back in -- violates CLAUDE.md browsing rule | SKILL.md does NOT reference `mcp__claude-in-chrome` |
| F08 | Non-ASCII (em-dash/smart-quote) leaks into a parsed-adjacent file | SKILL.md + both references + `scripts/check_prototype.py` are pure ASCII |
| F09 | Model guidance dropped -- every dispatch runs on the frontier model (token waste) | a `Model selection` section names both `sonnet` and `opus`. Moves on this revision (absent before, present after) -- the discrimination test |
| F10 | Fidelity-from-real-artifacts principle dropped -- prototypes built from prose get rejected | SKILL.md states fidelity + `real artifacts` |
| F11 | Behavior and visual gates collapse into one -- "it works" passes a layout that looks wrong | both `behavior gate` and `visual gate` documented |
| F12 | The `--tournament` critic-gate selection beat vanishes -- the headline capability is lost | SKILL.md names `--tournament` and `personal-critic-gate`. Moves on this revision -- the discrimination test |
| F13 | SKILL references a `scripts/*.py` that is missing -- broken instruction | every `scripts/*.py` path named in SKILL resolves on disk |
| F14 | Built prototype not self-contained / has position:fixed / non-ASCII / missing markers | `check_prototype.py` returns CHECK-OK on the good fixture and CHECK-FAIL on every bad fixture |

## Why structural, not behavioral

The plugin's acceptance command is `pwsh plugins/ping-personal/evals/run-all.ps1`
printing `ALL EVALS PASS`. A green structural grader keeps the suite honest and fast
and catches the realistic regression (an edit erodes the contract). Behavioral quality
-- are the N options genuinely distinct, is the recommendation defensible -- is judged
by the human in the loop during an actual run, which is the right place for taste.

F09-F14 extend the structural floor as this revision lands the start-prototype
portable lessons. F14 adds a deterministic SUBJECT-level layer: the bundled
`scripts/check_prototype.py` is calibrated against `evals/fixtures/` (a good fixture
must CHECK-OK; each bad fixture trips exactly one rule and must CHECK-FAIL). We do NOT
port the host repo's `gold_artifact` grader -- it pinned a host-repo path
(`docs/prototype-687/prototype.html`) that does not exist in this plugin; the good
fixture is the positive calibration instead. The headline `--tournament` flow (build
real variants, vote via `/personal-critic-gate`) is structurally guarded by F12 and
exercised live in the goal's dogfood phase, not in this fast deterministic eval.
