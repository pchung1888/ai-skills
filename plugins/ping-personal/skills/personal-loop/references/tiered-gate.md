# Tiered critic gate -- /personal-loop

## Fast lane (every tick, default)

ONE seat (resolved FAST_CRITIC) reviews the tick's output.
Parse with `vote_parser.py --fast-lane`.

`FIX` is **severity-aware** -- the critic is advisory and must not halt a
green-list run on taste alone:

| Vote | Severity / context | Loop behavior |
|---|---|---|
| `PASS` | -- | record + continue next tick |
| `FIX` | low / medium, green-list goal | log finding to `.claude/tmp/` status file; CONTINUE |
| `FIX` | high, OR security-tagged (secret / irreversible / scope-violation), OR a fenced/ship ACTION | HALT; write findings; report fix path |
| `ESCALATE` | -- | fire the full 5-seat panel (personal-critic-gate); resolve per verdict |

"Advisory" means precise: the critic cannot move the STOP verdict in EITHER
direction. It cannot declare the loop done, and a lone low-severity nitpick
cannot halt it. Completion is determined by the ONE authoritative gate (THE GATE
LAW: `all-goals-done` in campaign mode, `accept_cmd` exit 0 in single-artifact
mode), never by a critic vote.

## Full 5-seat panel (on trigger only)

Fires when:
1. Fast lane voted ESCALATE
2. A Stay-Paused condition was detected
3. The ACTION is a ship/merge/release step
4. Route confidence was `low` (uncertain ACTION pick)
5. `--full-every N` sample (periodic safety check, default off)

The full panel keeps PASS/FIX/BLOCK. ESCALATE is NOT a valid 5-seat vote
(tally.py raises ValueError if ESCALATE reaches the panel -- fail-loud design).

## Role resolution (portability)

FAST_CRITIC is resolved at runtime via the precedence chain in SKILL.md
"## Role Resolution". On a machine with no critic agent installed, the
inline-judge fallback fires and the loop ANNOUNCES the degraded tier.

Never hardcode `ms-mario` or any agent name in the loop's tick code.
