#!/usr/bin/env bash
# ctx-sidecar.sh -- statusline shim that captures the context % for /personal-quota (bash variant).
#
# See ctx-sidecar.ps1 for the full rationale. In short: context % lives ONLY in the statusline
# stdin as .context_window.used_percentage; this shim persists it to ~/.cache/personal-quota/ctx.json
# then chains to ccstatusline so the visible statusline is unchanged. Never breaks the statusline.
#
# ENABLE (opt-in): point ~/.claude/settings.json statusLine.command at this script.

payload="$(cat)"

dir="$HOME/.cache/personal-quota"
pct="$(printf '%s' "$payload" | jq -r '.context_window.used_percentage // empty' 2>/dev/null)"
model="$(printf '%s' "$payload" | jq -r '.model.display_name // .model.id // empty' 2>/dev/null)"

if [ -n "$pct" ]; then
  mkdir -p "$dir" 2>/dev/null
  ts="$(date -u +%Y-%m-%dT%H:%M:%S%z 2>/dev/null)"
  # round to integer without bc
  pct_int="$(printf '%.0f' "$pct" 2>/dev/null)"
  # atomic write (temp + mv) so a concurrent render never reads a half-written file
  tmp="$dir/ctx.json.$$.tmp"
  printf '{"contextPct":%s,"model":"%s","ts":"%s"}\n' "${pct_int:-0}" "$model" "$ts" > "$tmp" 2>/dev/null && mv -f "$tmp" "$dir/ctx.json" 2>/dev/null
fi

# Chain to ccstatusline, or emit a minimal fallback if it is not installed.
if command -v ccstatusline >/dev/null 2>&1; then
  printf '%s' "$payload" | ccstatusline
else
  folder="$(printf '%s' "$payload" | jq -r '.cwd // empty' 2>/dev/null)"
  folder="$(basename "$folder" 2>/dev/null)"
  pdisp="$pct"; [ -z "$pdisp" ] && pdisp="--"
  printf '[%s] %s | ctx: %s%%' "$folder" "${model:-?}" "$pdisp"
fi
