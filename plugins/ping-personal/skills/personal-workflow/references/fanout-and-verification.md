# Fan-out eligibility + verification gate

## FANOUT 3-rule -- ALL must hold, else sequential
1. "Do X for each of N >= 3 independent things."
2. No shared mutable state between units.
3. No serialization constraint -- no browser launch, no single shared-resource toggle (one dev server,
   one IIS/web.config, one prod DB), no sensitive git/deploy op.

Always sequential regardless (DERIVED from rule 3, not a named-skill list): any phase whose work
launches a browser, toggles a single shared resource, deploys, or mutates shared state. Cap fan-out
<= 8 concurrent (process-budget discipline -- see CLAUDE.md "Process Budget Discipline"). Fan-out units
MUST be idempotent: a fan-out phase is ONE beacon phase containing N units, committed only at the phase
boundary, so a crash re-runs the whole phase. Read-only triage, parallel critique, and
authoring-to-distinct-files satisfy idempotency; anything that mutates shared state trips rule 2/3 and
stays sequential anyway.

## Token capture
The `/workflows` completion `<usage>` carries `agentCount`, `subagent_tokens`, `duration_ms`. Fold
`subagent_tokens` into `/personal-goal-next --tokens`. It is AGGREGATE, not per-agent -- record the lump
sum + agent count + run-id and SAY so; never fabricate a per-agent split. The driver commits + timestamps
(the workflow script cannot run git / `Date.now()` / `Math.random()` -- they break resume). For inline
driver work (no fan-out), record an honest inline estimate labelled as such.

## Verification gate -- claim-type -> required primary evidence
Before recording any high-stakes claim, the driver re-checks the evidence its TYPE requires. A claim that
cannot name its evidence is UNVERIFIED (never recorded as fact). Schema/return-contract validation checks
an answer's SHAPE, never its TRUTH. Fan-out multiplies the risk (N agents = N chances at a
plausible-but-wrong root cause), so the gate matters most after a fan-out phase.

| Claim shape | Primary evidence the driver re-checks |
|---|---|
| "Genuine defect at file:line" | Read that exact line; confirm the asserted condition; check >=1 sibling using the same pattern |
| "Config/setting X drives behavior Y" | Read the actual config source (env var, settings file, registry, DB row) -- confirm presence/value |
| "Function / SP / module does X" | Read the source of that symbol; confirm the behavior is in the code, not assumed |
| "Endpoint returns status / page renders" | Hit the endpoint, or confirm the guard exists in source |
| "Test passes / fix works" | Re-run the test command; quote the result (do NOT trust the subagent's say-so) |
| Anything else | Cannot name evidence -> UNVERIFIED |

> Illustrative incident (host repo, 2026-05-28): a researcher subagent returned a `CBool(Null) -> HTTP 500`
> defect at HIGH confidence -- schema-valid and WRONG (the driving setting was absent, and 83 sibling
> pages using the identical line passed). The claim's SHAPE was fine; its TRUTH was not. The gate exists
> to re-check the evidence before such a claim hits the durable beacon.
