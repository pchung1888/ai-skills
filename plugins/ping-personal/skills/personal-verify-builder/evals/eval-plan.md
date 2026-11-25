# Eval plan: personal-verify-builder

## Target behavior (the contract)

A generator. `create` writes a repo's own `.claude/skills/verify/` skill, named exactly `verify`
and model-invocable so Claude Code runs it before each commit. Every generated check must have
been seen red on a planted bug. Findings are reported, never hidden by weakening a check.
Shared servers stay read-only. Before a commit only touched features run.

## Failure modes -> graders

| # | Failure | Grader | Tier |
|---|---|---|---|
| 1 | Frontmatter drift or a non-ASCII byte in any skill file | code: skill_frontmatter | every release |
| 2 | A mode is lost | code: four_modes | every release |
| 3 | The output name or the before-commit contract drifts (`verify-<repo>`, `disable-model-invocation`) | code: output_contract | every release |
| 4 | The planted-bug rule is softened or dropped from the template | code: able_to_fail | every release |
| 4b | Reverting a planted bug wipes uncommitted work, or leaves a mutated DLL registered | code: safe_revert | every release |
| 5 | Checks may be weakened, or product code edited, to get green | code: findings_stay_findings | every release |
| 6 | Shared QA/DEV/client servers may be driven or seeded | code: shared_read_only | every release |
| 7 | Every feature runs on every commit | code: touched_only | every release |
| 8 | A generated-skill section is lost from the template | code: template_sections | every release |
| 9 | maintain outcomes blur drift with bugs | code: maintain_outcomes | every release |
| 10 | The retro loop edits the skill without the user | code: retro_loop | every release |
| 11 | The fixture loses its planted-bug switch, so tier 2 cannot go red | code: fixture_oracle | every release |
| 12 | The pstack MIT notice goes missing | code: notice | every release |
| 13 | The generator writes a skill whose checks do not run, do not catch the planted bug, or do not go green again | behavior: run-fixture.ps1 | before a release that changes SKILL.md or references/ |

## Tier 2: the fixture run

`evals/run-fixture.ps1` copies `fixtures/tiny-ledger` (a Python `http.server` + `sqlite3` app)
to a temp folder, has a headless `claude -p` session follow `create`, then checks the output.
Headless Claude Code refuses file-tool writes under `.claude/` even with allow rules, so the
script makes `.claude/skills/verify` a junction to `_verify_staging/` and the agent writes there.
After the session:

1. runs the single-line command under the generated `## Run all checks` heading on clean code:
   must exit 0;
2. a neutral edit (an SQL comment) must stay 0, so a check that reds on any file change fails;
3. two planted bugs must each give a real non-zero exit code (a timeout does not count): the SQL
   counts cancelled trades (`WHERE status = 'open'` -> `WHERE 1 = 1`), and the page total drops
   rows (`rows` -> `rows[:1]` in `app.py`, which the SQL check cannot see);
4. after the last revert it must exit 0 again.

It also fails when the agent commits, changes product code, leaves a server on port 8765, or
writes a generated SKILL.md without a `---` frontmatter block, `Synced at` or `## Safety`.

Not covered: that Claude Code really runs the generated `verify` before a commit. That rests on
the Claude Code skills docs (code.claude.com/docs/en/skills, "Run your checks before each
commit"); no eval makes a real commit. The fixture also does not prove the agent kept
uncommitted work safe during plant and revert (every file is committed before the session),
and `Bash(python *)` lets the agent under test run any Python, so "work only inside this
folder" rests on the prompt. Run the fixture by hand, never unattended.

It costs a headless session (about 100-200K tokens, an estimate), so `run-all.ps1` does not run it.

## Ship gate

eval.ps1 exits 0 AND run-all.ps1 prints ALL EVALS PASS. For a change to SKILL.md or
references/, run-fixture.ps1 also prints FIXTURE PASS.
