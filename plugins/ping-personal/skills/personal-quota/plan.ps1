# plan.ps1 -- quota-aware task planner for the orchestration skills.
#
# Turns the real quota (from quota.ps1, the sensor) + a list of candidate tasks sized
# light/medium/heavy into a schedule decision: which tasks can START now, which must wait for a
# reset, which reset, and how to wake for them. This is the shared brain that personal-loop,
# personal-workflow, personal-goal, and personal-progress call so none of them re-encode budget
# policy. It NEVER touches the token (delegates to quota.ps1) and never decides safety -- the
# loop's counted limits remain the safety boundary; this only informs planning + scheduling.
#
# Bands on the BINDING meter (whichever of session/weekly is MORE consumed; tie -> weekly):
#   < 60% used  PROCEED     light, medium, heavy may start
#   60-85%      CONSERVE    light, medium (heavy defers)
#   85-95%      LIGHT_ONLY  light only
#   > 95%       STOP        nothing starts; hand off now
# (mirrors the CLAUDE.md Token Budget Discipline table; percent bands, NOT token math -- the
#  window's absolute token size is unknown, so token<->percent conversion is deliberately avoided.)
#
# Usage:
#   pwsh -NoProfile -File plan.ps1 -Tasks "docs:light,refactor:heavy" -Json
#   pwsh -NoProfile -File plan.ps1 -Tasks "light,medium,heavy"           # human table
# Test hooks:
#   -QuotaJson '<json>'|<path>   inject a quota snapshot instead of calling quota.ps1
#   -Now "<iso8601>"             fix "now" for deterministic wake-timing tests

[CmdletBinding()]
param(
    [string]$Tasks = 'light,medium,heavy',
    [string]$QuotaJson,
    [string]$Now,
    [switch]$Json
)
$ErrorActionPreference = 'Stop'

$nowTs = if ($Now) { [datetimeoffset]::Parse($Now) } else { [datetimeoffset]::Now }

# ---- get the quota snapshot (inject for tests, else call the sensor) ----------------------------
if ($QuotaJson) {
    $q = if ($QuotaJson.TrimStart().StartsWith('{')) { $QuotaJson | ConvertFrom-Json }
         else { Get-Content -LiteralPath $QuotaJson -Raw | ConvertFrom-Json }
} else {
    $quotaScript = Join-Path $PSScriptRoot 'quota.ps1'
    $q = (& pwsh -NoProfile -File $quotaScript -Json) -join "`n" | ConvertFrom-Json
}

$sessionPct = [int]$q.sessionPct
$weeklyPct  = [int]$q.weeklyPct

# ---- binding meter = the more-consumed window (its reset is what frees headroom) ----------------
if ($weeklyPct -ge $sessionPct) {
    $binding = 'weekly';  $bindingPct = $weeklyPct;  $bindingReset = $q.weeklyReset
} else {
    $binding = 'session'; $bindingPct = $sessionPct; $bindingReset = $q.sessionReset
}

$band = if ($bindingPct -gt 95) { 'STOP' }
        elseif ($bindingPct -ge 85) { 'LIGHT_ONLY' }
        elseif ($bindingPct -ge 60) { 'CONSERVE' }
        else { 'PROCEED' }

# size -> may it START now under this band?
function Test-Fits {
    param([string]$size, [int]$pct)
    switch ($size) {
        'light'  { return $pct -le 95 }
        'medium' { return $pct -lt 85 }
        'heavy'  { return $pct -lt 60 }
        default  { return $pct -lt 60 }   # unknown size treated as heavy (conservative)
    }
}

# ---- classify each task -------------------------------------------------------------------------
$taskOut = @()
$anyDefer = $false
foreach ($t in ($Tasks -split ',' | Where-Object { $_.Trim() })) {
    $parts = $t.Trim() -split ':', 2
    if ($parts.Count -eq 2) { $name = $parts[0].Trim(); $size = $parts[1].Trim().ToLower() }
    else                    { $name = $parts[0].Trim(); $size = $parts[0].Trim().ToLower() }
    $fits = Test-Fits -size $size -pct $bindingPct
    if (-not $fits) { $anyDefer = $true }
    $taskOut += [ordered]@{
        name       = $name
        size       = $size
        decision   = if ($fits) { 'FITS_NOW' } else { 'DEFER' }
        deferUntil = if ($fits) { $null } elseif ($bindingReset) { ([datetimeoffset]::Parse([string]$bindingReset)).ToString('o') } else { $null }
    }
}

# ---- wake mechanism for deferred work: ScheduleWakeup clamps to 1h, so only <=55m fits ----------
$wakeMechanism = 'none'; $wakeDelaySeconds = $null
if ($anyDefer -and $bindingReset) {
    $mins = ([datetimeoffset]::Parse([string]$bindingReset) - $nowTs).TotalMinutes
    if ($mins -le 0) {
        # reset already elapsed -> re-check quota immediately on the shortest allowed wakeup
        $wakeMechanism = 'schedulewakeup'; $wakeDelaySeconds = 60
    } elseif ($mins -le 55) {
        $wakeMechanism = 'schedulewakeup'; $wakeDelaySeconds = [int][math]::Min(3600, [math]::Max(60, [math]::Round($mins * 60)))
    } else {
        # further than the 1h ScheduleWakeup clamp -> the loop's quota-timed Task Scheduler relauncher
        $wakeMechanism = 'task-scheduler'
    }
}

$handoffRecommended = ($band -eq 'LIGHT_ONLY' -or $band -eq 'STOP' -or $anyDefer)

$result = [ordered]@{
    binding            = $binding
    bindingPct         = $bindingPct
    band               = $band
    sessionPct         = $sessionPct
    weeklyPct          = $weeklyPct
    handoffRecommended = $handoffRecommended
    wakeMechanism      = $wakeMechanism
    wakeDelaySeconds   = $wakeDelaySeconds
    deferUntil         = if ($anyDefer -and $bindingReset) { ([datetimeoffset]::Parse([string]$bindingReset)).ToString('o') } else { $null }
    tasks              = $taskOut
}

if ($Json) {
    $result | ConvertTo-Json -Depth 6
    exit 0
}

# ---- human table --------------------------------------------------------------------------------
Write-Host ""
Write-Host ("Quota plan  --  binding: {0} at {1}%  ->  band {2}" -f $binding, $bindingPct, $band)
Write-Host ("  session {0}%   weekly {1}%" -f $sessionPct, $weeklyPct)
Write-Host ""
foreach ($t in $taskOut) {
    $line = "  [{0,-6}] {1,-20} {2}" -f $t.size, $t.name, $t.decision
    if ($t.decision -eq 'DEFER') { $line += "  (until $($t.deferUntil))" }
    Write-Host $line
}
Write-Host ""
if ($handoffRecommended) {
    Write-Host ("  -> handoff recommended; wake via {0}{1}" -f $wakeMechanism, $(if ($wakeDelaySeconds) { " in ${wakeDelaySeconds}s" } else { "" }))
} else {
    Write-Host "  -> proceed; no handoff needed"
}
Write-Host ""
