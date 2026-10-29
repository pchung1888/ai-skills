# Reporter briefs

## Tick report (fresh background agent, each tick where run-log changed)

The tick adds two lines to this brief: "Now: <Day MM-DD HH:MM>" (the reporter has no shell, so
this is her clock) and "Report shape: <shape>" (from inputs.json "report", chosen by the user at start).

```text
Read <STATE_DIR>/STATUS.md (its Tasks section is the task table), the last 40 lines of
log/run-log.md, the last 3 lines of log/quota-log.md, and the previous report.
Write <STATE_DIR>/reports/<YYYY-MM-DD-HHMM>.md, named from the "Now:" line; use that time for "now"
and never guess a time. Follow the "Report shape:" line (shapes below). Plain shape, max 12 lines: what is being worked on now,
what finished since the last report (do not repeat it), what went wrong and how it is handled,
whether work is paused to save usage and when it resumes (day and date), what comes next, and
any decision taken without the owner (with how to reverse it).
Use the words in glossary.md (in the same folder as this brief) and no others for the same ideas; no codes,
stage or task ids, decision ids, hashes, line numbers or agent names; explain any unavoidable
technical word in the same sentence.
Finish estimates only from measured durations in run-log.md, with the basis stated.
Return the report text only.
```
<!-- <STATE_DIR> Example: docs/proj-123/autopilot -->

Report shapes (the user picks one at start step 1; plain is the default):

- **plain:** the 12-line report above.
- **copilot:** for a short weekday run that the user follows on their phone. Before writing, call the
  Skill tool with `ping-personal:personal-copilot-talk` and follow its "The words" and "Special
  cases" sections. Write like a junior developer reporting to a manager, as a stack of short
  blocks, each with a bold heading and a `---` line between blocks: **Since the last report**
  (what finished, with its proof), **Now** (what runs and what it does, in one or two sentences),
  **Why** (only when a choice was made without the user, with how to reverse it), **Next** (what comes
  after this). Leave out the skill's "Step N" and "Tell me" blocks: the user is never asked anything.
  If the Skill call fails, write the plain shape and start the report with the line
  "copilot talk did not load: <error>", so the coordinator logs it in log/skill-friction.md.
- **with the full task list:** after the other lines, every row of the STATUS.md Tasks section in
  phone shape: one line per task, no table, status first. Example:
  `[done] Fix invoice rounding - Fri 10-16 19:40 to 19:52`. Keep the ADDED remark on added tasks.
- **task ids allowed:** task ids may appear in the text (check_run then skips its report-plain check).
  Hashes, run ids and agent names stay out.

## Task table contract (the Tasks section of `<STATE_DIR>/STATUS.md`)

STATUS.md is the owner's one status file; there is no separate progress file.
`scripts/build_table.py` enforces this contract and rewrites only the lines between
`<!-- tasks:begin ... -->` and `<!-- tasks:end -->`; the reporter reads the table, it never writes it.

- One table, every planned task from start to end, including tasks not started yet.
- Columns: #, stage, task id, what it does, status, started, finished, tokens used, token estimate, notes.
- Status comes from run-state.json outcomes: Done, Deferred (agent), Deferred (owner), Failed, Not run.
- Per-item work shows (x/N) in status, not item names.
- Unplanned work gets a new row with the remark `ADDED Day MM-DD HH:MM - why` and a line under
  "Added along the way".
- Every date-time is `Day MM-DD HH:MM` local; a day key sits at the top.
- An unknown number is written "don't know". Rows are never deleted or reordered.
- A "Task details" section maps each task id to its plan section, live log and results path.

## OWNER-REPORT.md (written at FINAL or STOP; check_run checks its shape)

```text
# <goal> - owner report
Verdict: <the exact line from run_state.py record final>

## What changed
<5-10 plain lines: what now works that did not before; what was deferred and what the user must decide>

## Evidence
<per shipped change: the check that proves it, its output before the run and after, with paths>

## Merge danger
Overall: <one-way door | two-way door> - <one sentence why>
<per shipped change: one-way or two-way door (can it be reverted cheaply?) and blast radius (who or
what is affected if it is wrong)>

## Judge review
<the judge's VERDICT line and Reviewed: <sha>; each fix-now row and its fix; each row flagged for the owner>

## Deferred items
<each: what failed, root cause so far, what the user must provide, how to resume>

Run /personal-big-project retro <state-dir> to rate this run.
```
A two-way door is a change that can be reverted cheaply; a one-way door touches the world (data,
mail, a deploy, a published package) and is expensive to undo. Small radius on a two-way door needs
a light review; a one-way door needs the user's eyes first.

## Boss report (only on request)

```text
Report as if to a boss who knows we use AI as a senior developer that has run N hours.
Plain words, one page, readable in 2 minutes on a phone. Points or a table are fine.
No decision ids, test numbers or file references. Do not stop or pause any working agent.
Give an independent finish estimate from measured durations, not the last estimate.
```

On request also: an HTML timeline Artifact (10-15 key points, to-scale chart), a 30-second motion
version (film-maker agent), and a post of both links to the owner's Slack channel. Offer these in
one line in OWNER-REPORT.md.
