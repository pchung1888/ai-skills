#requires -Version 7
# Eval grader for personal-pr-briefing. See evals/eval-plan.md for the failure-mode map.
# Deterministic red/green grader. Exit 0 = all checks pass; exit 1 = at least one fails.
# ASCII only (no em-dashes/smart-quotes -- Windows PowerShell 5.1 cp1252 pitfall).
$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'

$SkillDir = Resolve-Path (Join-Path $PSScriptRoot '..')
$Skill    = Join-Path $SkillDir 'SKILL.md'

# The contract this skill exists to carry: idempotent marker-scoped updates,
# both forges, description-only boundary, independent-analysis rule.
$contractChecks = @(
    @{ Pat = [regex]::Escape('<!-- reviewer-briefing:start -->'); Why = 'start marker (idempotent re-runs)' },
    @{ Pat = [regex]::Escape('<!-- reviewer-briefing:end -->');   Why = 'end marker' },
    @{ Pat = '\bgh pr\b';                                          Why = 'GitHub path (gh)' },
    @{ Pat = '\bglab mr\b';                                        Why = 'GitLab path (glab)' },
    @{ Pat = '(?i)not the\s+commit\s+messages';                    Why = 'independent-analysis rule (anti self-marking)' },
    @{ Pat = '(?i)Never merge, approve';                           Why = 'description-only boundary' }
)

$tests = @(
    @{
        Name = 'skill_frontmatter: SKILL.md declares the right name + a description'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?m)^name:\s*personal-pr-briefing\s*$') { throw "frontmatter name not personal-pr-briefing" }
            if ($s -notmatch '(?m)^description:\s*\S') { throw "frontmatter description missing" }
        }
    },
    @{
        Name = 'required_sections: Procedure + Boundaries present'
        Run = {
            $s = Get-Content $Skill -Raw
            foreach ($h in @('## Procedure', '## Boundaries')) {
                if ($s -notmatch [regex]::Escape($h)) { throw "missing required section: $h" }
            }
        }
    },
    @{
        Name = 'briefing_contract: markers + both forges + independence rule + boundary all documented'
        Run = {
            $s = Get-Content $Skill -Raw
            foreach ($c in $contractChecks) {
                if ($s -notmatch $c.Pat) { throw "contract knowledge lost: $($c.Why)" }
            }
        }
    },
    @{
        Name = 'calibration: a mutated copy missing the end marker FAILS the contract grader'
        Run = {
            $s = Get-Content $Skill -Raw
            $bad = $s.Replace('<!-- reviewer-briefing:end -->', '')
            $survives = $true
            foreach ($c in $contractChecks) {
                if ($bad -notmatch $c.Pat) { $survives = $false }
            }
            if ($survives) { throw "contract grader passed a copy without the end marker -- dead metric" }
        }
    }
)

$pass = 0; $fail = 0
foreach ($t in $tests) {
    try { & $t.Run; $pass++; Write-Host "PASS $($t.Name)" -ForegroundColor Green }
    catch { $fail++; Write-Host "FAIL $($t.Name): $_" -ForegroundColor Red }
}
if ($fail -eq 0) { Write-Host "EVAL PASS personal-pr-briefing ($pass)" -ForegroundColor Green; exit 0 }
else { Write-Host "EVAL FAIL personal-pr-briefing ($fail of $($pass+$fail))" -ForegroundColor Red; exit 1 }
