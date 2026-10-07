# Eval plan: personal-harness

Deterministic contract grader (`eval.ps1`). It checks that SKILL.md still carries
the rules the skill exists for and that the scripts it runs exist; it does not
run the bootstrap.

| Failure mode | Check in eval.ps1 |
|---|---|
| Skill stops loading or triggering | frontmatter name + description with trigger phrases |
| Apply drifts from the real bootstrap | bootstrap path + PASS line documented; referenced scripts exist |
| Rule edits skip the hash manifest or the check | `--update-manifest` and `check_harness_sync.py --check` documented |
| Global rules change without consent | wait-for-OK rule |
| Generated files hand-edited / personal state committed | both boundaries documented |
| Session keeps old rules | `/reload-plugins` reminder |
| Dead metric | calibration: a copy without the approval rule must fail |

Not covered (manual): a real apply on a fresh machine.
