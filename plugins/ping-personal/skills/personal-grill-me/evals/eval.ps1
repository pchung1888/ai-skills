#requires -Version 7
# Eval grader for personal-grill-me. See evals/eval-plan.md for the failure-mode map.
# Deterministic red/green grader. Exit 0 = all checks pass; exit 1 = at least one fails.
$ErrorActionPreference = 'Stop'

$SkillDir = Resolve-Path (Join-Path $PSScriptRoot '..')
$Skill    = Join-Path $SkillDir 'SKILL.md'

$tests = @(
    @{
        Name = 'skill_frontmatter: name, description, model-invocable (its aliases forward to it), ASCII'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?m)^name:\s*personal-grill-me\s*$') { throw "frontmatter name not personal-grill-me" }
            if ($s -notmatch '(?m)^description:\s*\S') { throw "frontmatter description missing" }
            if ($s -match '(?m)^disable-model-invocation:\s*true') { throw "must stay model-invocable, or the alias forward is refused" }
            $bad = @([System.IO.File]::ReadAllBytes($Skill) | Where-Object { $_ -gt 127 }).Count
            if ($bad) { throw "$bad non-ASCII bytes in SKILL.md" }
        }
    },
    @{
        Name = 'interview_rules: design tree, frontier rounds, a recommended answer each, yes accepts it'
        Run = {
            $s = Get-Content $Skill -Raw
            foreach ($k in @('**design tree**', '**frontier**', '-> Recommended:', '"yes" accepts your recommended answer')) {
                if ($s -notmatch [regex]::Escape($k)) { throw "SKILL.md lost: $k" }
            }
        }
    },
    @{
        Name = 'facts_vs_decisions: look facts up yourself, put decisions to the user, confirm before acting'
        Run = {
            $s = Get-Content $Skill -Raw
            foreach ($k in @('Facts are your job, never the user''s', 'Decisions are the user''s', 'Do not act on it until the user confirms')) {
                if ($s -notmatch [regex]::Escape($k)) { throw "SKILL.md lost: $k" }
            }
        }
    },
    @{
        Name = 'ping_rules: options named by what they do, speech-to-text check'
        Run = {
            $s = Get-Content $Skill -Raw
            foreach ($k in @('never by bare letters', 'speech-to-text')) {
                if ($s -notmatch [regex]::Escape($k)) { throw "SKILL.md lost: $k" }
            }
        }
    },
    @{
        Name = 'with_docs_mode: with docs runs personal-domain-modeling into docs/glossary/'
        Run = {
            $s = Get-Content $Skill -Raw
            foreach ($k in @('ping-personal:personal-domain-modeling', 'docs/glossary/GLOSSARY.md', 'docs/glossary/decisions/', '/grill-with-docs')) {
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
if ($fail -eq 0) { Write-Host "EVAL PASS personal-grill-me ($pass)" -ForegroundColor Green; exit 0 }
else { Write-Host "EVAL FAIL personal-grill-me ($fail of $($pass+$fail))" -ForegroundColor Red; exit 1 }
