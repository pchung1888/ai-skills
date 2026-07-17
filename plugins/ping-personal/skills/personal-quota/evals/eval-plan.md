# Eval plan: personal-quota

## Target Behavior

- **LEVER** (what we version): `quota.ps1` resolution logic + `SKILL.md`.
- **SUBJECT** (what we grade): the `quota.ps1 -Json` object and its text output.

Given an injected usage cache, credentials path, context sidecar, and a fixed `-Now`,
`quota.ps1` must (1) select the correct source tier -- fresh cache -> `cache`, stale/missing
under `-NoFetch` -> `STALE cache` or `UNKNOWN`; (2) compute freshness as stale if
`age > FreshnessMinutes` OR a reset is in the past; (3) still emit the numbers when falling
back to a stale cache but set `stale=true` and label the source; (4) report `UNKNOWN` (null
pcts, null source) when there is no fresh cache and no fetch; (5) surface context % only when
the sidecar has a valid `contextPct`; (6) surface a per-model weekly split in `scoped[]` when
present; and (7) NEVER emit the access token or any credential material in any output path,
including `-Json`. The live-fetch tier is validated manually (see Not Covered).

## Failure Modes

| ID | Failure | Why It Matters | Grader |
| --- | --- | --- | --- |
| F01 | Fetches/derives when a fresh cache exists | wastes a call; may look "live" when cache would do | code: `fresh_cache_selected` |
| F02 | Treats an old cache as fresh | shows out-of-date numbers as current | code: `stale_by_age` |
| F03 | Ignores an elapsed reset window | a reset window rolled over but % shown as if not | code: `stale_by_reset_past` |
| F04 | Invents numbers when it has none | hallucinated quota -> wrong finish/pause decision | code: `missing_cache_unknown` |
| F05 | Drops numbers while flagging stale | operator loses the last-known signal | code: `stale_by_age` (asserts pct present) |
| F06 | Context shown when unavailable / hidden when present | false ctx reading, or missing the headline field | code: `context_present`, `context_absent_and_malformed` |
| F07 | Per-model split lost | scoped weekly (e.g. Fable/Opus) invisible | code: `scoped_rendering` |
| F08 | Token leak in output | credential exposure in a shared transcript | code: `token_safety` |
| F09 | Frontmatter rot (name/model/description) | skill stops triggering | code: `skill_frontmatter` |
| F10 | Dangling reference to a missing script | skill body points at a file that is not shipped | code: `referential_integrity` |

Every failure here is deterministic -- nothing is a matter of taste, so there is NO judge.

## Eval Cases

| ID | Input | Expected Behavior | Must Not Happen |
| --- | --- | --- | --- |
| E01 | good-usage-fresh, mtime -5m | source=cache, stale=false, 57/73 | fetch / stale flag |
| E02 | good-usage-fresh, mtime -60m | stale=true, source=STALE, numbers present | numbers dropped |
| E03 | bad-usage-stale-reset (reset in past) | stale=true | shown as current |
| E04 | no usage file, -NoFetch | sessionPct/source null (UNKNOWN) | invented numbers |
| E05 | good-ctx sidecar | contextAvailable=true, 43 | ctx null |
| E06 | no ctx / bad-ctx (no pct) | contextAvailable=false | false ctx value |
| E07 | good-usage-scoped | scoped[] has Opus + Sonnet | split lost |
| E08 | any run | no accessToken/Bearer/token-field in output | leak |
| E09 (regression) | good-usage-fresh sessionUsage mutated | eval goes RED | vacuous green |

## Graders

### Code Graders (`eval.ps1`)

All 11 graders are code; each runs `quota.ps1 -Json` with injected fixtures (always `-NoFetch`
+ bogus `-CredentialsPath`, so no network) and asserts one deterministic fact. Calibrated
against `good-*` (accepted) and `bad-*` (rejected) fixtures; `token_safety` is the security
guardrail expressed as code, not prose.

### Model Judge

None -- no subjective dimension.

### Human Spot Checks

Live-fetch tier: one manual run confirming real session/weekly/scoped render and the token is
never printed.

## Baseline Run

- date: 2026-07-15
- agent version: personal-quota @ ping-personal (pre-release; version bump deferred to ship)
- result summary: `EVAL PASS personal-quota (14)`. RED path proven: mutating
  `good-usage-fresh` sessionUsage 57->99 -> `EVAL FAIL` exit 1; restore -> `EVAL PASS`.
- Post-critic (Ms.Mario lightweight seat) additions: `malformed_cache_no_crash` (H2 crash-guard),
  `token_safety_live_path` (H3 -- drives Get-LiveUsage with a sentinel token against an unreachable
  port and asserts no leak), `fresh_cache_prevents_fetch` (M2 -- ordering). Fixes: wrapped both
  parse paths in try/catch (no crash on bad shape), ConvertTo-EasternLabel accepts a null reset,
  atomic ctx.json writes, sh fallback quote.

## Not Covered (honest limits)

- Live-fetch tier (`GET /api/oauth/usage`) needs a real subscription token + network -> manual only.
- `ctx-sidecar.sh` (bash) is not driven on Windows; mirrors the working statusline jq logic.
  The PowerShell shim's output shape IS the `good-ctx` fixture.

## Ship Gate

- `pwsh plugins/ping-personal/skills/personal-quota/evals/eval.ps1` -> `EVAL PASS` (exit 0).
- `pwsh plugins/ping-personal/evals/run-all.ps1` -> `ALL EVALS PASS`.
- Highest-severity blocker: F08 (token leak) -- must always be green.
