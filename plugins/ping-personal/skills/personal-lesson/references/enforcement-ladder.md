# Enforcement ladder for a repeated lesson

Use this when a new lesson matches a lesson that is already stored. A second occurrence means
the written lesson did not stop the mistake, so a stronger fix is needed.

Pick the highest rung that is practical (rung 1 is strongest):

1. Architecture: change the code or tool so the mistake cannot happen.
2. Hook or lint: a check that blocks the action or fails the build.
3. Eval or test: an automated check that fails when the mistake returns.
4. Doc: a written rule (what the lesson already is).

Rules:

- Print the proposal to the user as text: the matching lesson title, the rung, and the exact change.
  Never edit code, hooks or tests yourself from this step.
- The new check must fail on the original case before it ships. Show the failing run, then the fix.
- If the lesson duplicates a hard rule, Step 0 already stopped; this step is not reached.
- Matches are searched in `~/.claude/lessons/*.md` and the domain skills' seed lessons.
  Example fixture: `evals/fixtures/repeated-lesson.md`.
