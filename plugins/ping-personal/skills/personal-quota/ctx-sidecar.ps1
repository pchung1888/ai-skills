# ctx-sidecar.ps1 -- statusline shim that captures the context % for /personal-quota.
#
# WHY THIS EXISTS: session/weekly quota can be fetched on demand (see quota.ps1), but the
# context-window % is ONLY available in the JSON Claude Code pipes to the statusLine command's
# stdin, as .context_window.used_percentage. A skill cannot read that stdin. So this shim -- which
# YOU own, not a third party -- persists that one number to ~/.cache/personal-quota/ctx.json each
# render, then CHAINS to ccstatusline so your visible statusline is unchanged.
#
# ENABLE (opt-in; the skill prints this, it does not edit settings.json for you):
#   Set  ~/.claude/settings.json  ->  statusLine.command  to:
#     pwsh -NoProfile -File "C:/Users/<you>/.claude/plugins/.../personal-quota/ctx-sidecar.ps1"
#   (or copy this file somewhere stable and point at that path).
#
# This shim must NEVER break the statusline: all failures are swallowed and it always emits SOMETHING.

$ErrorActionPreference = 'SilentlyContinue'

# Read the entire statusline stdin exactly once; reuse it for both the sidecar write and the chain.
$payload = [Console]::In.ReadToEnd()

try {
    $o = $payload | ConvertFrom-Json
    $pct = $o.context_window.used_percentage
    $model = if ($o.model.display_name) { $o.model.display_name } else { $o.model.id }
    if ($null -ne $pct) {
        $dir = Join-Path $env:USERPROFILE '.cache\personal-quota'
        if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
        $rec = [ordered]@{
            contextPct = [int][math]::Round([double]$pct, 0)
            model      = "$model"
            ts         = (Get-Date).ToString('o')
        }
        # -Compress + utf8 (no BOM on PowerShell 7) keeps the file tiny and ASCII-clean.
        # Atomic write (temp + replace) so a concurrent statusline render can never read a half-written file.
        $dest = Join-Path $dir 'ctx.json'
        $tmp  = "$dest.$PID.tmp"
        $rec | ConvertTo-Json -Compress | Set-Content -LiteralPath $tmp -Encoding utf8
        Move-Item -LiteralPath $tmp -Destination $dest -Force
    }
} catch { }

# Chain to ccstatusline so the visible statusline is unchanged. If ccstatusline is not installed,
# emit a minimal fallback so the statusline still renders (resilience: never rely on a third party).
$cc = Get-Command ccstatusline -ErrorAction SilentlyContinue
if ($cc) {
    $payload | & $cc.Source
} else {
    $folder = try { Split-Path -Leaf ($o.cwd) } catch { '' }
    $mdl = try { if ($o.model.display_name) { $o.model.display_name } else { $o.model.id } } catch { '?' }
    $ctx = try { '{0:N0}%' -f [double]$o.context_window.used_percentage } catch { '--' }
    "[$folder] $mdl | ctx: $ctx"
}
