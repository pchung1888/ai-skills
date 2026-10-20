---
name: personal-diagnosing-bugs
description: Use PROACTIVELY the moment something is wrong and the cause is not known - "the client says the page is broken", "wrong numbers", "error 50001", "it's not working", "the report is off", "why does this happen", "investigate this ticket", "it got slow after the deploy", a failing job or a stack trace. Covers ASP Classic, VB6, T-SQL and IIS, and any other stack. Builds a repeatable check that shows the bug before any theory (an HTTP request to the page, sqlcmd on the stored procedure, a cscript call to the DLL), then narrows it, ranks the causes, fixes it and proves the fix. Also /personal-diagnosing-bugs.
---

# Diagnosing Bugs

Adapted from Matt Pocock's `diagnosing-bugs` skill (MIT, see `THIRD-PARTY-NOTICES.md`). This
version adds feedback loops for ASP Classic, VB6 COM, T-SQL and IIS on Windows.

A discipline for hard bugs. Skip a phase only when you can say why.

When exploring the codebase, read `docs/glossary/GLOSSARY.md` if it exists, for the project's
terms. Check the decision notes under `docs/glossary/decisions/` in the area you touch.

## In your daily work

| You hear | Start here |
|---|---|
| "The Browse page shows the wrong rows for this client" | Phase 1, loop 2: request the page with the client's filter and assert on the row |
| "This stored procedure returns a wrong total" | Phase 1, loop 3: run it with `sqlcmd` and the reported inputs |
| "The DLL throws error 50001 on save" | Phase 1, loop 4: call the COM class from a `cscript` harness |
| "It only breaks on the client box" | Phase 1, loop 8: a person-in-the-loop script for the steps only they can do |
| "The page got slow after the deploy" | The performance branch in Phase 4: measure first |

On QA, DEV and client boxes, probes stay read-only. Get the owner's approval before adding
instrumentation, and back up any file before you change it.

## Redact

This skill shows commands, outputs and captured artifacts. Write `<REDACTED>` in place of every
password, connection-string credential and key. Build loops that read credentials from
environment variables, so the credential never appears in what you show.

If the redacted output is not enough to diagnose the bug, say so and ask the owner.

## Phase 1: Build a feedback loop

**This is the skill.** A tight pass/fail signal that goes red on this bug lets you find the cause.
Bisection, hypotheses and instrumentation all depend on it. Without one, reading code will not save you.

Spend most of your effort here. Be creative, and do not give up.

### Ways to build one, in roughly this order

1. **A failing test** at whatever seam reaches the bug, where the project has tests.
2. **An HTTP request to the page.** Send the same form fields the page posts, with
   `Invoke-WebRequest` or `curl.exe`, to the local IIS site. Assert on a string in the response.
3. **A `sqlcmd` call to the stored procedure** with the reported inputs, against the dev database.
   Assert on the returned row or total.
4. **A `cscript` harness for a VB6 COM class.** A small `.vbs` file runs
   `CreateObject("<ProgID>")`, calls the method with the reported inputs, and prints the result.
5. **Replay a captured request.** Take the request from the IIS log or a browser HAR file and
   send it again through loop 2.
6. **A differential loop.** Run the same input on DEV and QA, or on the old and new DLL build.
   Diff the outputs.
7. **A bisection harness.** If the bug appeared between two commits, automate "build, check,
   repeat" so `git bisect run` can drive it.
8. **A person-in-the-loop script.** Last resort, for steps only a person can do, such as RDP
   to a client box. Drive the person with `scripts/hitl-loop.template.ps1`, so the loop stays
   structured and the answers come back to you.

### Tighten the loop

Once you have a loop, make it faster, sharper and more deterministic. Narrow the request to
the one field that matters. Assert on the exact symptom, not "no error". Pin dates and test data.
A 30-second flaky loop is barely better than none. A 2-second deterministic loop is the goal.

### Bugs that come and go

The goal is a higher reproduction rate, not a clean repro. Loop the trigger 100 times, add load,
or narrow the timing window. A bug that fails half the time is debuggable. One that fails 1% is not.

### When you cannot build a loop

Stop and say so. List what you tried. Ask the owner for one of these: access to the machine
that reproduces it, a redacted capture (IIS log, HAR file, screen recording with times), or
permission to add temporary instrumentation on that box. Do not hypothesise without a loop.

### Done when: one command that goes red

Phase 1 is done when you can name **one command** that you have **already run at least once**.
Show the command and its redacted output. It must be:

- [ ] **Red-capable**: it drives the real bug path and checks the owner's exact symptom.
- [ ] **Deterministic**: same verdict every run, or a pinned high rate for a flaky bug.
- [ ] **Fast**: seconds, not minutes.
- [ ] **Agent-runnable**: you can run it alone; a person joins only through the HITL script.

If you catch yourself reading code to build a theory before this command exists, stop.
Jumping straight to a hypothesis is the exact failure this skill prevents.

## Phase 2: Reproduce and minimise

Run the loop and watch it go red. Confirm three things:

- [ ] It shows the failure the **owner** described, not a nearby different failure.
- [ ] It fails across several runs, or at a high enough rate.
- [ ] You captured the exact symptom: error number, wrong value or timing.

Then shrink the repro. Cut inputs, rows, config and steps one at a time, and re-run after each
cut. Keep only what the failure needs. Done when removing any remaining piece turns the loop green.

## Phase 3: Hypothesise

Write **3-5 ranked hypotheses** before testing any. One hypothesis anchors on the first idea.

Each must be falsifiable: "If <X> is the cause, then changing <Y> makes the bug go away."
If you cannot state the prediction, discard or sharpen it.

**Show the ranked list to the owner before testing.** The owner often knows something that
re-ranks it at once, such as "we changed that stored procedure last week". Do not block on an
answer when the owner is away.

## Phase 4: Instrument

Each probe tests one prediction from Phase 3. Change one thing at a time.

1. A debugger, where one exists (VB6 IDE, SSMS query plans).
2. Targeted logging at the boundaries that tell hypotheses apart.
3. Never "log everything and search".

Tag every debug line with a unique prefix, such as `[DEBUG-a4f2]`. In ASP that is a
`Response.Write` or a log write; in T-SQL a `PRINT`. Cleanup is then one search.

**Performance branch.** For a slow page, logs usually mislead. Measure a baseline first: page
timing, the query plan, `SET STATISTICS TIME ON`. Then bisect. Measure first, fix second.

## Phase 5: Fix and regression check

Write the regression check **before the fix**, if a correct seam exists. A correct seam runs
the real bug pattern as it happens at the call site. A check at a shallower seam gives false confidence.

If no correct seam exists, that is a finding. Write it down.

If one exists:

1. Turn the minimised repro into a failing check at that seam.
2. Watch it fail.
3. Apply the fix.
4. Watch it pass.
5. Re-run the Phase 1 loop against the original scenario.

## Phase 6: Cleanup

Before saying done:

- [ ] The original repro no longer fails (re-run the Phase 1 loop).
- [ ] The regression check passes, or the missing seam is written down.
- [ ] Every `[DEBUG-...]` line is gone (search for the prefix).
- [ ] Throwaway harnesses are deleted or moved to a clearly marked folder.
- [ ] The commit or PR message states which hypothesis was right, so the next debugger learns.
