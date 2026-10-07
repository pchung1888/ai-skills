[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$repo = Resolve-Path (Join-Path $PSScriptRoot '..')
. (Join-Path $PSScriptRoot 'HarnessPython.ps1')

$python = Find-HarnessPython
if (-not $python) {
    Write-Host "HARNESS DOGFOOD FAIL: Python runtime not found" -ForegroundColor Red
    exit 1
}
$env:PATH = "$(Split-Path $python);$env:PATH"

$syncOutput = (& $python (Join-Path $repo 'scripts\check_harness_sync.py') '--check' 2>&1 | Out-String)
if ($LASTEXITCODE -ne 0 -or $syncOutput -notmatch 'HARNESS SYNC CHECK PASS') {
    Write-Host $syncOutput
    Write-Host 'HARNESS DOGFOOD FAIL: sync check' -ForegroundColor Red
    exit 1
}

$evalOutput = (& pwsh -NoProfile -File (Join-Path $repo 'plugins\ping-personal\evals\run-all.ps1') 2>&1 | Out-String)
if ($LASTEXITCODE -ne 0 -or $evalOutput -notmatch 'ALL EVALS PASS') {
    Write-Host $evalOutput
    Write-Host 'HARNESS DOGFOOD FAIL: plugin eval suite' -ForegroundColor Red
    exit 1
}

Write-Host 'HARNESS DOGFOOD PASS'
Write-Host (($syncOutput -split "`n") | Where-Object { $_ -match 'HARNESS SYNC CHECK PASS' } | Select-Object -Last 1)
Write-Host (($evalOutput -split "`n") | Where-Object { $_ -match 'ALL EVALS PASS' } | Select-Object -Last 1)
exit 0
