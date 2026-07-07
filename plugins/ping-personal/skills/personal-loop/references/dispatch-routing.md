# Dispatch routing + bounded-tree rules

route(features) -> target (deterministic; model override recorded separately):
| features | target |
|---|---|
| n_steps==1 single-shot | subagent (Explore / general-purpose) |
| n_steps>1, n_domains==1 | /personal-goal |
| n_domains>1 or multi_phase | /personal-workflow |
| has_own_gate and long_horizon | nested /personal-loop (depth-2 cap) |

Bounds (spec S4.2): depth is PARENT-INJECTED + immutable (`check_depth` refuses
>=2). Width counts TOTAL live descendants charged to the root ledger
(`check_width`): normal free<=3 / confirm<=6 / stop; another session active
tightens to free<=1 / confirm<=3 / stop. All descendant fan-out -- including a
/personal-workflow leaf that itself /workflows-fans-out -- is charged to the
root ledger BEFORE dispatch. Runaway is stopped by these counted limits +
iters / deadline / run-ceiling, NOT by the (estimated) token budget.
