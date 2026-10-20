# Eval plan: personal-diagnosing-bugs

## Target behavior (the contract)

An instruction-only discipline in six phases. Its core rule: no hypothesis before a
red-capable feedback loop that has already run once. The loop ladder must keep the ASP Classic
seams (an HTTP request to the IIS page, sqlcmd, a cscript COM harness, IIS log replay), and
the shared-box read-only rule must stay.

## Failure modes -> graders

| # | Failure | Grader |
|---|---|---|
| 1 | Frontmatter drift | code: skill_frontmatter |
| 2 | A phase is deleted or reordered | code: six_phases |
| 3 | The loop-before-theory gate or the ranked-hypotheses step is softened | code: loop_before_theory |
| 4 | A re-sync from upstream drops the ASP Classic feedback loops | code: start_loops |
| 5 | Probes are allowed to change QA, DEV or client boxes | code: shared_boxes_read_only |
| 6 | The HITL template goes missing, gains non-ASCII, or stops parsing | code: hitl_template |

## Ship gate

eval.ps1 exits 0 AND run-all.ps1 prints ALL EVALS PASS.
