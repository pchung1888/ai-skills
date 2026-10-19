# Scripted pre-flight checks for /personal-big-project (checks 1, 6, 7, 8 and 11 in
# references/pre-flight.md). The other checks need live tools and are run by the coordinator.
# Prints one line per check: "PASS <name> ..." or "FAIL <name>: <what to do>". Exit 1 on any FAIL.
#
# Example:
#   pwsh -NoProfile -File scripts/preflight.ps1 -RepoPath D:\work\myrepo -StateDir docs/proj-123/autopilot `
#     -DoneCommand "& 'C:\Program Files\Git\bin\bash.exe' done.sh" -PassLine "ALL CHECKS: PASS" -Disks C:,D: -MinGB 1 -WeeklyCap 85

param(
    # Target repo root. Example: D:\work\myrepo
    [Parameter(Mandatory)][string]$RepoPath,
    # State folder, relative to RepoPath. Example: docs/proj-123/autopilot
    [Parameter(Mandatory)][string]$StateDir,
    # Done command, run by pwsh inside RepoPath. Use a full path to Git Bash, because a bare
    # "bash" in pwsh can resolve to WSL. Example: & 'C:\Program Files\Git\bin\bash.exe' done.sh
    [Parameter(Mandatory)][string]$DoneCommand,
    # The exact last line the done command prints only when everything passes. Example: ALL CHECKS: PASS
    [Parameter(Mandatory)][string]$PassLine,
    # The exact last line the done command prints while the work is still unfinished. Default: the
    # pass line with PASS replaced by FAIL. Example: ALL CHECKS: FAIL
    [string]$FailLine = ($PassLine -replace 'PASS', 'FAIL'),
    # Drive letters to watch. Example: C:,D:
    [Parameter(Mandatory)][string[]]$Disks,
    # Minimum free GB on each disk. Example: 1
    [double]$MinGB = 1,
    # Weekly quota % at which the run stops starting new stages. Example: 85
    [int]$WeeklyCap = 85,
    # Minutes the done command may run before this check gives up. Example: 10
    [int]$DoneTimeoutMin = 10,
    # This session's id; Claude Code sets CLAUDE_CODE_SESSION_ID. Example: 7d4f0df1-929c-4862-941e-12ecb5445122
    [string]$SessionId = $env:CLAUDE_CODE_SESSION_ID,
    # Folder of ping-hud live-usage snapshots. Override only in tests.
    [string]$LiveUsageDir = (Join-Path $HOME '.claude/live-usage'),
    # Fallback quota reader from the personal-quota skill. Override only in tests.
    [string]$QuotaPs1 = (Join-Path $PSScriptRoot '../../personal-quota/quota.ps1')
)
$ErrorActionPreference = 'Stop'
$script:failed = 0
function Pass($name, $detail) { "PASS $name $detail" }
function Fail($name, $fix) { $script:failed++; "FAIL ${name}: $fix" }

# Snapshots older than this are stale; the ping-hud mod rewrites them while the session is active.
$StaleMinutes = 15

# --- 1 coordinator model + 6 quota (both read the live-usage snapshot) ---
$snap = $null
$snapPath = if ($SessionId) { Join-Path $LiveUsageDir "$SessionId.json" } else { $null }
if ($snapPath -and (Test-Path $snapPath)) {
    try { $snap = Get-Content $snapPath -Raw | ConvertFrom-Json } catch { $snap = $null }
}
if (-not $snap) {
    Fail 'coordinator-model' "no readable live-usage snapshot for session '$SessionId' in $LiveUsageDir. Is the ping-hud mod loaded?"
} elseif ($snap.model -match 'Opus') {
    Pass 'coordinator-model' "($($snap.model))"
} else {
    Fail 'coordinator-model' "session model is '$($snap.model)'. Switch this session to Opus (/model) before going unattended."
}

$weekly = $null
# pwsh's ConvertFrom-Json turns ISO strings into DateTime objects; re-parsing one as text loses the UTC offset.
$w = if ($snap) { $snap.writtenAt } else { $null }
$written = $null
try { $written = if ($w -is [datetime]) { [datetimeoffset]$w } elseif ($w) { [datetimeoffset]::Parse($w) } else { $null } } catch { $written = $null }
$age = if ($written) { ([datetimeoffset]::UtcNow - $written).TotalMinutes } else { [double]::MaxValue }
# A snapshot from the future (beyond 1 min of clock skew) is treated as stale, not fresh.
if ($age -ge -1 -and $age -lt $StaleMinutes) {
    $weekly = ($snap.claude | Where-Object window -eq '7d').percentUsed
    $source = "snapshot, $([int]$age) min old"
}
# A stale snapshot, or a fresh one with no 7d row, falls back to the personal-quota script.
if ($null -eq $weekly -and (Test-Path $QuotaPs1)) {
    try {
        $rows = & pwsh -NoProfile -File $QuotaPs1 -Provider claude -Json | ConvertFrom-Json
        $weekly = ($rows | Where-Object window -eq '7d').percentUsed
        $source = 'quota.ps1'
    } catch { $weekly = $null }
}
if ($null -eq $weekly) {
    Fail 'quota-sensor' "neither a fresh snapshot (< $StaleMinutes min) nor quota.ps1 gave a weekly %. Run /personal-quota and fix what it reports."
} elseif ($weekly -ge $WeeklyCap) {
    Fail 'quota-sensor' "weekly usage $weekly% is already at or over the cap $WeeklyCap%. Raise the cap or start after the weekly reset."
} else {
    # ponytail: no token-to-% forecast here (the ratio is not published); the tick logs the real burn rate.
    Pass 'quota-sensor' "(weekly $weekly% of cap $WeeklyCap%, $source)"
}

# --- 7 disk ---
# "pwsh -File" passes "C:,D:" as one string, so split it here.
foreach ($d in ($Disks -split ',' | Where-Object { $_.Trim() })) {
    $letter = $d.TrimEnd(':', '\')
    $drive = Get-PSDrive -Name $letter -PSProvider FileSystem -ErrorAction SilentlyContinue
    if (-not $drive) { Fail "disk-$letter" "drive $letter not found"; continue }
    $freeRaw = $drive.Free / 1GB   # compare the unrounded value; round only for display
    $freeGB = [math]::Round($freeRaw, 1)
    if ($freeRaw -ge $MinGB) { Pass "disk-$letter" "($freeGB GB free, minimum $MinGB)" }
    else { Fail "disk-$letter" "$freeGB GB free, below the minimum $MinGB GB. Free space before leaving." }
}

# --- 8 state folder ---
$state = Join-Path $RepoPath $StateDir
$missing = @('STATUS.md', 'log/run-log.md', 'log/quota-log.md', 'log/side-effects.md', 'log/skill-friction.md') | Where-Object { -not (Test-Path (Join-Path $state $_)) }
if ($missing) {
    Fail 'state-folder' "missing in ${state}: $($missing -join ', '). Create them from references/STATUS.template.md."
} else {
    try {
        Add-Content (Join-Path $state 'log/run-log.md') "| $(Get-Date -Format 'ddd MM-dd HH:mm') | preflight | state folder accepts appends | - |"
        Pass 'state-folder' "($state)"
    } catch { Fail 'state-folder' "cannot append to log/run-log.md: $($_.Exception.Message)" }
}

# --- 11 done command is RED now ---
$job = Start-Job -ScriptBlock {
    param($repo, $cmd)
    Set-Location $repo
    & pwsh -NoProfile -Command $cmd 2>&1 | Out-String
} -ArgumentList $RepoPath, $DoneCommand
if (Wait-Job $job -Timeout ($DoneTimeoutMin * 60)) {
    $out = Receive-Job $job
    $last = (($out -split "`r?`n") | Where-Object { $_.Trim() } | Select-Object -Last 1)
    $last = if ($last) { $last.Trim() } else { '' }
    if (-not $last) { Fail 'done-red' "the done command printed nothing. Check it runs: $DoneCommand" }
    elseif ($last -eq $PassLine) { Fail 'done-red' "the done command already passes, so finishing cannot be proven. Tighten it until it fails on the current code." }
    elseif ($last -eq $FailLine) { Pass 'done-red' "(last line: $last)" }
    else { Fail 'done-red' "unexpected last line '$last' (wanted the fail line '$FailLine'), so the done command may be broken. Fix the command or pass -FailLine." }
} else {
    Stop-Job $job
    Fail 'done-red' "the done command ran longer than $DoneTimeoutMin min. Give a quicker command that proves RED, or raise -DoneTimeoutMin."
}
Remove-Job $job -Force

if ($script:failed) { "PREFLIGHT FAIL ($script:failed)"; exit 1 }
'PREFLIGHT SCRIPTED CHECKS PASS'
