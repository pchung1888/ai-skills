---
name: personal-lesson-data
model: haiku
description: Data-boundary lessons -- read-only data sources, file path encoding, secrets/env handling, gitignore contracts, data schema boundaries. Any project's "thou shalt not write here" perimeter and related data contract lessons. Invoked by personal-lesson master router when classification matches data keywords, or directly via /personal-lesson-data or natural phrases like "lessons about data", "lessons about vault", "lessons about file paths", "lessons about secrets", "lessons about env". Appends new lessons to ~/.claude/lessons/personal-lesson-data.md and reads from there for browse mode.
user_invocable: true
---

# /personal-lesson-data -- Data Boundary Lessons

Lessons about where data lives, what is read-only, how path encoding works,
what must stay out of git, and how to handle secrets, env files, and data
contracts. Applies to any project that has a "thou shalt not write here"
perimeter around its data sources.

---

## Capture flow (invoked by master router or directly)

### Step 0 -- Hard-rule gate (when invoked directly)

If invoked directly (not via the master router), check CLAUDE.md and
.claude/rules/*.md for hard rules that the incoming lesson would duplicate. If
the lesson IS a duplicate of a hard rule, reply:

> This is already a hard rule in CLAUDE.md / .claude/rules/. Nothing appended.

Then STOP. If invoked via the master router, skip Step 0 (the router already
ran it).

### Step 1 -- Duplicate check

Grep BOTH sources for a distinctive phrase from the incoming lesson (a file
path pattern, an env var name, a 5-word snippet of the Rule):

1. `~/.claude/lessons/personal-lesson-data.md` (user-scope appends, skip if absent)
2. The `## Seed Lessons` section of THIS file (`personal-lesson-data/SKILL.md`)

If either matches, reply:

> Duplicate: already recorded as "<existing title>" in personal-lesson-data.
> Nothing appended.

Then STOP.

### Step 2 -- Append

Use Edit (or Write if the file does not exist) to append before the end of
`~/.claude/lessons/personal-lesson-data.md`, using the standard format:

```markdown
---

## [SEVERITY] [Short Title]
**Domain:** data
**Discovered:** [YYYY-MM in America/New_York -- never UTC]
**Context:** [1-2 sentences -- when this surfaced]
**Problem:** [What goes wrong without this knowledge]
**Rule:** [Actionable imperative -- concrete thing to do or avoid]
**Example:** [Optional: wrong vs right snippet, error message, or file reference]
```

Create `~/.claude/lessons/personal-lesson-data.md` if absent. The file should
begin with a brief one-line header on creation:
`# Lessons -- Data Boundary (user-scope, auto-appended)`

After appending, confirm: "Appended to ~/.claude/lessons/personal-lesson-data.md."

---

## Browse mode

When asked "show me data lessons" or "lessons about <topic> in data handling":
1. Read `~/.claude/lessons/personal-lesson-data.md` if it exists.
2. Also read the Seed Lessons section below.
3. Search for the user's term across both sources.
4. Quote lesson text verbatim -- do not paraphrase.

---

## Seed Lessons

The lessons below are cross-project reference seeds. They record patterns that
recur whenever a project has read-only data sources, env-managed secrets, or
strict data-boundary contracts.

---

## NEVER Keep Sensitive Artifacts Local-Only and Untracked
**Domain:** data
**Discovered:** 2026-04
**Context:** Reviewing the boundary between a read-only data source and generated
workflow artifacts. The distinction between "source I read" and "output I write"
was not explicit in the project's gitignore or documented contract.
**Problem:** Sensitive generated artifacts (canonical exports, staged CSV outputs,
backups, generated data bundles) can be accidentally committed, synced to the
wrong location, or written back into the read-only source if the boundary is not
explicit and enforced by gitignore.
**Rule:** Keep all sensitive derived artifacts gitignored and local-only. Treat
the read-only data source (OneDrive folder, mounted drive, external API, upstream
repo) as read-only input only -- never write back to it. Verify that derived
output paths are not git-tracked before finishing any data pipeline run.
**Example:** Wrong: commit generated data bundles or canonical CSVs. Right: read
from the read-only source, write derived artifacts only to approved local
gitignored paths, and confirm those paths are not tracked with `git status`.

---

## CAUTION Non-ASCII Path Components Require Explicit Encoding Handling
**Domain:** data
**Discovered:** 2026-04
**Context:** A data source path contained non-ASCII characters (e.g. Chinese or
accented characters in a folder name) on a Windows machine. Scripts and tools
that constructed the path dynamically or read it from environment variables
failed intermittently depending on the terminal encoding and PowerShell version.
**Problem:** On Windows, `powershell.exe` (5.1) defaults to Windows-1252 encoding
when reading UTF-8 files without a BOM. A path like `C:\Users\user\OneDrive\...\`
with a Chinese character in a segment reads correctly in a UTF-8 terminal but
silently corrupts in a CP1252 context, producing a path that does not resolve.
**Rule:** When any path component may contain non-ASCII characters, either:
(a) read the path from an env var set in a UTF-8-aware context (the env var
stores a byte sequence, not text), or
(b) use the raw Win32 path API (`\\?\` prefix or `[System.IO.Directory]`) which
bypasses the text encoding layer, or
(c) rename the path component to ASCII-safe if you control it.
Never hard-code the non-ASCII segment as a string literal in a script file --
it will break when the file is opened by a tool with a different encoding.

---

## CAUTION Env Files Must Be Excluded From Every Output Path and Git Tree
**Domain:** data
**Discovered:** 2026-04
**Context:** Adding a new build step that wrote output to a directory. The
directory happened to be adjacent to where `.env.local` and `.env.production`
lived, and a glob pattern picked them up during a "clean artifacts" sweep.
**Problem:** An overly broad clean or copy operation can silently delete or
export `.env*` files. Committing them leaks secrets; deleting them breaks the
dev environment. The failure may not surface immediately if env vars are cached
in the shell.
**Rule:** In every script or pipeline that reads from or writes to project
directories: (a) explicitly exclude `*.env*`, `.env`, `.env.*` from globs,
(b) add `.env*` to .gitignore if not already present, and (c) verify with
`git status` that no `.env` files are staged before any commit.
**Example:** A clean-artifacts script should use `Get-ChildItem -Exclude '.env*'`
or equivalent -- not `Remove-Item *.*` or a bare glob.
