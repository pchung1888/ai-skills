#requires -Version 7
# Eval grader for personal-plugin-release. See evals/eval-plan.md for the failure-mode map.
# Deterministic red/green grader. Exit 0 = all checks pass; exit 1 = at least one fails.
# ASCII only (no em-dashes/smart-quotes -- Windows PowerShell 5.1 cp1252 pitfall).
$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'

$SkillDir = Resolve-Path (Join-Path $PSScriptRoot '..')
$Skill    = Join-Path $SkillDir 'SKILL.md'

# The load-bearing knowledge this skill exists to carry. If any of these
# regexes stops matching, the skill has lost the fact that caused the
# original friction (7 sessions of "is it actually installed?").
$couplingChecks = @(
    @{ Pat = [regex]::Escape('plugins/ping-personal/.claude-plugin/plugin.json'); Why = 'repo plugin.json path' },
    @{ Pat = [regex]::Escape('.claude-plugin/marketplace.json');                  Why = 'repo marketplace.json path' },
    @{ Pat = [regex]::Escape('installed_plugins.json');                          Why = 'user-scope installed_plugins.json' },
    @{ Pat = [regex]::Escape('ping-personal@ping-personal');                     Why = 'correct install key (owner@name)' },
    @{ Pat = 'NOT\s+`?ping-personal@personal-plugin';                            Why = 'wrong-key warning' }
)

$tests = @(
    @{
        Name = 'skill_frontmatter: SKILL.md declares the right name + a description'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?m)^name:\s*personal-plugin-release\s*$') { throw "frontmatter name not personal-plugin-release" }
            if ($s -notmatch '(?m)^description:\s*\S') { throw "frontmatter description missing" }
        }
    },
    @{
        Name = 'three_file_coupling: all three version files + install-key contract documented'
        Run = {
            $s = Get-Content $Skill -Raw
            foreach ($c in $couplingChecks) {
                if ($s -notmatch $c.Pat) { throw "coupling knowledge lost: $($c.Why)" }
            }
        }
    },
    @{
        Name = 'verify_loaded_gate: mandatory gate + eval-suite ship gate + never-push-main all present'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?i)VERIFY-LOADED') { throw "verify-loaded gate missing" }
            if ($s -notmatch [regex]::Escape('run-all.ps1')) { throw "eval-suite ship gate missing" }
            if ($s -notmatch '(?i)never push main') { throw "never-push-main boundary missing" }
            if ($s -notmatch '(?i)reload-plugins') { throw "reload step missing" }
        }
    },
    @{
        Name = 'calibration: a mutated copy missing installed_plugins.json FAILS the coupling grader'
        Run = {
            $s = Get-Content $Skill -Raw
            $bad = $s -replace 'installed_plugins\.json', 'REDACTED.json'
            $survives = $true
            foreach ($c in $couplingChecks) {
                if ($bad -notmatch $c.Pat) { $survives = $false }
            }
            if ($survives) { throw "coupling grader passed a copy with installed_plugins.json removed -- dead metric" }
        }
    }
)

$pass = 0; $fail = 0
foreach ($t in $tests) {
    try { & $t.Run; $pass++; Write-Host "PASS $($t.Name)" -ForegroundColor Green }
    catch { $fail++; Write-Host "FAIL $($t.Name): $_" -ForegroundColor Red }
}
if ($fail -eq 0) { Write-Host "EVAL PASS personal-plugin-release ($pass)" -ForegroundColor Green; exit 0 }
else { Write-Host "EVAL FAIL personal-plugin-release ($fail of $($pass+$fail))" -ForegroundColor Red; exit 1 }
