---
name: personal-verify-builder
description: Use when the user wants a repo to check its own code changes before commit - "set up verify for this repo", "build a verify skill", "make the agent prove the feature works", "feature map", "is the verify skill still true to the code" - or types /personal-verify-builder create, maintain, rate or improve. Works on any stack (ASP Classic, VB6, T-SQL, React, .NET). Not for running an existing repo's checks (that is the repo's own /verify) or for finding the cause of a known bug (personal-diagnosing-bugs).
---

# Verify builder

A test checks the cases someone thought to write. This skill gives a repo its own `verify`
skill: a feature map, a way to drive each feature, and checks that were each seen to fail on a
planted bug. Claude Code runs a project skill named exactly `verify` before each commit, so
the checks run without anyone remembering to ask. The method follows poteto's pstack
`create-verification-skill` (MIT, see `THIRD-PARTY-NOTICES.md`).

The generated skill is written for an agent that reads it cold, mid-change, and has never seen
the repo. Use the repo's real commands, paths and names. Leave no placeholder.

## Modes

| You type | What happens |
|---|---|
| `create` | Survey the repo and write `.claude/skills/verify/` with checks proven to fail on a planted bug |
| `maintain` | Bring an existing `verify` skill back in line with the code, and report each result as in sync, updated, bug or blocked |
| `rate <1-5> <note>` | Append one row to the retro log and stop |
| `improve` | Read the retro log and propose edits to this skill |
| nothing | Ask which mode in one line |

## Rules for every mode

1. **Every check must fail on a planted bug.** A check you never saw fail proves nothing. For
   each check, plant one small break in the code it guards, run it red, revert from a backup
   copy (`create` step 6), run it green.
   Doctor and read-only checks against a shared server prove they can fail on the local box,
   with a wrong expected value; never change a server to plant a bug.
2. **Findings stay findings.** When the current code fails a check, report it with the steps to
   reproduce. Never weaken a check, a golden file or an expected value to make it pass, and
   never change product code unless the user asks.
3. **Shared servers stay read-only.** QA, DEV and client servers get the doctor and read-only
   config checks only. Drive features and plant bugs only on the local box or a copy.
4. **The output is named exactly `verify`,** at `.claude/skills/verify/SKILL.md` in the repo
   root, with no `disable-model-invocation`. Another name or that flag stops the run before
   each commit.
5. **Touched features only before a commit.** The feature map lists the files behind each
   feature; the generated skill runs only the features a change touches. `/verify all` runs
   everything.
6. **Stop only what you started.** Record the PID or port of every process a run launches and
   stop only those; never stop an instance you did not start. Evidence goes to
   `.claude/verify-evidence/` (gitignored) and survives cleanup.
7. **Honest scope.** Say what is checked, against which data, and what is not covered.

## create

If `.claude/skills/verify/SKILL.md` already exists, stop: offer `maintain`, and overwrite only
when the user says so in this session.

```text
Create progress:
- [ ] 1 Survey: surface, launch, drive handles, data, isolation
- [ ] 2 Feature list: 3-5 features, files behind each, what proves each works
- [ ] 3 Checks chosen per feature from references/check-layers.md
- [ ] 4 Files written from references/verify-template.md
- [ ] 5 All checks green on the current code, or each red one reported as a finding
- [ ] 6 Every check seen red on a planted bug, then green after revert
- [ ] 7 Sync commit recorded; generated skill followed once as a cold reader
- [ ] 8 Hand-off report
```

1. **Survey the repo, not the user.** Find what a user touches (pages, endpoints, a CLI), how the
   app starts, how an agent can drive it, what data it needs, and whether two instances can
   run side by side. Reuse what exists: Playwright specs, test projects, seed scripts, a
   `run-<name>` skill. If launching needs a database, env file or multi-step build and no
   recipe exists, run `/run-skill-generator` first or write Launch from what you proved works.
   Ask the user only what the repo cannot show, such as which database copy is safe.
2. **List features by cost of a bug.** Start with the 3-5 features where a wrong result hurts a
   user most. For each: the user's name for it, how to reach it, the files behind it (pages,
   includes, procedures, DLLs), and the observable result that proves it works.
3. **Pick the checks** from references/check-layers.md: a runtime check plus the deeper layer
   that would catch the bug a user would feel. Compute expected values from the inputs, not by
   copying the app's own output, unless the check is a labeled characterization (golden) check.
4. **Write the files** from references/verify-template.md: SKILL.md, one `features/<name>.md`
   per feature, the runner and checks in `checks/`, golden files in `golden/`, and the
   `.gitignore` line. One single-line command must launch what it needs, run every check,
   stop what it started, and exit 0 only if all pass.
5. **Run everything on the current code.** Green is the goal. A red check on unchanged code is
   either a check bug (fix the check) or a finding (rule 2). Decide which by reading the code.
6. **Prove each check can fail.** For each check:
   1. If `git status --porcelain -- <file>` is not empty, the file holds someone's
      uncommitted work: tell the user before you touch it.
   2. Copy the file to `<system temp>/verify-plant-backup/<repo name>/<its repo-relative path>`
      (outside the repo, so no protected folder blocks it). Delete any old copy at that path
      first, then compare `git hash-object` of the copy and the original.
      No saved copy, no plant: a missing copy or a hash mismatch stops the plant. For a compiled target (a VB6 DLL, a .NET build), back up the
      good binary too.
   3. Plant the smallest break in the code the check guards and run that check. Copy its red
      line into the feature's "Proof it can fail".
      The red line must be that check's own assertion; a crash, import error or startup
      failure proves nothing about the check.
   4. Restore the file from the backup copy. Never use `git checkout` or `git stash` on
      a file you did not save first. Restore a compiled target's good binary and, for COM,
      re-register it. Rerun and confirm green.
   5. If the check stayed green in step 3, it is too weak: strengthen it and repeat.
   Do not commit a planted bug.
7. **Record and replay.** Put `git rev-parse HEAD` in each feature's "Synced at" cell. Then follow the
   generated SKILL.md once as a cold reader: Doctor, one feature, cleanup. Fix any step that
   does not run as written. If a step fails, return to step 4.
8. **Hand off** with this table, then what is not covered and any formal candidates:

   | Feature | Checks | Planted break | Red line | Green after revert |
   |---|---|---|---|---|

## maintain

Outcomes per feature: **in sync** (nothing it describes changed, checks pass), **updated** (the
map or checks now describe the new code, checks pass), **bug** (the checks describe the code
and the code fails them), **blocked** (cannot run or cannot be brought in line; say why).

1. **Run the checks as they are** and record the result before changing anything.
2. **Read every change since each feature's "Synced at" commit:**
   `git log --oneline <synced-at>..HEAD -- <that feature's files>` and the diffs. Also look for moved or renamed files and new code that touches the same data.
3. **Classify each change:** no effect; the check no longer describes the code (update the
   check from the code, never from the result); the promise changed on purpose (cite the
   commit or ticket, then update the expected value); or the promise may be broken (a bug
   candidate).
4. **Add missing features** that new files created, using `create` steps 2-6 for each.
5. **Rerun.** Every updated check must again be seen red on a planted bug, using `create`
   step 6 (backup copy, porcelain check, restore from the backup). The tree is often dirty
   during `maintain`, so never revert a planted bug with git.
6. **Move a feature's "Synced at"** only when it ended in sync or updated. Report each
   feature's outcome, the commits read, and each bug as steps in the code's own words.

## rate and improve

The retro log is `~/.claude/verify-builder-retros.md`, outside every repo. Create it with the
header `| Date | Repo | Mode | Score 1-5 | Note |` if it is missing. `rate` appends one row with
the user's note verbatim and confirms in one line. `improve` needs at least three rows: group the
rows scored 3 or less by what went wrong, propose one edit to this SKILL.md per group, and
change nothing until the user picks. Shipping an edit is a plugin release.

## Common mistakes

| Mistake | Instead |
|---|---|
| A check that has only ever passed | Plant a break and watch it fail (rule 1) |
| Expected values copied from the app's current output | Compute them from the inputs, or label the check as characterization |
| One runner that checks every feature on every commit | Map files to features; run touched features only |
| Naming the output `verify-<repo>` or adding `disable-model-invocation` | Exactly `verify`, model-invocable |
| Driving or seeding on a shared QA box | Local box or a database copy; shared boxes get doctor only |
| Editing the golden file because the check went red | Report the finding; update only with a cited intended change |
