#requires -Version 7
# run-all.ps1 -- top-level eval runner for the ping-personal plugin.
# Runs the dual-runtime package check, then discovers every
# skills/<skill>/evals/eval.ps1, runs each in a child shell, and tallies.
# Prints "ALL EVALS PASS (<n> skills)" and exits 0 only if every skill's grader is green.
# This is the goal's acceptance command (accept-match "ALL EVALS PASS").
#
# Usage:
#   pwsh plugins/ping-personal/evals/run-all.ps1            # run all
#   pwsh plugins/ping-personal/evals/run-all.ps1 -Detailed  # also print each grader's PASS lines
[CmdletBinding()]
param([switch]$Detailed)

$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'   # cp1252 console guard (CLAUDE.md Windows pitfall)

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot '..\..\..')
$DualRuntimeCheck = Join-Path $RepoRoot 'scripts\check_dual_runtime.py'
if (-not (Test-Path $DualRuntimeCheck)) {
    Write-Host "Missing dual-runtime check: $DualRuntimeCheck" -ForegroundColor Red
    exit 1
}

Write-Host "Running dual-runtime package check..."
$dualOut = (python $DualRuntimeCheck 2>&1 | Out-String)
if ($LASTEXITCODE -ne 0) {
    Write-Host $dualOut
    Write-Host "DUAL RUNTIME CHECK FAIL" -ForegroundColor Red
    exit 1
}
if ($Detailed) { Write-Host $dualOut }
else {
    $dualSummary = (($dualOut -split "`n") | Where-Object { $_ -match 'DUAL RUNTIME CHECK PASS' } | Select-Object -Last 1)
    Write-Host ("  OK    {0,-26} {1}" -f 'dual-runtime', ($dualSummary.Trim())) -ForegroundColor Green
}
Write-Host ""

# Mod checks (ping-hud band in hooks/): source must be pure ASCII, and its claude plugin tests must pass.
$PluginDir = Resolve-Path (Join-Path $PSScriptRoot '..')
$modFiles = Get-ChildItem (Join-Path $PluginDir 'hooks\*') -Include *.ts, *.tsx -File
$nonAscii = @($modFiles | Where-Object { [System.IO.File]::ReadAllBytes($_.FullName) | Where-Object { $_ -gt 127 } | Select-Object -First 1 })
if ($nonAscii.Count -gt 0) {
    Write-Host ("MOD ASCII FAIL: {0}" -f (($nonAscii | ForEach-Object Name) -join ', ')) -ForegroundColor Red
    exit 1
}
Write-Host ("  OK    {0,-26} MOD ASCII PASS ({1} files)" -f 'ping-hud mod', $modFiles.Count) -ForegroundColor Green
if (Get-Command claude -ErrorAction SilentlyContinue) {
    $modOut = (claude plugin test $PluginDir 2>&1 | Out-String)
    if ($LASTEXITCODE -ne 0) {
        Write-Host $modOut
        Write-Host "MOD TESTS FAIL" -ForegroundColor Red
        exit 1
    }
    $modSummary = (($modOut -split "`n") | Where-Object { $_ -match 'Ran \d+ tests' } | Select-Object -Last 1)
    Write-Host ("  OK    {0,-26} MOD TESTS PASS {1}" -f 'ping-hud mod', ($modSummary.Trim())) -ForegroundColor Green
}
else { Write-Host ("  SKIP  {0,-26} claude CLI not on PATH (Codex-only machine)" -f 'ping-hud mod') -ForegroundColor Yellow }
Write-Host ""

$SkillsDir = Resolve-Path (Join-Path $PSScriptRoot '..\skills')
$evals = Get-ChildItem (Join-Path $SkillsDir '*\evals\eval.ps1') | Sort-Object FullName

if (-not $evals) { Write-Host "No skill evals found under $SkillsDir" -ForegroundColor Red; exit 1 }

$judgeCount = (Get-ChildItem (Join-Path $SkillsDir '*\evals\judge-rubric.md') -ErrorAction SilentlyContinue).Count
Write-Host ("Running {0} skill evals ({1} also have a judge rubric)..." -f $evals.Count, $judgeCount)
Write-Host ""

$pass = 0; $fail = 0; $failed = @()
foreach ($e in $evals) {
    $skill = $e.Directory.Parent.Name           # .../<skill>/evals/eval.ps1 -> <skill>
    $out = (pwsh -NoProfile -File $e.FullName 2>&1 | Out-String)
    if ($LASTEXITCODE -eq 0) {
        $pass++
        $summary = (($out -split "`n") | Where-Object { $_ -match 'EVAL PASS' } | Select-Object -Last 1)
        Write-Host ("  OK    {0,-26} {1}" -f $skill, ($summary.Trim())) -ForegroundColor Green
        if ($Detailed) { Write-Host $out }
    }
    else {
        $fail++; $failed += $skill
        Write-Host ("  FAIL  {0}" -f $skill) -ForegroundColor Red
        Write-Host $out
    }
}

# Report-only: top-10 overlapping skill descriptions. Never changes the result or exit code.
$cc = Join-Path $SkillsDir 'personal-create-eval\lib\collision_check.py'
if (Test-Path $cc) { Write-Host (python $cc 2>&1 | Out-String).TrimEnd() }
Write-Host ""
if ($fail -eq 0) {
    Write-Host ("ALL EVALS PASS ({0} skills)" -f $pass) -ForegroundColor Green
    exit 0
}
else {
    Write-Host ("EVALS FAIL ({0} of {1} skills): {2}" -f $fail, ($pass + $fail), ($failed -join ', ')) -ForegroundColor Red
    exit 1
}
