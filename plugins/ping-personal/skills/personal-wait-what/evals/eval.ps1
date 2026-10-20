#requires -Version 7
# Eval grader for personal-wait-what. See evals/eval-plan.md for the failure-mode map.
# Deterministic red/green grader. Exit 0 = all checks pass; exit 1 = at least one fails.
$ErrorActionPreference = 'Stop'

$SkillDir = Resolve-Path (Join-Path $PSScriptRoot '..')
$Skill    = Join-Path $SkillDir 'SKILL.md'

$tests = @(
    @{
        Name = 'skill_frontmatter: name, description, model-invocable (its aliases forward to it), ASCII'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?m)^name:\s*personal-wait-what\s*$') { throw "frontmatter name not personal-wait-what" }
            if ($s -notmatch '(?m)^description:\s*\S') { throw "frontmatter description missing" }
            if ($s -match '(?m)^disable-model-invocation:\s*true') { throw "must stay model-invocable, or the alias forward is refused" }
            $bad = @([System.IO.File]::ReadAllBytes($Skill) | Where-Object { $_ -gt 127 }).Count
            if ($bad) { throw "$bad non-ASCII bytes in SKILL.md" }
        }
    },
    @{
        Name = 'repitch_rules: context first, 20-word STE sentences, glossary terms, unslop, the ask last'
        Run = {
            $s = Get-Content $Skill -Raw
            foreach ($k in @('**Context first.**', '20 words or fewer', 'ASD-STE100', 'docs/glossary/GLOSSARY.md', 'personal-unslop', '**End with the ask.**')) {
                if ($s -notmatch [regex]::Escape($k)) { throw "SKILL.md lost: $k" }
            }
        }
    },
    @{
        Name = 'no_new_facts: keeps every fact and adds none'
        Run = {
            $s = Get-Content $Skill -Raw
            foreach ($k in @('Keep every fact', 'Add no new facts')) {
                if ($s -notmatch [regex]::Escape($k)) { throw "SKILL.md lost: $k" }
            }
        }
    }
)

$pass = 0; $fail = 0
foreach ($t in $tests) {
    try { & $t.Run; $pass++; Write-Host "PASS $($t.Name)" -ForegroundColor Green }
    catch { $fail++; Write-Host "FAIL $($t.Name): $_" -ForegroundColor Red }
}
if ($fail -eq 0) { Write-Host "EVAL PASS personal-wait-what ($pass)" -ForegroundColor Green; exit 0 }
else { Write-Host "EVAL FAIL personal-wait-what ($fail of $($pass+$fail))" -ForegroundColor Red; exit 1 }
