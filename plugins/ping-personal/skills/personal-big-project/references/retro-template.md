# Retro template (RETRO.md, written at the end of every run or stop)

The retro is about how /personal-big-project worked, not about the project. It is read later in
the plugin repo to improve the skill, by a reader who never saw the project.

Process only: no report names, table names, SQL, customer names, file contents, credentials or
business rules. Name things by their role ("the done command", "the second stage", "a database
setup step"). Label every claim EXTRACTED, INFERRED or UNKNOWN with its basis.

```text
# Retro - <one-line kind of goal, no project names> - <Day MM-DD> to <Day MM-DD>
<!-- Example kind of goal: "migrate 50 reports to a new database driver" -->

Skill version: <ping-personal version from the plugin cache path>   Coordinator model: <model>

## Numbers
<paste the table printed by scripts/retro_metrics.py>

## Did it match what the owner wanted
- Owner's score, 1 (missed) to 5 (exactly): <n, or "not asked yet">
- What surprised the owner: <owner's words, or "not asked yet">
- Goal-brief corrections at the door: <n>; questions the brief missed that came up later: <list>

## Timeline of the process (skill steps, not project work)
| When | Skill step or part | What happened |
|---|---|---|

## Where the skill got in the way
One row per row of log/skill-friction.md, plus anything the coordinator noticed afterwards.
| When | Skill step | Problem | Workaround used | Suggested change to the skill |
|---|---|---|---|---|

## Decisions worth remembering
From log/decisions.md and the critic-gate rows in STATUS.md; judge each with hindsight.
| When | Decision | Smart or dumb | Evidence (cost saved or lost, time, tokens) |
|---|---|---|---|

## Estimates vs actual
| What was estimated | Estimate | Actual | Basis of the estimate |
|---|---|---|---|

## Proposed changes to /personal-big-project (most valuable first)
<!-- When the owner's surprise or score points at something the skill missed, that is change 1, even with no friction row behind it. -->
1. <change> - because <evidence row above, or the owner's words>
```
