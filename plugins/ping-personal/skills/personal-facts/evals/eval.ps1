#requires -Version 7
# Eval grader for personal-facts. See evals/eval-plan.md for the failure-mode map.
# Deterministic red/green grader. Exit 0 = all checks pass; exit 1 = at least one fails.
# ASCII only (no em-dashes/smart-quotes -- Windows PowerShell 5.1 cp1252 pitfall).
$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'

$SkillDir = Resolve-Path (Join-Path $PSScriptRoot '..')
$Skill    = Join-Path $SkillDir 'SKILL.md'

# The label taxonomy IS the skill. Losing any label breaks the data contract
# that downstream facts docs (docs/<area>/facts/) depend on.
$labels = @('CONFIRMED-LIVE', 'EXTRACTED', 'INFERRED', 'UNKNOWN', 'RESOLVED')

$tests = @(
    @{
        Name = 'skill_frontmatter: SKILL.md declares the right name + a description'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?m)^name:\s*personal-facts\s*$') { throw "frontmatter name not personal-facts" }
            if ($s -notmatch '(?m)^description:\s*\S') { throw "frontmatter description missing" }
        }
    },
    @{
        Name = 'label_taxonomy: all five confidence labels documented'
        Run = {
            $s = Get-Content $Skill -Raw
            foreach ($l in $labels) {
                if ($s -notmatch [regex]::Escape($l)) { throw "label missing from taxonomy: $l" }
            }
        }
    },
    @{
        Name = 'output_contract: facts path convention + no-unlabeled-claims + wrong-fact penalty'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch [regex]::Escape('facts/')) { throw "facts/ output path convention missing" }
            if ($s -notmatch [regex]::Escape('-facts.md')) { throw "-facts.md filename suffix missing" }
            if ($s -notmatch '(?i)No unlabeled claims') { throw "no-unlabeled-claims rule missing" }
            if ($s -notmatch '(?i)3x worse') { throw "wrong-fact-vs-UNKNOWN penalty missing" }
            if ($s -notmatch '(?i)read-only') { throw "read-only probe boundary missing" }
        }
    },
    @{
        Name = 'calibration: a mutated copy missing RESOLVED FAILS the taxonomy grader'
        Run = {
            $s = Get-Content $Skill -Raw
            $bad = $s -replace 'RESOLVED', 'SETTLED'
            $survives = $true
            foreach ($l in $labels) {
                if ($bad -notmatch [regex]::Escape($l)) { $survives = $false }
            }
            if ($survives) { throw "taxonomy grader passed a copy without RESOLVED -- dead metric" }
        }
    }
)

$pass = 0; $fail = 0
foreach ($t in $tests) {
    try { & $t.Run; $pass++; Write-Host "PASS $($t.Name)" -ForegroundColor Green }
    catch { $fail++; Write-Host "FAIL $($t.Name): $_" -ForegroundColor Red }
}
if ($fail -eq 0) { Write-Host "EVAL PASS personal-facts ($pass)" -ForegroundColor Green; exit 0 }
else { Write-Host "EVAL FAIL personal-facts ($fail of $($pass+$fail))" -ForegroundColor Red; exit 1 }
