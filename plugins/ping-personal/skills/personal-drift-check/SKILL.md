---
name: personal-drift-check
model: haiku
description: Measure harness drift -- whether this session (or a cohort of past sessions) has stopped gathering evidence and stopped behaving like the skill that was invoked. Parses Claude Code JSONL transcripts and reports evidence share, skill-attribution share, and the decay curve across the session, calibrated against a known-good baseline. TRIGGER on "/personal-drift-check", "am I drifting", "check drift", "harness drift", "did the skill stop working", "why did you stop reading files", "am I still following the skill", "measure my evidence share", or when a session has run long and you want to know whether discipline is still live before trusting its conclusions.
---

# /personal-drift-check

Answers one question with a number: **is this session still looking at
reality, or has it started asserting from memory?**

Harness drift is the measured phenomenon that a session progressively stops
using evidence tools and stops behaving like the skill it invoked -- with no
user action, no interruption, and no context compaction. The full analysis is
in `docs/harness-drift/` in the personal-plugin repo.

## Why this skill exists

Every other guardrail in this stack is a *brake*: a rule, a gate, a critic. A
brake you cannot read is a brake you cannot trust. This is the *gauge*. It
came first for a reason -- without it there is no way to tell whether any of
the brakes work, and no way to notice drift while it is happening rather than
after a wrong answer has already been delivered.

## The two signals

| Signal | What it is | Behaviour |
|---|---|---|
| **Evidence share** | Read+Grep+Glob as a share of work-tool calls | **Leading.** Collapses first. This is the one that matters. |
| **Attribution share** | Calls the harness still stamps with `attributionSkill` | **Lagging.** Stays at 100% for roughly one decile after the behaviour is already gone. |

Reading them together is the whole trick. In the measured session `e855ab40`,
evidence share fell from 43.3% to 3.3% between decile 1 and decile 2 **while
attribution was still 100%**. The harness was still crediting every call to
`/personal-goal` at the exact moment the goal's discipline stopped being
followed. Waiting for attribution to drop means noticing one decile late.

**Do not treat attribution as the health check.** It measures bookkeeping, not
behaviour.

## How to run

Current project, most recent session:

```powershell
pwsh -NoProfile -File "${CLAUDE_PLUGIN_ROOT}/skills/personal-drift-check/drift-check.ps1"
```

A specific past session:

```powershell
pwsh -NoProfile -File "${CLAUDE_PLUGIN_ROOT}/skills/personal-drift-check/drift-check.ps1" -SessionFile "<path>.jsonl"
```

A cohort (comma-separated wildcards -- call the script directly, not via
`-File`, because `-File` passes arguments verbatim and will not bind an array):

```powershell
& "${CLAUDE_PLUGIN_ROOT}/skills/personal-drift-check/drift-check.ps1" -Cohort "<dir>\aaaa*.jsonl","<dir>\bbbb*.jsonl"
```

Machine-readable, for a loop tick or a hook:

```powershell
pwsh -NoProfile -File "${CLAUDE_PLUGIN_ROOT}/skills/personal-drift-check/drift-check.ps1" -Json
```

## Reading the output

| Evidence share | Verdict | Meaning |
|---|---|---|
| >= 30% | HEALTHY | At or above the measured good-session baseline. |
| 20-29% | WATCH | Below baseline, above the drifted window. |
| 10-19% | DRIFTED | Matches the measured problem window. |
| < 10% | SEVERE | The session is acting almost without looking. |

The **CLIFF** line is the most actionable output. It names the part of the
session where evidence share fell below a third of its opening value, and the
approximate tool-call number where that happened. In the measured sessions the
cliff lands around **tool call 30**.

## What to do when it says DRIFTED or SEVERE

In this order:

1. **Do not trust this session's unverified factual claims.** Anything asserted
   about how the system works, made after the cliff and not backed by a
   `file:line` or a quoted command output, is suspect. Re-probe before acting.
2. **Re-probe the load-bearing claims specifically.** Not all of them -- the
   ones a decision rests on.
3. **Delegate the next sweep.** A subagent starts at decile 1 with a fresh
   context; the main session is past its cliff and will not recover on its own.
4. **Do not simply re-type the skill name.** Measured: the originating skill was
   re-invoked exactly once across four sessions and it did not restore
   evidence share. Re-invocation is not the fix.

## Calibration and honest limits

- The denominator is the seven work tools (Read, Grep, Glob, Edit, Write, Bash,
  PowerShell). Meta/UI calls, MCP calls, and `Agent` are excluded -- they are
  not a choice between looking and acting. `Agent` is reported separately so
  that delegating never reads as a drop in evidence share.
- This definition is calibrated to reproduce the published baseline exactly:
  BASELINE 144/375 = 38.4%, RECENT 78/733 = 10.6%. If a future change to this
  script stops reproducing those two figures, the change is wrong.
- **Evidence share is a proxy, not a virtue.** A session legitimately doing a
  long mechanical edit run will score low without drifting. Read the verdict
  alongside what the session was actually doing. The cliff shape -- high then
  suddenly flat -- is more diagnostic than the absolute number.
- Subagent turns are excluded. On CLI 2.1.224 they do not appear in the project
  transcript at all (`isSidechain` is never true), so the filter is currently a
  no-op guard against a future build change.
- The script reads only local transcripts. It cannot see a session still in
  flight beyond what has already been flushed to the JSONL.

## Related

- `/personal-cache-stats` -- sibling skill, same transcript-parsing shape,
  measures prompt-cache reuse instead of behaviour.
- `/personal-facts-check` -- what to run once this skill tells you the session
  stopped verifying.
- `docs/harness-drift/` in the personal-plugin repo -- the analysis, the
  measured cohorts, and the remediation handoff.
