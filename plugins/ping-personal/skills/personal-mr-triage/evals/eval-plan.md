# Eval plan: personal-mr-triage

Deterministic contract grader (`eval.ps1`). It checks that SKILL.md still carries
the rules the skill exists for; it does not run a live merge request.

| Failure mode | Check in eval.ps1 |
|---|---|
| Skill stops loading or triggering | frontmatter name + description with trigger phrases |
| Findings accepted without checking | "verify" step requires `file:line` or command output evidence |
| Replies leak the private conversation | rule against mentioning the user's private chat |
| Replies posted without consent | post-only-after-approval rule |
| "Pushed" claimed without proof | remote commit hash rule |
| Only one forge supported | both `glab mr` and `gh pr` paths documented |
| Dead metric (grader passes anything) | calibration: a copy without the approval rule must fail |

Not covered (manual): a real triage run against a live MR with reviewer comments.
