# cache-stats.ps1 -- report prompt-cache hit rate for the current Claude Code session
#
# Reads the most recent JSONL transcript for this project and aggregates the
# message.usage blocks Anthropic returns on every assistant turn.
#
# Auto-detects the project's transcript directory from $PWD. Claude Code
# sanitizes the project path to a directory name under
# ~/.claude/projects/ by replacing colons, slashes, backslashes, and spaces
# with dashes. If the auto-detected dir doesn't exist, the script falls back
# to the most recently modified .jsonl across ALL project dirs.
#
# Usage:
#   pwsh cache-stats.ps1                       # whole session, auto-detect project
#   pwsh cache-stats.ps1 -LastN 10             # last 10 turns only
#   pwsh cache-stats.ps1 -PerTurn              # also print per-turn table
#   pwsh cache-stats.ps1 -SessionFile <path>   # pick a specific JSONL
#   pwsh cache-stats.ps1 -ProjectDir <path>    # override the project dir

[CmdletBinding()]
param(
    [int]$LastN = 0,
    [switch]$PerTurn,
    [string]$SessionFile,
    [string]$ProjectDir
)

$ErrorActionPreference = 'Stop'

function Get-ProjectSlugFromPath {
    param([string]$Path)
    # Claude Code's sanitization: replace any non-alphanumeric character with `-`.
    # Real rule may differ slightly per version; this matches observed behavior
    # for D:/startuser/START gitlab/START -> D--startuser-START-gitlab-START.
    return ($Path -replace '[^A-Za-z0-9]', '-')
}

$projectsRoot = Join-Path $env:USERPROFILE '.claude\projects'

if ($SessionFile) {
    $target = Get-Item -LiteralPath $SessionFile
}
else {
    # Resolve the project's transcript dir.
    if (-not $ProjectDir) {
        $cwd = (Get-Location).Path
        $slug = Get-ProjectSlugFromPath $cwd
        $ProjectDir = Join-Path $projectsRoot $slug
    }

    if (Test-Path $ProjectDir) {
        $candidates = Get-ChildItem (Join-Path $ProjectDir '*.jsonl') -ErrorAction SilentlyContinue
    }
    else {
        # Fallback: search all project dirs and pick the most recent .jsonl overall.
        Write-Host "Project dir not found ($ProjectDir); searching all transcripts..." -ForegroundColor Yellow
        $candidates = Get-ChildItem (Join-Path $projectsRoot '*\*.jsonl') -ErrorAction SilentlyContinue
    }

    if (-not $candidates) {
        Write-Host "No transcripts found under $projectsRoot" -ForegroundColor Red
        exit 1
    }

    $target = $candidates | Sort-Object LastWriteTime -Descending | Select-Object -First 1
}

$turns = @()
$i = 0
foreach ($line in Get-Content -LiteralPath $target.FullName) {
    $i++
    try {
        $o = $line | ConvertFrom-Json
    }
    catch { continue }
    if (-not $o.message.usage) { continue }
    $u = $o.message.usage
    $turns += [pscustomobject]@{
        Turn   = $i
        Read   = [int]($u.cache_read_input_tokens     | ForEach-Object { $_ })
        Write  = [int]($u.cache_creation_input_tokens | ForEach-Object { $_ })
        Fresh  = [int]($u.input_tokens                | ForEach-Object { $_ })
        Output = [int]($u.output_tokens               | ForEach-Object { $_ })
        TTL1h  = [int]($u.cache_creation.ephemeral_1h_input_tokens | ForEach-Object { $_ })
        TTL5m  = [int]($u.cache_creation.ephemeral_5m_input_tokens | ForEach-Object { $_ })
    }
}

if (-not $turns) {
    Write-Host "Transcript has no assistant turns with usage blocks yet." -ForegroundColor Yellow
    exit 0
}

$rows = if ($LastN -gt 0) { $turns | Select-Object -Last $LastN } else { $turns }

$read = ($rows.Read | Measure-Object -Sum).Sum
$write = ($rows.Write | Measure-Object -Sum).Sum
$fresh = ($rows.Fresh | Measure-Object -Sum).Sum
$output = ($rows.Output | Measure-Object -Sum).Sum
$ttl1h = ($rows.TTL1h | Measure-Object -Sum).Sum
$ttl5m = ($rows.TTL5m | Measure-Object -Sum).Sum
$inputTotal = $read + $write + $fresh
$hit = if ($inputTotal) { [math]::Round($read / $inputTotal * 100, 1) } else { 0 }

# Hit-rate verdict
$verdict = switch ($true) {
    ($hit -ge 80) { 'WARM  -- good cache reuse'; break }
    ($hit -ge 50) { 'MIXED -- some invalidations'; break }
    ($hit -ge 20) { 'COLD  -- mostly first-touch'; break }
    default { 'FROZEN -- almost all fresh writes' }
}

Write-Host ""
Write-Host "Session  : $($target.Name)"
Write-Host "Turns    : $($rows.Count)  (of $($turns.Count) total in file)"
if ($LastN -gt 0) { Write-Host "Window   : last $LastN turns" }
Write-Host ""
Write-Host ("Cache READ  (hit)  : {0,12:N0}" -f $read)
Write-Host ("Cache WRITE (miss) : {0,12:N0}" -f $write)
Write-Host ("Fresh INPUT (tail) : {0,12:N0}" -f $fresh)
Write-Host ("Output tokens      : {0,12:N0}" -f $output)
Write-Host ""
Write-Host ("Hit rate : {0}%  [{1}]" -f $hit, $verdict)
Write-Host ""
if ($write -gt 0) {
    Write-Host ("TTL split on writes: 1h = {0:N0}   5m = {1:N0}" -f $ttl1h, $ttl5m)
    Write-Host ""
}

if ($PerTurn) {
    Write-Host "Per-turn detail:"
    $rows | Format-Table -AutoSize Turn, Read, Write, Fresh, Output, TTL1h, TTL5m
}
