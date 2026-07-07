#requires -Version 7
# run-all.ps1 -- top-level eval runner for the ping-personal plugin.
# Discovers every skills/<skill>/evals/eval.ps1, runs each in a child shell, and tallies.
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

Write-Host ""
if ($fail -eq 0) {
    Write-Host ("ALL EVALS PASS ({0} skills)" -f $pass) -ForegroundColor Green
    exit 0
}
else {
    Write-Host ("EVALS FAIL ({0} of {1} skills): {2}" -f $fail, ($pass + $fail), ($failed -join ', ')) -ForegroundColor Red
    exit 1
}
