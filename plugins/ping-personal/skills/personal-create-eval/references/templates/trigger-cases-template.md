# Trigger cases for <skill-name>

Fill in 3-5 prompts per list. Put them in `evals/eval-plan.md` (or `evals/fixtures/`) so a reviewer can
check the skill's `description:` against them.

## Should fire (a user asking for this skill's job)

<!-- Write real prompts a user would type. Example: "summarize this youtube link: https://youtu.be/abc123" -->
1. <prompt that should trigger the skill>
2. <same ask, different wording>
3. <ask that names no skill but needs it>

## Should stay quiet (looks close, belongs to another skill or none)

<!-- Name the skill that should win instead. Example: "write an eval for my skill" -> personal-create-eval, not this one -->
1. <near-miss prompt> -> <skill that should handle it, or "none">
2. <near-miss prompt> -> <skill that should handle it, or "none">

## Description collision

Run `python lib/collision_check.py`. If the new skill appears in a top pair, reword its description so
the "should stay quiet" prompts no longer match it. The report never fails a run.
