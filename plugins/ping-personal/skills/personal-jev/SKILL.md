---
name: personal-jev
model: sonnet
description: Second opinion with a confidence meter from TypeSafe Jev (typed Noul / Choice / Score judgments). ON DEMAND ONLY. TRIGGER on "/personal-jev", "ask jev", "jev this", "what would jev pick", "jev-check this", "which jev type", "noul or choice or score", "jev, are these claims backed". Four modes - Decide (help Ping pick among options an AI offered), Which-tool (recommend Noul vs Choice vs Score and draft the question), Checklist (batch of yes/no checks), Claim check (is each claim supported by the evidence). Never sends raw code, SQL, client names, emails, or secrets; every send is previewed and needs Ping's OK. Do NOT auto-trigger on AskUserQuestion.
---

# /personal-jev

Ask TypeSafe Jev for typed judgments with probabilities, and tell Ping when Jev is split so
the decision is genuinely his. Jev does not generate text; it answers questions you define.

## Hard rules

1. **On demand only.** Run only when Ping asks. Never on your own initiative.
2. **Abstract the state.** Rewrite everything generically: no source code, SQL, stored proc
   names, table names, client or company names, people, emails, hostnames, GUIDs, or secrets.
   Describe the situation the way you would to an outside consultant under NDA.
3. **Preview, then OK, then send.** Always run the preview first, show Ping the payload, and
   add `-Send -Approve <fingerprint>` only after he says yes in this turn. The fingerprint is
   printed by the preview; if the payload changes afterwards, the send is refused (exit 6) and
   you must preview again and get a fresh OK. One approval covers the whole batch.
4. **Batch.** Put every question for one decision (or one checklist) in ONE payload. Jev
   evaluates many questions in parallel in a single call; one approval per batch is the point.
5. **Report YOUR CALL honestly.** When the script flags `YOUR CALL`, do not recommend. Lay out
   the tradeoff and say the decision depends on Ping's preference.

## Write the state as a packet

Keep `state` short and use this layout every time, so it stays compact, consistent, and
easy to check for client detail:

```
GOAL: the one decision or check being asked about.
FACTS: what is known, in generic words.
EVIDENCE: what the facts rest on (paraphrased), and what is unknown.
CONSTRAINTS: limits, preferences, what must not happen.
OPTIONS: the candidates, one line each (Decide mode only).
```

## Pick the primitive (ask in order, stop at the first yes)

| Test | Use | Answer | Mistake it prevents |
|---|---|---|---|
| Is it ONE statement that is true or false? | `noul` | 0-1 = P(yes) | Compound "A and B" (ask two); inverted phrasing ("free of X" - ask "contains X") |
| Is it ONE pick from a fixed, unordered set? | `choice` (1-255 options) | pick + probabilities + confidence | Missing an `other` option; non-exclusive options (use several nouls) |
| Is it a position on an ORDERED scale? | `score` (2-10 levels, low to high) | fractional score + confidence | Two dimensions in one score; reading a noul 0.5 as "medium" (it means unsure) |

When options are easy to confuse, use structured criteria: Choice option objects with
`what` / `not_for` / `examples`; Score levels as `{ "summary": ..., "signals": [...] }`.

## Modes

**Decide** - Ping has options an AI offered and wants a second opinion.
1. `pick`: one `choice` over the options (plus `other`).
2. Per option, one `score` per dimension, id `<option>__<dimension>`. Default dimensions:
   `safety`, `reversibility`, `cost`. **Order levels worst -> best** so higher is better.
3. Optional weights file `{ "<option>__<dimension>": weight }` -> one composite per option.
   Each composite prints how many scores it used and the least-sure one. A composite marked
   YOUR CALL rests on at least one unsure score; `incomplete` means a weighted answer is
   missing. Never rank options on composites alone when they are marked YOUR CALL.
4. Report: pick with probability, per-option composites (with their sureness), and YOUR CALL
   items.

**Which-tool** - Ping asks which primitive fits a question. Apply the table above yourself,
explain the choice in one line, and draft the question JSON. No API call needed unless Ping
asks to confirm with Jev.

**Checklist** - a batch of yes/no checks (e.g. against an abstracted change summary). One
`noul` per check, ids named after the check. Report pass / fail / unsure per item.

**Claim check** - one `noul` per claim: "Is this claim supported by the evidence below?"
with the abstracted evidence in `state`. ALWAYS say: "Evidence was paraphrased, so this
checks meaning, not exact wording."

## Running it

Write the payload to a temp file in the scratchpad: `{ "state": "...", "questions": { ... } }`
(`model` defaults to `jev-latest`). Then:

```bash
pwsh -NoProfile -File "${CLAUDE_PLUGIN_ROOT}/skills/personal-jev/jev.ps1" -Payload q.json                        # preview, prints fingerprint
pwsh -NoProfile -File "${CLAUDE_PLUGIN_ROOT}/skills/personal-jev/jev.ps1" -Payload q.json -Send -Approve <fp>      # after OK
pwsh -NoProfile -File "${CLAUDE_PLUGIN_ROOT}/skills/personal-jev/jev.ps1" -Payload q.json -Send -Approve <fp> -Weights w.json -Json
```

Options: `-Threshold 0.6` (confidence below it, or a noul between 1-t and t, is YOUR CALL),
`-Json` (machine-readable), `-Fake answers.json` (canned answers, no network).

Exit codes: 0 ok, 1 usage or missing key, 2 bad JSON, 3 bad shape, 4 leak tripwire refused,
5 HTTP error, 6 approval fingerprint missing or stale. On exit 4, rewrite the flagged category generically and preview again - never
try to get around the tripwire. On exit 3, fix the question shape.

**API key:** `TYPESAFE_API_KEY` env var, else a `TYPESAFE_API_KEY=` line in `.env.local` in
the current folder, else the same line in `~/.claude/jev.env` (override with `-KeyFile`). Put
the key in `~/.claude/jev.env` once and the skill works from any folder. The script never
searches parent folders and never prints the key. Never echo or cat the key yourself.

**Receipts:** every real send writes one JSON record to `~/.claude/jev-receipts/` (override
with `-ReceiptDir`): the state, the questions, the model, the threshold, every answer with
its full odds, the composites, and an empty `decision` slot. It is never written inside a repo,
never holds the key, and is not written when a payload is refused. The path is printed after
the answers. These receipts are the raw material for later checking how often Jev agrees with
Ping's final call.

## Where Jev pays off

Jev is fast and cheap per question, so it pays off in batches: a 20-item checklist or sorting
50 items in one call instead of a 30-100K-token subagent. For a single decision its value is
an independent opinion with real odds, not speed. It cannot find problems nobody thought to
ask about - that is still a critic's job (Ms.Mario / personal-critic-gate).

## Limits

- The tripwire only catches obvious identifiers; the preview + Ping's OK is the real gate.
- The fingerprint proves the sent payload is the previewed one. It does not prove a human saw
  it - that is still hard rule 3.
- Pricing, rate limits, and exact error-response shape are unknown (not in the docs read).
- Design: `docs/superpowers/specs/2026-09-23-personal-jev-design.md` (local only).
