# Claim-blind Seat 5, cycle cap, four-bucket reconcile

## Claim-blind Seat 5
Seat 5 judges the artifact, not the author's story. Before dispatching it, strip the author's summary
and claims (for example "I fixed X, tests pass") from its brief. What each Seat 5 variant receives:
- codex: the artifact only. The cross-vendor strip in SKILL.md (requirement withheld) still applies.
- iris fallback: the artifact plus the requirement, still without the author's summary or claims.
A claim the seat needs checked is re-derived from the artifact by the seat itself.

## Cycle cap
A FIX -> fix -> re-review loop stops after 3 cycles. After the third FIX the item is deferred: record it
as a deferred finding (owner decides later) and move on. Never start a 4th re-review of the same item.

## Four-bucket reconcile
After the tally, the driver prints one table: finding | bucket | seats that raised it.

| Bucket | Rule |
|---|---|
| Act On | raised by 2 or more seats |
| Consider | raised by 1 seat, with evidence (file:line or quoted output) |
| Noted | raised without evidence |
| Dismissed | contradicts an owner order (owner orders are constraints, not review items) |

Dismissed rows name the order they contradict. The table informs the resolution step; the vote verdict
itself is still decided by lib/tally.py.
