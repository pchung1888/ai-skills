---
name: personal-critic-judge
description: Use when the user asks for a judged review of a plan, diff, skill or step output before it ships - /personal-critic-judge, "judge review", "critic judge this" - or when personal-workflow, personal-goal, personal-loop or personal-big-project reaches a review step. Five reviewers find problems from different angles, then one judge rules on every finding against the user's main goal and the subtask under review, and only the real, in-scope "fix now" findings get fixed. Not the vote-based personal-critic-gate.
---

# Critic judge

Reviewers find problems. A judge decides what matters. The driver fixes only what the judge rules
"fix now". This stops a correct but unwanted finding from turning into work the user never asked for.

## Inputs

Every run needs these four. Quote the user's words for the first one, do not summarise them.

| Input | Meaning | Example |
|---|---|---|
| Main goal | The user's ultimate requirement | "a new skill to talk this way for a session when I ask for it" |
| Subtask | The piece under review now | "step 5: the parser change", or "the whole skill" |
| Review purpose | Why this review happens now | "check logic and security before step 6 builds on it" |
| Artifact | What to review | a file path, `current diff`, or pasted text |

A caller skill may also pass `UNATTENDED` (see "Unattended runs").

If the Main goal or the Subtask is missing, stop and ask the user in one line. Never guess them.

## Before dispatch

1. Say the cost. Full run: 5 seats plus the judge, about 435K tokens (measured on a past ticket: 434,654
   tokens, 6 agents, 334 s). Light run (seats 1, 2 and 5 plus the judge, for a small subtask):
   about 290K. Seat 5 is in every run: on a past ticket it alone found every "fix now" finding.
2. For a diff, run `python plugins/ping-personal/skills/personal-critic-gate/lib/floor_guard.py --base <ref>`
   and keep its rows for every brief. Record the reviewed commit as `Reviewed: <sha>`.
3. Pick seat 3, the domain seat, with personal-critic-gate's "Seat 4 Domain Routing Table": vex
   for data work (`.sql`, parser, csv, migration script), maggie for design and UI, vex when
   mixed. Use that table, do not copy it, so the two skills cannot drift.
4. Pick seat 5. Run the codex probe from personal-critic-gate's "Preflight Codex Probe" section.
   If it passes, seat 5 is codex. If not, seat 5 is iris.
5. Write the run header: date, artifact, `Reviewed: <sha>`, floor guard result, the domain seat
   with the keyword that picked it, and seat 5's agent.

## The seats

Each seat works alone and never sees another seat's findings. Dispatch them in one message. When
the caller caps parallel agents, dispatch them one after another instead.

| Seat | Lens | Agent |
|---|---|---|
| 1 | Adversarial critic: defects, contradictions, what breaks | ms-mario |
| 2 | Intent: does this serve the Main goal and this Subtask | amanda |
| 3 | Domain seat: data shape and SQL safety (vex), or design and reuse (maggie) | vex or maggie |
| 4 | Security and test coverage | rhea |
| 5 | Fresh outsider, claim-blind | codex (`--fresh` prompt, via the Agent tool) or iris |

Seat 5 is claim-blind: it gets only the artifact, the Subtask and a one-line scope in your own
words. It never gets your summary or your claims ("I fixed X, tests pass"). The user's exact words
never go to codex.

Seat brief (seats 1-4 get the Main goal verbatim, seat 5 gets your one-line scope):

```text
MAIN GOAL: <the user's words>
SUBTASK: <the piece under review>
REVIEW PURPOSE: <why now>
YOUR LENS: <the seat's lens from the table>
ARTIFACT: <path, diff or text>
FLOOR GUARD ROWS: <rows, or "none">
Review only. Do not edit anything. Do not vote.
Write your findings in English, ASCII only. No emoji, no box drawing.
Return a list of findings. Each finding has: a short title, severity (high, medium or low),
evidence (file:line or quoted output), and which input it serves (main goal, subtask or neither).
```

Seats return findings only. A seat that ends with a vote or a verdict is fine, but the judge
ignores it.

## The judge

The judge is a fresh general-purpose agent. It did not review and did not write the work. You do
not judge: you wrote the work and lean toward your own fixes.

Judge brief:

```text
You are the judge. You did not write or review this work.
MAIN GOAL: <the user's words>   SUBTASK: <...>   REVIEW PURPOSE: <...>
ARTIFACT: <path, diff or text>
FINDINGS: <all five seats' lists, labelled by seat>
Rules:
1. Merge duplicate findings. Two seats raising one finding is a signal, not a vote.
2. For each finding decide:
   Real? yes, or no (false alarm, already handled, or a wrong reading of the artifact).
   In scope? yes only if it matters for this Subtask AND serves the Main goal.
   When? fix now, later, later - flagged for the owner, or never.
   Why: one line.
3. fix now only when Real is yes, In scope is yes, and the fix closes the defect without adding
   new behavior. A guard, check or test that closes a real defect is fine. A fix that gives the
   work a new capability (a feature, rule or section the Main goal does not ask for) is later.
4. Safety floor: a leaked secret, data loss, a security hole, or a deleted or skipped test starts
   its Finding cell with [floor] and is never "never". In the changed work it is fix now.
   Otherwise it is "later - flagged for the owner" and goes at the top of the table.
5. Check before you rule. Before fix now or later - flagged for the owner, open the cited file and line
   yourself and write EXTRACTED and what you saw in Why. Before you call anything unknown, run one
   cheap probe (read, grep, git blame, git diff). If the probe cannot answer: Real is no, When is
   later - flagged for the owner, and Why starts with UNKNOWN and names what would answer it.
6. When a [floor] row's real-world size depends on volume, size or frequency, name in Why the one
   sizing probe that would measure it (a query, a log count). Run it if you can.
7. Real and In scope hold exactly yes or no. Evidence goes in Why. Never put a pipe character
   inside a cell.
8. Return only this, every finding in the table, rejected ones too. The first line is the verdict:
VERDICT: FIX (<n> fix now, <n> flagged, <n> later, <n> never)   or   VERDICT: CLEAN (0 fix now, ...)
| # | Finding | Seats | Real | In scope | When | Why |
|---|---|---|---|---|---|---|
```

## After the judge

1. Fix every "fix now" row. Fix nothing else.
2. Send the same judge one verify pass on the fixed rows only: "For each fixed row, did the fix
   close the finding, and did it change anything outside it?" A failed row goes back to "later"
   with a note. The verify pass finds nothing new. That is its whole job.
3. Show the user the verdict line, the final table, the list of fixes made, and any
   "later - flagged for the owner" rows first.
4. There is no second panel. If the user wants another review, they run the skill again.

To check a judge table by hand: `pwsh plugins/ping-personal/skills/personal-critic-judge/evals/eval.ps1 -TableFile <table.md>`.

## Saving the run

Save the header, the verdict, the table and each seat's text verbatim. Never replace or strip
characters to make a file ASCII. If non-ASCII text remains, stop and ask the user how to save it.

## Unattended runs

A caller skill (personal-workflow, personal-goal, personal-loop, personal-big-project) passes
`UNATTENDED` when the user is away. Then:

- The caller supplies the inputs: the Main goal from the beacon goal or GOAL-BRIEF.md, quoted.
  Never stop to ask. With no goal text at all, do not run: report the review as not run.
- Fix now rows are fixed and verified as above.
- "later - flagged for the owner" rows go to the caller's owner list (OWNER-REPORT.md, the beacon,
  or the handoff), never into a question.
- The caller reads the VERDICT line. A stale `Reviewed: <sha>` (not HEAD) is not a pass.

## Not for

- A vote between options: retry, defer or stop on a failed item, or picking a recovery path
  when blocked. That stays with personal-critic-gate.
- Brainstorming critique mid-design. Dispatch ms-mario directly.
