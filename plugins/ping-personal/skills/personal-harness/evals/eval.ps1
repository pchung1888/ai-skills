#requires -Version 7
# Eval grader for personal-harness. See evals/eval-plan.md for the failure-mode map.
# Deterministic red/green grader. Exit 0 = all checks pass; exit 1 = at least one fails.
# ASCII only (Windows PowerShell 5.1 cp1252 pitfall).
$ErrorActionPreference = 'Stop'

$SkillDir = Resolve-Path (Join-Path $PSScriptRoot '..')
$Skill    = Join-Path $SkillDir 'SKILL.md'
$Repo     = Resolve-Path (Join-Path $SkillDir '..\..\..\..')

# The contract this skill exists to carry.
$contractChecks = @(
    @{ Pat = [regex]::Escape('scripts\bootstrap_machine.ps1');     Why = 'apply runs the bootstrap script' },
    @{ Pat = 'MACHINE BOOTSTRAP PASS';                             Why = 'apply reports the PASS line' },
    @{ Pat = '(?i)--update-manifest';                              Why = 'add-rule records source hashes' },
    @{ Pat = '(?i)check_harness_sync\.py"? --check';               Why = 'check / add-rule run the sync check' },
    @{ Pat = '(?i)wait for the user.s OK';                         Why = 'rule edits need approval' },
    @{ Pat = '(?i)Never hand-edit';                                Why = 'generated files are not hand-edited' },
    @{ Pat = '(?i)Never commit anything from';                     Why = 'per-machine state stays out of git' },
    @{ Pat = '/reload-plugins';                                    Why = 'running session must reload' }
)

$tests = @(
    @{
        Name = 'skill_frontmatter: name + description with trigger phrases'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?m)^name:\s*personal-harness\s*$') { throw "frontmatter name not personal-harness" }
            if ($s -notmatch '(?m)^description:\s*\S') { throw "frontmatter description missing" }
            if ($s -notmatch '(?i)apply the harness') { throw "trigger phrase missing" }
        }
    },
    @{
        Name = 'harness_contract: bootstrap, PASS line, manifest, check, approval, boundaries, reload'
        Run = {
            $s = Get-Content $Skill -Raw
            foreach ($c in $contractChecks) {
                if ($s -notmatch $c.Pat) { throw "contract knowledge lost: $($c.Why)" }
            }
        }
    },
    @{
        Name = 'referenced_scripts_exist: every script the skill runs is in the repo'
        Run = {
            foreach ($rel in @('scripts\bootstrap_machine.ps1', 'scripts\sync_harness_adapters.py', 'scripts\check_harness_sync.py')) {
                if (-not (Test-Path (Join-Path $Repo $rel))) { throw "skill runs a script that does not exist: $rel" }
            }
        }
    },
    @{
        Name = 'ascii_only: SKILL.md has no byte >= 128'
        Run = {
            foreach ($b in [System.IO.File]::ReadAllBytes($Skill)) { if ($b -ge 128) { throw "non-ASCII byte in SKILL.md" } }
        }
    },
    @{
        Name = 'calibration: a copy without the approval rule FAILS the contract grader'
        Run = {
            $bad = (Get-Content $Skill -Raw) -replace '(?i)wait for the user.s OK', 'continue'
            $survives = $true
            foreach ($c in $contractChecks) { if ($bad -notmatch $c.Pat) { $survives = $false } }
            if ($survives) { throw "contract grader passed a copy without the approval rule -- dead metric" }
        }
    }
)

$pass = 0; $fail = 0
foreach ($t in $tests) {
    try { & $t.Run; $pass++; Write-Host "PASS $($t.Name)" -ForegroundColor Green }
    catch { $fail++; Write-Host "FAIL $($t.Name): $_" -ForegroundColor Red }
}
if ($fail -eq 0) { Write-Host "EVAL PASS personal-harness ($pass)" -ForegroundColor Green; exit 0 }
else { Write-Host "EVAL FAIL personal-harness ($fail of $($pass+$fail))" -ForegroundColor Red; exit 1 }
