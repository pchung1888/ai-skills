#requires -Version 7
# Eval grader for personal-bypass. See evals/eval-plan.md for the failure-mode map.
# Exit 0 = all checks pass; exit 1 = at least one fails. Auto-discovered by evals/run-all.ps1.
# Uses a temp repo and a temp state folder only. ASCII only.
$ErrorActionPreference = 'Stop'
$SkillDir = Resolve-Path (Join-Path $PSScriptRoot '..')
$Script = Join-Path $SkillDir 'Set-PermissionMode.ps1'
$fails = 0; $passes = 0
function Check([string]$name, [bool]$ok) {
    if ($ok) { Write-Host "PASS $name"; $script:passes++ } else { Write-Host "FAIL $name" -ForegroundColor Red; $script:fails++ }
}

$tmp = Join-Path ([IO.Path]::GetTempPath()) ("pb-" + [guid]::NewGuid().ToString('N'))
$repo = Join-Path $tmp 'repo'; $state = Join-Path $tmp 'state'
New-Item -ItemType Directory -Force (Join-Path $repo '.claude') | Out-Null
$local = Join-Path $repo '.claude/settings.local.json'
function Run([string]$mode, [string]$r = $repo) { & pwsh -NoProfile -File $Script -Mode $mode -Repo $r -StateRoot $state 2>&1 | Out-String }
function Load([string]$p = $local) { Get-Content -LiteralPath $p -Raw | ConvertFrom-Json -AsHashtable }

try {
    $orig = @{ permissions = @{ allow = @('Read', 'Bash(git status)'); deny = @('Bash(sudo *)'); ask = @('Bash(git push *)'); defaultMode = 'acceptEdits' }; env = @{ A = '1' } }
    $orig | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $local -Encoding utf8NoBOM

    $h0 = (Get-FileHash $local).Hash
    $out = Run 'status'
    Check 'status changes nothing' ((Get-FileHash $local).Hash -eq $h0)
    Check 'status reports the local ask rule' ($out -match 'local 1')

    Run 'bypass' | Out-Null
    $b = Load
    Check 'bypass sets defaultMode bypassPermissions' ($b.permissions.defaultMode -eq 'bypassPermissions')
    Check 'bypass empties the local ask rules' (@($b.permissions.ask | Where-Object { $_ }).Count -eq 0)
    Check 'bypass writes last.json and good.json' (((Get-ChildItem $state -Recurse -Filter 'last.json').Count -eq 1) -and ((Get-ChildItem $state -Recurse -Filter 'good.json').Count -eq 1))

    Run 'bypass' | Out-Null   # a second bypass must not overwrite the parked original
    Run 'auto' | Out-Null
    $a = Load
    Check 'auto restores the original defaultMode' ($a.permissions.defaultMode -eq 'acceptEdits')
    Check 'auto restores the original ask rules' ((@($a.permissions.ask) -join '|') -eq 'Bash(git push *)')
    Check 'allow, deny and env unchanged' (((@($a.permissions.allow) -join '|') -eq 'Read|Bash(git status)') -and ((@($a.permissions.deny) -join '|') -eq 'Bash(sudo *)') -and ($a.env.A -eq '1'))
    Check 'auto removes the parked file' ((Get-ChildItem $state -Recurse -Filter 'parked.json').Count -eq 0)

    # Toggling many times keeps the backups at three files, and good.json stays the original.
    1..6 | ForEach-Object { Run 'bypass' | Out-Null; Run 'auto' | Out-Null }
    Run 'bypass' | Out-Null; Run 'bypass' | Out-Null   # a bypass while already in bypass must keep good.json
    $files = @(Get-ChildItem $state -Recurse -File | Where-Object { $_.Directory.Name -like 'repo-*' })
    Check 'twelve toggles keep three backup files at most' ($files.Count -le 3)
    Check 'good.json is the original file after many toggles' ((Load (Join-Path $files[0].DirectoryName 'good.json')).permissions.defaultMode -eq 'acceptEdits')

    # A toggle that broke the file: restore puts the good copy back, even over invalid JSON.
    '{ not json' | Set-Content -LiteralPath $local
    $outR = Run 'restore'
    $r = Load
    Check 'restore repairs a broken file from good.json' (($outR -match 'Restored') -and ($r.permissions.defaultMode -eq 'acceptEdits') -and ((@($r.permissions.ask) -join '|') -eq 'Bash(git push *)'))
    Check 'restore clears the parked values' ((Get-ChildItem $state -Recurse -Filter 'parked.json').Count -eq 0)
    Check 'restore keeps the broken file in last.json' ((Get-Content (Join-Path $files[0].DirectoryName 'last.json') -Raw) -match 'not json')

    $repo2 = Join-Path $tmp 'bare'; New-Item -ItemType Directory -Force $repo2 | Out-Null
    $local2 = Join-Path $repo2 '.claude/settings.local.json'
    Run 'bypass' $repo2 | Out-Null
    Check 'bypass creates a missing settings.local.json' ((Load $local2).permissions.defaultMode -eq 'bypassPermissions')
    Run 'auto' $repo2 | Out-Null
    Check 'auto on a created file leaves no defaultMode' (-not (Load $local2).permissions.ContainsKey('defaultMode'))

    $repo3 = Join-Path $tmp 'policy'; New-Item -ItemType Directory -Force (Join-Path $repo3 '.claude') | Out-Null
    '{"permissions":{"disableBypassPermissionsMode":"disable"}}' | Set-Content -LiteralPath (Join-Path $repo3 '.claude/settings.json')
    $out3 = Run 'bypass' $repo3
    Check 'bypass refuses when settings disable bypass mode' (($out3 -match 'Refused') -and -not (Test-Path (Join-Path $repo3 '.claude/settings.local.json')))

    $repo5 = Join-Path $tmp 'managed'; New-Item -ItemType Directory -Force $repo5 | Out-Null
    $managed = Join-Path $tmp 'managed-settings.json'
    '{"permissions":{"disableBypassPermissionsMode":"disable"}}' | Set-Content -LiteralPath $managed
    $out5 = & pwsh -NoProfile -File $Script -Mode bypass -Repo $repo5 -StateRoot $state -ExtraManagedPaths $managed 2>&1 | Out-String
    Check 'bypass refuses when a managed policy file disables bypass' (($out5 -match 'Refused') -and -not (Test-Path (Join-Path $repo5 '.claude/settings.local.json')))

    $repo4 = Join-Path $tmp 'tracked'; New-Item -ItemType Directory -Force (Join-Path $repo4 '.claude') | Out-Null
    '{}' | Set-Content -LiteralPath (Join-Path $repo4 '.claude/settings.local.json')
    git -C $repo4 init -q; git -C $repo4 add -f .claude/settings.local.json   # -f: a global gitignore may skip it
    $out4 = Run 'bypass' $repo4
    Check 'bypass refuses when git tracks settings.local.json' (($out4 -match 'Refused') -and ((Get-Content (Join-Path $repo4 '.claude/settings.local.json') -Raw).Trim() -eq '{}'))

    $skill = Get-Content -LiteralPath (Join-Path $SkillDir 'SKILL.md') -Raw
    Check 'SKILL.md names the script and the three modes' (($skill -match 'Set-PermissionMode\.ps1') -and ($skill -match 'bypass\|auto\|status'))
    Check 'SKILL.md stays manual-only (it lowers future sessions'' permission checks)' ($skill -match '(?m)^disable-model-invocation:\s*true\s*$')
    $nonAscii = Get-ChildItem $SkillDir -Recurse -File | Where-Object { [IO.File]::ReadAllBytes($_.FullName) | Where-Object { $_ -gt 127 } | Select-Object -First 1 }
    Check 'all skill files are ASCII' (-not $nonAscii)
} finally {
    Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
}
if ($fails) { Write-Host "EVAL FAIL personal-bypass ($fails of $($passes + $fails))" -ForegroundColor Red; exit 1 }
Write-Host "EVAL PASS personal-bypass ($passes)" -ForegroundColor Green
exit 0
