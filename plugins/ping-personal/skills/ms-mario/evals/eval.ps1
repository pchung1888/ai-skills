#requires -Version 7
$ErrorActionPreference = 'Stop'
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot '..\..\..\..\..')
$Check = [IO.Path]::Combine($RepoRoot, 'scripts', 'check_dual_runtime.py')
$out = (python $Check 2>&1 | Out-String)
if ($LASTEXITCODE -ne 0) { throw $out }
if ($out -notmatch 'DUAL RUNTIME CHECK PASS') { throw 'dual runtime check did not report pass' }
Write-Host 'EVAL PASS ms-mario persona wrapper (1)' -ForegroundColor Green
exit 0
