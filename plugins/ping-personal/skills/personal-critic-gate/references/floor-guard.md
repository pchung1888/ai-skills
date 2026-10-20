# Floor guard (lowered-bar check)

`lib/floor_guard.py --base <ref>` reads `git diff <ref>` (default HEAD~1) and prints one row per
signal as `file:line signal | text`. Last line `FLOOR PASS` (exit 0) or `FLOOR FAIL <n>` (exit 1).

Signals: a deleted test, a skip/xfail marker added, a numeric threshold lowered in a test or eval,
a lint/type suppression added (noqa, ts-ignore, eslint-disable, type: ignore), an empty catch or
bare pass/stub added, an assertion removed from a test or eval.

Scope: code and test files only. Markdown, `floor_guard.py`, its own test and `fixtures/` folders
are skipped, so documentation that names these signals never flags itself.

Use: run it before dispatching seats and paste its rows into every seat brief. A hit with no written
reason (a commit message line, a decisions row) is an automatic FIX vote, same as an unverified
done claim. A written reason clears the hit.
