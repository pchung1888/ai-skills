# Seat 5 dispatch -- full rules and evidence

Loaded from SKILL.md step 11. SKILL.md holds the rules; this file holds the detail and the evidence behind them.

## Contents
- Why the Agent tool, not the Skill tool
- Cross-vendor text strip
- Read-only guard
- Vote parsing

## Why the Agent tool, not the Skill tool

The Codex plugin's `rescue.md` warns that `Skill(codex:rescue)` re-enters the command and
HANGS the session. The Agent-tool path is the only programmatic route.
(EXTRACTED from the Codex plugin's `commands/rescue.md` line 8; verified working via a
live read-only test 2026-06-07.)

## Cross-vendor text strip

Seat 5 runs on OpenAI's Codex CLI, a DIFFERENT VENDOR from every other seat. The
artifact text is interpolated into its prompt unfiltered, and beacons are in-scope
artifacts -- so a beacon's `## Requirement` section, which holds the owner's
unedited words and may quote client names or account identifiers, would leave the
vendor boundary. Before emitting the prompt: remove any `## Requirement` section
and replace any `ASK:<fragment>` Source cell with `ASK:[withheld]`, substituting
`[requirement withheld from cross-vendor seat]` where the section was.
This is a capability cut, not a filter, and it has NO escape hatch -- it does not
depend on a pattern matching correctly. Seat 5 is the fresh-eyes seat looking for
unexamined assumptions; it does not need the owner's words to do that, and amanda
(in-vendor, Seat 2) already owns requirement-matching.

## Read-only guard

**Read-only guard (IMPORTANT -- residual risk).** The `codex:codex-rescue`
forwarder DEFAULTS to a write-capable Codex run (`--write`) and only
stays read-only when the brief reads as "review-only / read-only /
review / diagnosis / research". This is a heuristic the forwarder
applies to the natural-language brief -- there is NO hard `--read-only`
flag exposed. The "Do NOT fix. Do NOT edit any files. Review-only."
lines above are what keep Seat 5 read-only, so they MUST stay verbatim.
(EXTRACTED from the plugin's `codex-cli-runtime` skill + `codex-rescue`
agent; the prose guard was confirmed to hold in the 2026-06-07 test, but
it is not enforced -- treat a write-capable slip as a real, if unlikely,
risk.)

## Vote parsing

Seat 5 vote parsing (robust extraction -- do it in this order):
- Do NOT use "last non-empty line". When dispatched via the Agent tool
  the harness appends a trailing `agentId: ... (use SendMessage ...)`
  footer with no preceding newline, so the JSON is not on a clean final
  line. (EXTRACTED from the 2026-06-07 live test, where the returned
  text ended `...}agentId: a6ca... (use SendMessage ...)`.)
- Extract the vote object with a quote-aware BALANCED `{...}` scan, not a
  flat regex. Walk the text tracking brace depth AND string state: skip
  braces inside double-quoted string values, and track backslash escapes
  so an escaped quote (`\"`) does not prematurely end a string. Collect
  every top-level balanced `{...}` span, then take the LAST span that
  `JSON.parse`s and carries a top-level `"VOTE"` key. A naive flat pattern
  such as
  `\{[^{}]*"VOTE"[^{}]*\}` is NOT sufficient: a `{` or `}` inside a
  `"why"` string value truncates the match, and Codex prose routinely
  contains example objects earlier in the text. (This brittleness was
  caught by a live Codex Vote 3 on this skill's own diff, 2026-06-07.)
- Validate the parsed object before counting it. Its `VOTE` value MUST be
  one of `PASS` / `FIX` / `BLOCK` for diff/plan artifacts (legacy aliases
  `SHIP` -> `PASS`, `ABORT` -> `BLOCK` are accepted), or a declared
  OPTIONS label / `ABSTAIN` for planning-time artifacts. A parsed object
  whose `VOTE` is missing, null, or out-of-set is a parse FAILURE, not a
  vote -- do not coerce it.
- If extraction, parse, or validation fails: retry once (fresh dispatch,
  same brief).
- On second failure: Seat 5 = ABSTAIN; record the parse failure in the
  tally block. The remaining 4 seats proceed; 3-of-4 majority applies.
- ABSTAIN (a valid object with `"VOTE": "ABSTAIN"`) is recorded as
  ABSTAIN and does NOT count toward any outcome.
- The canonical implementation is `lib/vote_parser.py` in this skill's
  directory. Use it as the reference for all parsing logic.
- Residual risk (accepted, not eliminated): a stray VOTE-shaped object
  in reviewer prose AFTER the real vote would make "last valid span" pick
  the wrong one. Mitigation: the brief above REQUIRES the vote object to
  be the FINAL content emitted, so "last span" aligns with the real vote.
  Keep that instruction verbatim. On genuine ambiguity, treat as a parse
  failure and retry once.
