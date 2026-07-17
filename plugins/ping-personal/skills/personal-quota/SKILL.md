---
name: personal-quota
model: haiku
description: Report REAL Claude usage for the current account -- 5h (session) window %, weekly %, per-model scoped %, and context-window %, each with its reset time in local EST/EDT. TRIGGER on "/personal-quota", "how much quota", "how much usage left", "what's my usage", "am I close to the limit", "quota check", "how full is my weekly", "when does my session reset", "when does my weekly reset". Reads ccstatusline's cache when fresh, otherwise fetches the same /api/oauth/usage endpoint directly with the subscription token, so it never depends on ccstatusline being alive.
---

# /personal-quota

Show the operator's REAL Claude usage: session (5h) %, weekly %, any per-model scoped %,
and context-window %, each with when it resets in local time.

## When to invoke

Triggers are in the frontmatter description. Use it to decide "finish now / pause / fresh
session / smaller job" against real numbers instead of the IDE's percentage meters.

Do NOT invoke for: prompt-cache hit rate (that is `/personal-cache-stats`), historical
usage charts (see `~/.claude/usage-data/report.html`), or Anthropic developer-API console
questions (the operator has no developer API access -- this skill uses the subscription
OAuth token, which is a different thing).

## What this skill does

Runs `${CLAUDE_PLUGIN_ROOT}/skills/personal-quota/quota.ps1`, which resolves the numbers in a
cache-first, fetch-fallback order so no single third party can hold the data hostage:

| # | Source | When | Cost |
|---|---|---|---|
| 1 | ccstatusline cache `~/.cache/ccstatusline/usage.json` | fresh (age < 15 min AND resets not past) | free, no network |
| 2 | `GET /api/oauth/usage` with the subscription token | cache missing/stale, or ccstatusline not installed | one metadata call, no token cost |
| 3 | stale cache, flagged `STALE` / `UNKNOWN` | no fresh cache AND fetch failed (offline / token expired) | -- |

Context % comes from a separate path: it is native Claude Code data available only on the
statusline stdin, captured by the `ctx-sidecar` shim (see "Enable context %" below). If the
shim is not active, context % shows `n/a` and everything else still works.

The access token is read only into a request header; it is never printed, logged, or written
to any output (including `-Json`).

## How to run

Normal (cache-first, OAuth fallback):

```powershell
pwsh -NoProfile -File "${CLAUDE_PLUGIN_ROOT}/skills/personal-quota/quota.ps1"
```

Machine-readable (for scripts / evals -- emits a JSON object with no token field):

```powershell
pwsh -NoProfile -File "${CLAUDE_PLUGIN_ROOT}/skills/personal-quota/quota.ps1" -Json
```

Cache-only, never touch the network (if you want zero fetches; context % still works):

```powershell
pwsh -NoProfile -File "${CLAUDE_PLUGIN_ROOT}/skills/personal-quota/quota.ps1" -NoFetch
```

## Reading the output

```
Claude Usage -- you@example.com
  5h session    72%   resets in 54m  (03:39 EDT)
  Weekly        75%   resets in 1d 2h  (Jul 16 04:59 EDT)   Fable 58%
  Context       43% (0m old)

  source: cache (0m old)
```

- The `source:` line always says which tier answered and how old it is -- a stale number can
  never masquerade as live. `STALE cache` or `UNKNOWN` means treat the quota numbers with
  caution.
- Per-model scoped weekly (e.g. `Fable 58%`) appears only when the account has a scoped limit.
- Times are local EST/EDT (project rule). "resets in ..." is the countdown; the parenthesised
  time is the wall-clock reset.

Present these numbers to the operator directly. If `source` is STALE or the quota is UNKNOWN,
say so plainly (Honesty Protocol) rather than presenting the numbers as current.

## Enable context % (opt-in, one-time)

Context % needs the `ctx-sidecar` shim to run as the statusline command. This is a
self-owned shim -- it captures Claude Code's own `context_window.used_percentage` and then
chains to ccstatusline so your visible statusline is unchanged.

Because plugin paths change on upgrade, copy the shim to a stable location first, then point
`settings.json` at the copy. Print these steps for the operator; DO NOT edit settings.json
automatically (scope-control rule):

1. Copy the shim to a stable path:

   ```powershell
   Copy-Item "${CLAUDE_PLUGIN_ROOT}/skills/personal-quota/ctx-sidecar.ps1" "$env:USERPROFILE/.claude/ctx-sidecar.ps1"
   ```

2. In `~/.claude/settings.json`, set `statusLine.command` to:

   ```
   pwsh -NoProfile -File "C:/Users/<you>/.claude/ctx-sidecar.ps1"
   ```

   (bash statusline instead? use `ctx-sidecar.sh` with `bash "<path>/ctx-sidecar.sh"`.)

3. The shim writes `~/.cache/personal-quota/ctx.json` on every render; `/personal-quota` reads
   it. No change to what your statusline looks like.

To turn it off, point `statusLine.command` back at `ccstatusline`.

## Honest limits

- The `/api/oauth/usage` endpoint is reverse-engineered from ccstatusline v2.2.23, not
  official Anthropic docs. If Anthropic changes it, the fetch fails and the skill falls back
  to the cache (or reports UNKNOWN) -- it will not crash or invent numbers.
- The fetch uses the subscription OAuth token Claude Code keeps in `~/.claude/.credentials.json`.
  Inside a live session that token is normally fresh; if it is expired the fetch returns
  nothing and the skill falls back to the cache.
- Context % is only as fresh as the last statusline render (shown as "(Nm old)"). If the shim
  is not enabled, context % is `n/a`.
- The freshness window is 15 minutes by default (`-FreshnessMinutes`). Inside a live session
  with ccstatusline rendering, the cache is essentially always fresh.

## Related

- `/personal-cache-stats` -- prompt-cache hit rate for the current session (different metric).
- `/cost` -- Claude Code's built-in per-session cost. Does not show plan quota %.
- ccstatusline session/weekly widgets -- the always-on statusline version of these numbers.
