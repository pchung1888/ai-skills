#requires -Version 7
# Eval grader for personal-jira-sync. See evals/eval-plan.md for the failure-mode map.
# Deterministic red/green grader. Exit 0 = all checks pass; exit 1 = at least one fails.
# ASCII only (no em-dashes/smart-quotes -- Windows PowerShell 5.1 cp1252 pitfall).
$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'

$SkillDir = Resolve-Path (Join-Path $PSScriptRoot '..')
$Skill    = Join-Path $SkillDir 'SKILL.md'

# Safety + degradation contract: these are the rules that keep a client-visible
# ticket safe and the skill usable when the MCP is absent.
$contractChecks = @(
    @{ Pat = '(?i)Never transition';                 Why = 'status-transition ban' },
    @{ Pat = '(?i)PASTE-READY';                      Why = 'degraded mode when MCP absent' },
    @{ Pat = [regex]::Escape('getJiraIssue');        Why = 'MCP preflight names the read tool' },
    @{ Pat = [regex]::Escape('editJiraIssue');       Why = 'MCP preflight names the edit tool' },
    @{ Pat = '(?i)never\s+clobber the\s+description';   Why = 'description-preservation rule' },
    @{ Pat = '(?i)nothing\s+unverified goes on it';     Why = 'client-visible honesty rule' }
)

$tests = @(
    @{
        Name = 'skill_frontmatter: SKILL.md declares the right name + a description'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?m)^name:\s*personal-jira-sync\s*$') { throw "frontmatter name not personal-jira-sync" }
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
        Name = 'sync_contract: transition ban + degraded mode + MCP preflight + preservation rules'
        Run = {
            $s = Get-Content $Skill -Raw
            foreach ($c in $contractChecks) {
                if ($s -notmatch $c.Pat) { throw "contract knowledge lost: $($c.Why)" }
            }
        }
    },
    @{
        Name = 'calibration: a mutated copy missing the transition ban FAILS the contract grader'
        Run = {
            $s = Get-Content $Skill -Raw
            $bad = $s -replace '(?i)Never transition', 'May transition'
            $survives = $true
            foreach ($c in $contractChecks) {
                if ($bad -notmatch $c.Pat) { $survives = $false }
            }
            if ($survives) { throw "contract grader passed a copy without the transition ban -- dead metric" }
        }
    }
)

$pass = 0; $fail = 0
foreach ($t in $tests) {
    try { & $t.Run; $pass++; Write-Host "PASS $($t.Name)" -ForegroundColor Green }
    catch { $fail++; Write-Host "FAIL $($t.Name): $_" -ForegroundColor Red }
}
if ($fail -eq 0) { Write-Host "EVAL PASS personal-jira-sync ($pass)" -ForegroundColor Green; exit 0 }
else { Write-Host "EVAL FAIL personal-jira-sync ($fail of $($pass+$fail))" -ForegroundColor Red; exit 1 }
