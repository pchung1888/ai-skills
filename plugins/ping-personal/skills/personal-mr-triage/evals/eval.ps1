#requires -Version 7
# Eval grader for personal-mr-triage. See evals/eval-plan.md for the failure-mode map.
# Deterministic red/green grader. Exit 0 = all checks pass; exit 1 = at least one fails.
# ASCII only (Windows PowerShell 5.1 cp1252 pitfall).
$ErrorActionPreference = 'Stop'

$SkillDir = Resolve-Path (Join-Path $PSScriptRoot '..')
$Skill    = Join-Path $SkillDir 'SKILL.md'

# The contract this skill exists to carry.
$contractChecks = @(
    @{ Pat = '(?i)file:line';                                   Why = 'verification evidence as file:line' },
    @{ Pat = '(?i)CONFIRMED, REFUTED or UNKNOWN';               Why = 'every finding gets a verdict' },
    @{ Pat = '(?i)Never mention the user.s private chat';       Why = 'replies never cite the private conversation' },
    @{ Pat = '(?i)Post only after approval';                    Why = 'nothing posted without the user OK' },
    @{ Pat = '(?i)remote commit hash';                          Why = 'proof before saying pushed' },
    @{ Pat = '\bglab mr\b';                                     Why = 'GitLab path (glab)' },
    @{ Pat = '\bgh pr\b';                                       Why = 'GitHub path (gh)' }
)

$tests = @(
    @{
        Name = 'skill_frontmatter: name + description with trigger phrases'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?m)^name:\s*personal-mr-triage\s*$') { throw "frontmatter name not personal-mr-triage" }
            if ($s -notmatch '(?m)^description:\s*\S') { throw "frontmatter description missing" }
            if ($s -notmatch '(?i)triage the review comments') { throw "trigger phrase missing" }
        }
    },
    @{
        Name = 'required_sections: Workflow + Boundaries present'
        Run = {
            $s = Get-Content $Skill -Raw
            foreach ($h in @('## Workflow', '## Boundaries')) {
                if ($s -notmatch [regex]::Escape($h)) { throw "missing required section: $h" }
            }
        }
    },
    @{
        Name = 'triage_contract: evidence, verdicts, reader-only replies, approval, proof, both forges'
        Run = {
            $s = Get-Content $Skill -Raw
            foreach ($c in $contractChecks) {
                if ($s -notmatch $c.Pat) { throw "contract knowledge lost: $($c.Why)" }
            }
        }
    },
    @{
        Name = 'ascii_only: SKILL.md has no byte >= 128'
        Run = {
            $bytes = [System.IO.File]::ReadAllBytes($Skill)
            foreach ($b in $bytes) { if ($b -ge 128) { throw "non-ASCII byte in SKILL.md" } }
        }
    },
    @{
        Name = 'calibration: a copy without the approval rule FAILS the contract grader'
        Run = {
            $s = Get-Content $Skill -Raw
            $bad = $s -replace '(?i)Post only after approval', 'Post when ready'
            $survives = $true
            foreach ($c in $contractChecks) {
                if ($bad -notmatch $c.Pat) { $survives = $false }
            }
            if ($survives) { throw "contract grader passed a copy without the approval rule -- dead metric" }
        }
    }
)

$pass = 0; $fail = 0
foreach ($t in $tests) {
    try { & $t.Run; $pass++; Write-Host "PASS $($t.Name)" -ForegroundColor Green }
    catch { $fail++; Write-Host "FAIL $($t.Name): $_" -ForegroundColor Red }
}
if ($fail -eq 0) { Write-Host "EVAL PASS personal-mr-triage ($pass)" -ForegroundColor Green; exit 0 }
else { Write-Host "EVAL FAIL personal-mr-triage ($fail of $($pass+$fail))" -ForegroundColor Red; exit 1 }
