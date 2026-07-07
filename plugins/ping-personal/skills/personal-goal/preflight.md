# 10-Rule Preflight Checklist

The skill walks these in order before step 6 (write beacon). Each rule is auto-satisfied by the skill OR triggers a user-confirm prompt OR is informational.

| # | Rule | Type | How |
|---|---|---|---|
| 1 | No team mode for unattended runs | auto-satisfy | Skill never calls `TeamCreate`. All worker dispatches in the driving session are one-shot `Agent(run_in_background=true)`. |
| 2 | Audit-tracker as crash-recovery beacon | auto-satisfy | Step 8 of the invocation procedure writes and commits the beacon. |
| 3 | Tiny-finishing-edit rule | documented for driver | Section "Useful patterns" of `agent-dispatch-template.md` describes the heuristic: agent returns reporting <=10 trivial lines remaining -> driving session finishes inline rather than re-dispatching. Not auto-enforced; the driving Claude session applies judgment. |
| 4 | Strong-honesty subagent return contract | mechanically enforced | The `agent-dispatch-template.md` brief instructs the agent to return a fenced YAML payload with `total_tokens`, `surprises`, `blocked_vs_done`. `/personal-goal-next` REFUSES to advance the beacon unless `--tokens`, `--outcome`, and (if `--outcome=BLOCKED`) `--notes` are supplied. |
| 5 | Dogfood phases are diagnostic gates | user-confirm | Skill asks at preflight: "Have you included a dogfood phase in the plan?" Y/N. Re-validated when `--plan` is parsed: skill greps phase headings for "dogfood" or "spec" or "self-render" patterns; absence triggers a second warning. Either way the skill proceeds. (Honor system; mechanical detection not feasible.) |
| 6 | Cascading normalization > single-pass | informational | Documented in `agent-dispatch-template.md` "Useful patterns" section. Not all goals do normalization, so not enforced. |
| 7 | Acceptance criterion empirically testable | auto-satisfy | Enforced by `accept_gate.py` -- refuses unless `--accept-cmd` with `--accept-match` or `--accept-regex`, or `--unverifiable` with reason >=10 chars. |
| 8 | Phase budget mean ~80K / p90 ~130K / p95 ~150K | encoded in agent-dispatch-template | Default soft-budget per phase = 100K (printed in agent brief). Plan headings can override per phase via `Estimated tokens: <N>`. |
| 9 | Commit the beacon as part of step 8 | auto-satisfy | The invocation procedure commits beacon + TODO.md in a single git commit at step 8. |
| 10 | Preflight ToolSearch | auto-satisfy | Step 1 of the invocation procedure loads required deferred tools. |
