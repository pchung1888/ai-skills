---
name: personal-cache-stats
model: haiku
description: Report prompt-cache hit rate for the current Claude Code session by parsing the most recent transcript JSONL. TRIGGER on "/personal-cache-stats", "show cache hit rate", "what's my cache hit rate", "how warm is my cache", "cache stats", or any question about how well the current session is reusing cached prompt tokens. Returns cached_read / cache_creation / fresh_input totals and a hit-rate percentage, with optional per-turn breakdown.
---

# /personal-cache-stats

Show how well the current Claude Code session is reusing cached prompt tokens.

## When to invoke

Triggers are in the frontmatter description. Also useful after a large
CLAUDE.md or `.claude/rules/*.md` edit, to confirm the cache repopulated on
the next turn. Do NOT invoke for prompt-caching theory questions (answer
inline) or anything needing the Anthropic API console (the user has no API
access).

## What this skill does

Runs `${CLAUDE_PLUGIN_ROOT}/skills/personal-cache-stats/cache-stats.ps1`,
which reads the most recent `*.jsonl` file under
`%USERPROFILE%\.claude\projects\<project-slug>\` (auto-detected from the
current working directory) and aggregates the `message.usage` block from
every assistant turn. Reports four numbers:

| Field | Meaning |
|---|---|
| Cache READ (hit) | Tokens served from cache. HIGHER is better. |
| Cache WRITE (miss) | Tokens that paid full input price AND were written to cache for later reuse. |
| Fresh INPUT (tail) | The new user message + tool outputs appended after the cache breakpoint. Always uncached. |
| Hit rate | `READ / (READ + WRITE + FRESH)` as a percentage. Target >80% on a warm session. |

Also splits cache writes into 1-hour vs 5-minute TTL buckets.

## How to run

Default (whole session):

```powershell
pwsh -NoProfile -File "${CLAUDE_PLUGIN_ROOT}/skills/personal-cache-stats/cache-stats.ps1"
```

Last N turns only (useful for spotting a recent cache invalidation):

```powershell
pwsh -NoProfile -File "${CLAUDE_PLUGIN_ROOT}/skills/personal-cache-stats/cache-stats.ps1" -LastN 10
```

Per-turn breakdown (shows the table of every turn's read/write/fresh):

```powershell
pwsh -NoProfile -File "${CLAUDE_PLUGIN_ROOT}/skills/personal-cache-stats/cache-stats.ps1" -PerTurn
```

A specific transcript file (rare -- only when investigating a prior
session):

```powershell
pwsh -NoProfile -File "${CLAUDE_PLUGIN_ROOT}/skills/personal-cache-stats/cache-stats.ps1" -SessionFile "C:\Users\<user>\.claude\projects\<slug>\<session>.jsonl"
```

## Reading the output

The script prints a verdict band:

| Hit rate | Verdict | Likely cause |
|---|---|---|
| >= 80% | WARM | Session is humming. Stable system prompt + CLAUDE.md, repeated turns within TTL. |
| 50-79% | MIXED | Either mid-session CLAUDE.md edit, frequent plugin toggles, or long gaps between turns. |
| 20-49% | COLD | Recent invalidation event, OR you're on turn 2-3 of a fresh session and the average hasn't recovered yet. |
| < 20% | FROZEN | Almost all writes, almost no reads. Normal on turn 1; abnormal beyond turn 3. |

The 1h-vs-5m TTL split tells you whether Claude Code is using the extended
(1-hour) cache bucket. On Opus 1M sessions you typically see ephemeral_1h
tokens, which means cache survives ~12x longer than the 5-min default
before eviction.

## What to do with low hit rates

| Symptom | Investigation |
|---|---|
| Hit rate dropped from 80%+ to <30% mid-session | Did you edit CLAUDE.md, `.claude/rules/*.md`, or toggle a plugin? Those invalidate the cache. |
| Hit rate never climbs above 30% across many sessions | Look for context bloat -- huge CLAUDE.md, many auto-loaded plugins, large MEMORY.md. Each turn pays full price to write before any read can be served. |
| Hit rate high but session still feels expensive | Cache misses aren't the bottleneck. Check output_tokens and look for over-long replies, or runaway subagent spend. |

## Honest limits

- The script reads ONLY the local transcript file. It cannot see what
  Anthropic's server actually charged -- the numbers reported are the
  `usage` block Claude Code received, which is the authoritative cost
  source, but billing tier discounts (if any) are applied server-side and
  not reflected here.
- The script picks the MOST RECENTLY MODIFIED `.jsonl` under the current
  project's transcript dir. If the auto-detected project dir doesn't exist
  (sanitization mismatch), the script falls back to the most recent
  `.jsonl` across ALL project dirs under `~/.claude/projects/`. If two
  Claude Code sessions are running concurrently the choice may not be the
  one you intended -- use `-SessionFile` to disambiguate.
- A long-running session's average dilutes recent behavior. Use `-LastN`
  to focus on the most recent window when investigating a specific change.

## Related

- `/cost` -- Claude Code's built-in command. Shows the same numbers without
  per-turn detail. Faster to type but less analytical.
- ccstatusline cache-hit widget -- live, always-on percentage in the
  statusline. Toggle via `npx ccstatusline@latest`.
