#requires -Version 7
# Eval grader for personal-domain-modeling. See evals/eval-plan.md for the failure-mode map.
# Deterministic red/green grader. Exit 0 = all checks pass; exit 1 = at least one fails.
$ErrorActionPreference = 'Stop'

$SkillDir = Resolve-Path (Join-Path $PSScriptRoot '..')
$Skill    = Join-Path $SkillDir 'SKILL.md'

$tests = @(
    @{
        Name = 'skill_frontmatter: name and description present'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?m)^name:\s*personal-domain-modeling\s*$') { throw "frontmatter name not personal-domain-modeling" }
            if ($s -notmatch '(?m)^description:\s*\S') { throw "frontmatter description missing" }
        }
    },
    @{
        Name = 'format_files: GLOSSARY-FORMAT.md and DECISION-FORMAT.md exist, are linked and are ASCII'
        Run = {
            $s = Get-Content $Skill -Raw
            foreach ($f in @('GLOSSARY-FORMAT.md', 'DECISION-FORMAT.md')) {
                if ($s -notmatch [regex]::Escape("]($f)")) { throw "SKILL.md does not link $f" }
                $p = Join-Path $SkillDir $f
                if (-not (Test-Path $p)) { throw "$f missing" }
                $bad = @([System.IO.File]::ReadAllBytes($p) | Where-Object { $_ -gt 127 }).Count
                if ($bad) { throw "$bad non-ASCII bytes in $f" }
            }
        }
    },
    @{
        Name = 'decision_three_tests: decision notes are offered only when all three tests pass, in SKILL.md and DECISION-FORMAT.md'
        Run = {
            foreach ($p in @($Skill, (Join-Path $SkillDir 'DECISION-FORMAT.md'))) {
                $t = Get-Content $p -Raw
                foreach ($k in @('Hard to reverse', 'Surprising without context', 'The result of a real trade-off')) {
                    if ($t -notmatch [regex]::Escape($k)) { throw "$(Split-Path $p -Leaf) lost decision test: $k" }
                }
            }
        }
    },
    @{
        Name = 'docs_glossary_home: everything lives under docs/glossary/, with no docs/adr/ folder'
        Run = {
            foreach ($p in @($Skill, (Join-Path $SkillDir 'DECISION-FORMAT.md'), (Join-Path $SkillDir 'GLOSSARY-FORMAT.md'))) {
                $t = Get-Content $p -Raw
                if ($t -match 'docs/adr') { throw "$(Split-Path $p -Leaf) still points at docs/adr/" }
            }
            $s = Get-Content $Skill -Raw
            foreach ($k in @('docs/glossary/GLOSSARY.md', 'docs/glossary/decisions/')) {
                if ($s -notmatch [regex]::Escape($k)) { throw "SKILL.md lost the path: $k" }
            }
        }
    },
    @{
        Name = 'glossary_discipline: inline updates, no implementation details, lazy creation, check against code'
        Run = {
            $s = Get-Content $Skill -Raw
            foreach ($k in @('Do not batch the updates', 'holds no implementation details', 'Create files lazily', '### Check against the code', 'Update the glossary inline')) {
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
if ($fail -eq 0) { Write-Host "EVAL PASS personal-domain-modeling ($pass)" -ForegroundColor Green; exit 0 }
else { Write-Host "EVAL FAIL personal-domain-modeling ($fail of $($pass+$fail))" -ForegroundColor Red; exit 1 }
