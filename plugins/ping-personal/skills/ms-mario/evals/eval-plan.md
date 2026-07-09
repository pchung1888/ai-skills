# Eval Plan -- ms-mario persona wrapper

## Target Behavior

The wrapper exposes Ms.Mario to Codex while keeping `plugins/ping-personal/agents/ms-mario.md` as the canonical source.

## Failure Modes

| Failure | Grader |
|---|---|
| Wrapper stops referencing the canonical persona source | `scripts/check_dual_runtime.py` |
| Codex `agents/openai.yaml` policy is missing | `scripts/check_dual_runtime.py` |
| Wrapper model tier drifts from the canonical persona | `scripts/check_dual_runtime.py` |

## Ship Gate

`pwsh plugins/ping-personal/skills/ms-mario/evals/eval.ps1` must print `EVAL PASS ms-mario persona wrapper`.
