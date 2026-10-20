# Eval plan: wait-what (alias)

## Target behavior (the contract)

`wait-what` is a forwarding alias. It keeps `/wait-what`, and any skill text that names `wait-what`,
working after Matt Pocock's plugin is disabled. It calls `ping-personal:personal-wait-what` with the same
arguments. All behavior lives in `personal-wait-what`.

## Failure modes -> graders

| # | Failure | Grader |
|---|---|---|
| 1 | Name or invocation flag drifts, so the old command stops resolving | code: alias_frontmatter |
| 2 | The forward breaks, or the target becomes manual-only so the Skill tool refuses it | code: alias_forwards |

## Ship gate

eval.ps1 exits 0 AND run-all.ps1 prints ALL EVALS PASS.
