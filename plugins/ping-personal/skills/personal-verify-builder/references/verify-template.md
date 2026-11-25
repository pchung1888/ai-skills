# Template for the generated `verify` skill

## Contents

- Folder layout and the `.gitignore` line
- `SKILL.md`: frontmatter, Pick what to run, Safety, Launch, Doctor, Run all checks, Features, Reading a
  failure, Evidence, Coverage and sync, Not covered
- `features/<feature>.md`: what the user sees, how to get to it, files, checks, proof it can
  fail, test oracle, formal candidate, gotchas

`create` writes these files into the target repo. Fill every part from what the survey found:
real commands, paths, selectors and procedure names. Leave no `<...>` placeholder behind.

```text
.claude/skills/verify/
  SKILL.md                 # the file below
  features/<feature>.md    # one per feature, shape below
  checks/                  # the runner and one script per check, in the repo's own language
  golden/                  # characterization files, if any
```

Add `.claude/verify-evidence/` to the repo's `.gitignore`. Evidence goes there.

## SKILL.md

The name must be exactly `verify` and the file must sit at the repo root's `.claude/skills/`.
Do not add `disable-model-invocation`. Claude Code runs a model-invocable project skill named
`verify` before each commit; either change silently turns that off.

````markdown
---
name: verify
description: Use before every commit that changes code in <repo name>, and when asked to /verify, /verify <feature> or /verify all. Runs this repo's runtime, database, property and mutation-proven checks for the features a change touches.
---

# Verify <repo name>

<One sentence: what the app is and which surface a user touches.>

## Pick what to run

- Before a commit, or `/verify` with no argument: run the features whose files the change
  touches. Get the changed files with `git diff --name-only HEAD` (staged and unstaged) plus
  `git ls-files --others --exclude-standard` (new files), and match them against the Files
  column below.
- `/verify <feature>`: that feature only. `/verify all`: every feature.
- If no feature matches, say "no mapped feature touched" and list the changed files.

## Safety

Drive features and plant bugs only against <the local instance and the database copy, by name>.
QA, DEV and client servers get Doctor and read-only checks only. If Doctor cannot show the
target is local or a copy, stop. Stop only processes this run started.

## Launch

<Exact command(s) that start the app from a clean state, the ready signal, and how to stop it.
Or: "Follow .claude/skills/run-<name>/SKILL.md" when /run-skill-generator recorded one.>

## Doctor

<One read-only command that says the instance is worth driving: process up, port owned by us,
right build, database reachable. Run it first, and again after any failed drive.>

## Run all checks

```<shell>
<one line, run from the repo root: launches what it needs, runs every check, stops what it
started, and exits 0 only if all pass>
```

`<same runner> --feature <name>` runs one feature.

## Features

| Feature | Files | Checks | Proof it can fail | Synced at |
|---|---|---|---|---|
| <name, links to features/<name>.md> | <globs> | <runtime / database / property> | <the planted change that turned it red> | <full sha from git rev-parse HEAD> |

## Reading a failure

1. Rerun the failing check once. A different result means a flaky check; say so.
2. Run Doctor. A Doctor failure is a broken prerequisite. Find its cause before blaming the
   environment: a change that breaks startup or the database connection fails Doctor too.
3. Read the diff of the evidence against the golden file or the expected value.
4. If the change was meant to alter that output, say so and ask before `--approve`.
   Otherwise it is a finding: report it with the steps to reproduce. Never weaken the check.

## Evidence

Write proof to `.claude/verify-evidence/<date>-<feature>/`. Cleanup stops only what this run
started and never deletes evidence.

## Coverage and sync

Each feature's "Synced at" is the commit at which its checks last matched the code. When a
feature's files change in ways this skill does not describe, run
`/personal-verify-builder maintain`. Move a feature's sha forward only after its checks were
rerun and still describe the code.

## Not covered

<What this skill does not check, and any formal candidates.>
````

## features/<feature>.md

````markdown
# <Feature name>

## What the user sees
<One or two sentences, in the user's words.>

## How to get to it
<URL, menu path, command, or endpoint.>

## Files
<globs, including shared includes and stored procedures the feature calls>

## Checks
| Check | Layer | Command | Passes when |
|---|---|---|---|

## Proof it can fail
<For each check: the planted change, the check's own assertion message from the red run (not a
crash or import error), and the green rerun after revert.>

## Test oracle
<Who or what says the output is right, or "none: golden file records today's behavior">

## Formal candidate
<Only if the feature has retries, timeouts, concurrent users or a state flow: the rule that
must always hold, in one sentence. Otherwise omit this section.>

## Gotchas
<Preconditions the seed data lacks, login needs, timing traps.>
````
