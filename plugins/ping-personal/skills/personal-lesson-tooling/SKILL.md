---
name: personal-lesson-tooling
model: haiku
description: Tooling / process lessons -- git workflow, GitHub CLI, worktrees, hooks, settings.json, agent dispatch, multi-agent coordination, PowerShell patterns, Windows shell gotchas, commit conventions, subagent cost discipline. Invoked by personal-lesson master router when classification matches tooling keywords OR as the zero-hit fallback for any lesson that doesn't match another domain. Also triggered directly via /personal-lesson-tooling or natural phrases like "lessons about git", "lessons about tooling", "lessons about agents", "lessons about hooks", "lessons about PowerShell". Appends new lessons to ~/.claude/lessons/personal-lesson-tooling.md and reads from there for browse mode.
user_invocable: true
---

# /personal-lesson-tooling -- Tooling / Process Lessons

Lessons about the development toolchain: git workflow, GitHub CLI, worktrees,
agent dispatch, multi-agent coordination, PowerShell and Windows shell patterns,
commit conventions, hooks, and settings.json configuration. This is also the
catch-all domain -- any lesson that does not match a more specific domain lands
here.

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

Grep BOTH sources for a distinctive phrase from the incoming lesson (a command
name, an error string, a 5-word snippet of the Rule):

1. `~/.claude/lessons/personal-lesson-tooling.md` (user-scope appends, skip if absent)
2. The `## Seed Lessons` section of THIS file (`personal-lesson-tooling/SKILL.md`)

If either matches, reply:

> Duplicate: already recorded as "<existing title>" in personal-lesson-tooling.
> Nothing appended.

Then STOP.

### Step 2 -- Append

Use Edit (or Write if the file does not exist) to append before the end of
`~/.claude/lessons/personal-lesson-tooling.md`, using the standard format:

```markdown
---

## [SEVERITY] [Short Title]
**Domain:** tooling
**Discovered:** [YYYY-MM in America/New_York -- never UTC]
**Context:** [1-2 sentences -- when this surfaced]
**Problem:** [What goes wrong without this knowledge]
**Rule:** [Actionable imperative -- concrete thing to do or avoid]
**Example:** [Optional: wrong vs right snippet, error message, or file reference]
```

Create `~/.claude/lessons/personal-lesson-tooling.md` if absent. The file should
begin with a brief one-line header on creation:
`# Lessons -- Tooling / Process (user-scope, auto-appended)`

After appending, confirm: "Appended to ~/.claude/lessons/personal-lesson-tooling.md."

---

## Browse mode

When asked "show me tooling lessons" or "lessons about <topic> in tooling":
1. Read `~/.claude/lessons/personal-lesson-tooling.md` if it exists.
2. Also read the Seed Lessons section below.
3. Search for the user's term across both sources.
4. Quote lesson text verbatim -- do not paraphrase.

---

## Seed Lessons

The lessons below are cross-project reference seeds. They record patterns that
recur across all projects on this toolchain.

---

## NOTE Sub-Agents Cannot Spawn Child Agents -- Only the Parent Session Can Dispatch
**Domain:** tooling
**Discovered:** 2026-04
**Context:** A coordinator sub-agent (Amanda) was expected to dispatch further
sub-agents (Bunny, Maggie, etc.) from within her own sub-agent shell. At runtime
the Task / Agent tool was not available inside the sub-agent.
**Problem:** A sub-agent that tries to dispatch child agents silently fails to do
so -- no error is raised, but no child agent is spawned. The parent session
receives a plan but no implementations.
**Rule:** The Agent / Task tool is available ONLY in the parent (top-level) session.
Sub-agents cannot re-dispatch. The correct pattern: the coordinator sub-agent
writes the briefs and returns a numbered dispatch list; the parent session executes
the dispatches directly.
**How to apply:** When designing a multi-agent pipeline, ensure all `Skill()` and
`Agent()` calls that spawn workers are issued from the parent context, not from
inside a sub-agent.

---

## CAUTION Git Worktrees Are Siblings, Never Children of the Repo
**Domain:** tooling
**Discovered:** 2026-03
**Context:** Creating a git worktree during a development session. The worktree
was placed inside the main repo directory.
**Problem:** A worktree created inside the repo directory appears as untracked
content in the parent -- git becomes confused about what is tracked vs. what
is an untracked worktree directory.
**Rule:** Always place git worktrees as sibling directories to the main repo
(e.g. `D:\playground\project\project-worktree`), never inside the repo directory
itself. Run `git worktree list` to verify placement after creation.

---

## NEVER Write Tool Always Replaces Entire File -- Only Use When You Have Full Content
**Domain:** tooling
**Discovered:** 2026-04
**Context:** A script snippet was used with the Write tool to update one section
of a 300-line file. The Write call contained only the snippet, not the full file.
**Problem:** The Write tool always replaces the ENTIRE file with whatever content
is passed. Passing partial content silently deletes everything else. No warning
is given.
**Rule:** Only use the Write tool when you have the complete file content. For
partial changes, always use Edit (targeted replacement). Before using Write on
an existing file, confirm you have read the current full content.

---

## NEVER All Timestamps in Artifacts Must Use EST/EDT (America/New_York), Never UTC
**Domain:** tooling
**Discovered:** 2026-04
**Context:** Skills generating screenshots, log files, and test artifacts were
using UTC timestamps in their filenames and log entries.
**Problem:** UTC timestamps in artifacts desynchronize from EST/EDT audit logs,
making traceability impossible during audits. Artifacts from "2026-05-01T04:00Z"
are actually from the evening of 2026-04-30 in New York time -- a cross-day
mismatch that breaks chronological ordering of mixed-timezone artifacts.
**Rule:** ALL timestamps and filenames in skills, tests, and audit artifacts MUST
use EST/EDT (`America/New_York`). UTC is prohibited. In JS:
`(new Date()).toLocaleString('en-US', { timeZone: 'America/New_York' })`.

---

## CAUTION Subagent "Completed" Status Does Not Guarantee the Artifact Was Produced
**Domain:** tooling
**Discovered:** 2026-05
**Context:** Four parallel sub-agents were dispatched to write chunk files. Three
files landed on disk; one agent returned "completed" status but no file appeared.
The agent had burned its turn budget reading specs and cross-checking but never
reached the Write call.
**Problem:** The runtime marks an agent "completed" when it ends its turn budget,
NOT when it produces the requested output. An agent can claim success in its
final message without having written the file. Trusting "completed" without
verifying the artifact causes doubled cost (re-dispatch) and lost time.
**Rule:** After any sub-agent dispatch that is supposed to produce an artifact
(file write, DB insert, etc.), verify the artifact's existence on disk BEFORE
treating the dispatch as successful. Use a deterministic post-check:
`ls <expected-path>`, `git diff --name-only HEAD`, or equivalent. Do not trust
the agent's reply text either.
**Preventive pattern:** Embed an "EFFICIENCY DIRECTIVE -- write before you reply"
block in the agent's prompt so it treats the Write call as the first gate, not
the last.

---

## NEVER Windows Desktop Heap Exhaustion Freezes the Machine -- Not a RAM Problem
**Domain:** tooling
**Discovered:** 2026-05
**Context:** A Windows 11 dev box (64 GB RAM, IIS + SQL Server running) froze
mid-agent-dispatch. Symptoms: many short-lived `bash.exe` processes, `git-
credential-manager.exe` crashing with `Process.Start` exceptions, DCOM timeout
storms, UI freezing despite free RAM.
**Problem:** Each interactive Windows process (including headless `bash.exe`)
consumes a slice of the fixed-size kernel desktop heap pool. The default 20 MB
pool is sized for 2003-era workloads, not 2026-era multi-agent automation that
spawns hundreds of short-lived shells per minute. The machine froze; all in-
flight agent context was lost. Only on-disk artifacts survived.
**Rule:** Before dispatching parallel sub-agents, check the parallel-count budget
per `~/.claude/CLAUDE.md §Process Budget Discipline`. Halve the thresholds when
another Claude session is running concurrently. Prefer `Glob`/`Grep` (in-process)
over `Bash`+`rg`/`find` (spawns child shells). Batch related shell ops into a
single Bash call with `;`/`&&` rather than separate Bash tool calls.
**Related:** User-scope `~/.claude/CLAUDE.md §Process Budget Discipline`.

---

## CAUTION Durable Handoff Docs Are the Only Reliable Crash Recovery Vector
**Domain:** tooling
**Discovered:** 2026-05
**Context:** A machine freeze mid-dispatch wiped all in-flight conversational
context. The only recovery path was a handoff doc written before the crash.
**Problem:** LLM conversational context is volatile. A crash, /clear, window
close, or context compaction silently destroys all in-flight knowledge. Without
a durable on-disk artifact, the next session cannot verify what is done vs.
what was claimed-but-not-done. Under auto-mode, the temptation is to skip the
handoff write "until the end" -- but the end may never arrive.
**Rule:** Write a `docs/progress/YYYY-MM-DD-<task>-handoff.md` BEFORE dispatching
any work that meets ANY of: (a) 3+ Agent dispatches, (b) work touching files the
parent cannot trivially `git diff` to understand, (c) dispatch expected to run
longer than 5 minutes wall-clock time. The handoff must include: expected
`git status` state, expected file table (path + size), step-by-step resume plan
with sub-agent dispatches named, hard constraints, and done-ness criteria.
**Example:** Session recovery succeeded because a pre-crash handoff doc included
HEAD hash, expected file table, npm/tsc/audit step plan, and 8 done-ness
checkboxes. Cold-start session executed the plan in one pass.

---

## CAUTION Multi-Line PowerShell String Args Fragment Across `pwsh -File` Process Boundary
**Domain:** tooling
**Discovered:** 2026-05
**Context:** A PowerShell wrapper taking a `[string]$Body` parameter was invoked
via `pwsh -File .\wrapper.ps1 -Body $multilineVar` from a parent PS session. The
wrapper reported "Missing an argument for parameter 'Body'" even though the
variable was populated.
**Problem:** Two boundary failures conspire: (1) a snippet with PowerShell backtick
line-continuations pasted into a Bash tool invocation is misparse -- Bash treats
backtick as command substitution; (2) when one `pwsh` invokes another via
`-File <script> -Param $var`, multi-line string values get split at line breaks
across OS argv entries -- the binder sees the post-newline fragment as a separate
token and reports the parameter as missing.
**Rule:** When invoking a PowerShell wrapper that takes multi-line string params,
use the in-process call operator `& .\script.ps1 -Param $var` instead of the
child-process pattern `pwsh -File .\script.ps1 -Param $var`. The call operator
keeps the variable as a single in-memory string; no argv fragmentation. Reserve
`pwsh -File` for simple scalar args (booleans, integers, short single-line strings).
When documenting the invocation in a SKILL.md, label the snippet "Invoke via the
PowerShell tool, NOT Bash."

---

## CAUTION Parallelize for Scope Isolation, Not for Speed
**Domain:** tooling
**Discovered:** 2026-03
**Context:** Refactoring a skill into 3 parallel agents to run faster. Each agent
loaded its own copy of the same shared context files.
**Problem:** Each parallel agent loads its own context window with the same shared
files (CLAUDE.md, docs, lessons). A 3-agent run used 3x the tokens of a single-
session run with identical output. Parallelism multiplied cost, not throughput.
**Rule:** Default to single-session sequential execution. Only parallelize when
wall-clock time is genuinely the bottleneck AND the token budget is not a concern.
Always verify the parallelism actually reduces wall-clock time for the specific
task before committing to the pattern.

---

## CAUTION Dispatch a Critique Sub-Agent Before Executing Any Significant Plan
**Domain:** tooling
**Discovered:** 2026-03
**Context:** A plan with factual errors was executed without a critique step. The
errors propagated into implementation and required rework.
**Problem:** Plan authors have blind spots. A critique step catches errors before
they propagate into implementation.
**Rule:** Before executing any plan that touches multiple files or systems, dispatch
a critic (Ms.Mario or equivalent) with the plan as input. Only proceed after the
critique passes or its findings are resolved.
