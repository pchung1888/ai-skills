#requires -Version 7
# Eval grader for personal-ask-like-expert. See evals/eval-plan.md for the failure-mode map.
# Deterministic red/green grader. Exit 0 = all checks pass; exit 1 = at least one fails.
$ErrorActionPreference = 'Stop'

$SkillDir = Resolve-Path (Join-Path $PSScriptRoot '..')
$Skill    = Join-Path $SkillDir 'SKILL.md'

function Assert-Has([string]$text, [string[]]$keys) {
    foreach ($k in $keys) { if ($text -notmatch [regex]::Escape($k)) { throw "SKILL.md lost: $k" } }
}

$tests = @(
    @{
        Name = 'skill_frontmatter: name, description, ASCII in every skill file'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?m)^name:\s*personal-ask-like-expert\s*$') { throw "frontmatter name wrong" }
            if ($s -notmatch '(?m)^description:\s*\S') { throw "frontmatter description missing" }
            foreach ($f in Get-ChildItem $SkillDir -Recurse -File) {
                $bad = @([System.IO.File]::ReadAllBytes($f.FullName) | Where-Object { $_ -gt 127 }).Count
                if ($bad) { throw "$bad non-ASCII bytes in $($f.Name)" }
            }
        }
    },
    @{
        Name = 'four_questions: expert gap, rawest material, methods and tools, outside check'
        Run = {
            Assert-Has (Get-Content $Skill -Raw) @('would do here that the user is not asking for',
                'rawest material', 'specific methods and tools', 'other than you or me')
        }
    },
    @{
        Name = 'deeper_not_bigger: keeps scope, pasteable prompt, term glosses'
        Run = {
            Assert-Has (Get-Content $Skill -Raw) @('deeper, not bigger', 'add new deliverables', 'fenced code block', '**Terms.**')
        }
    },
    @{
        Name = 'check_ask: research first, term check, status check, counter-option prompt'
        Run = {
            Assert-Has (Get-Content $Skill -Raw) @('**Research first.**', 'personal-online-research',
                'the date checked', '**Check the ask.**', '**Term check.**', '**Status check.**',
                '**Counter-option.**', '**The counter-option prompt.**', 'Did you mean Y?', 'personal-grill-me', 'with docs',
                'vendor or primary-doc URL', 'add asks to the main prompt', 'unverified list',
                'never skip it', 'Tool and method names stay in the main answer')
        }
    },
    @{
        Name = 'retro_loop: rate mode, retro log outside repos, improve mode waits for the user'
        Run = {
            Assert-Has (Get-Content $Skill -Raw) @('rate <1-5>', '~/.claude/ask-like-expert-retros.md',
                '## Improve mode', 'Do not edit the skill until they pick')
        }
    },
    @{
        Name = 'honesty_labels: EXTRACTED / INFERRED / UNKNOWN and the stop rule'
        Run = {
            Assert-Has (Get-Content $Skill -Raw) @('EXTRACTED', 'INFERRED', 'UNKNOWN', "I don't know for sure")
        }
    },
    @{
        Name = 'metric_files: rubric with C1-C8 and at least 9 fixtures'
        Run = {
            $r = Get-Content (Join-Path $PSScriptRoot 'judge-rubric.md') -Raw
            foreach ($c in 1..8) { if ($r -notmatch "\| C$c \|") { throw "rubric lost C$c" } }
            $q = Get-Content (Join-Path $PSScriptRoot 'fixtures\questions.md') -Raw
            $n = ([regex]::Matches($q, '(?m)^## F\d+')).Count
            if ($n -lt 9) { throw "only $n fixtures" }
        }
    }
)

$pass = 0; $fail = 0
foreach ($t in $tests) {
    try { & $t.Run; $pass++; Write-Host "PASS $($t.Name)" -ForegroundColor Green }
    catch { $fail++; Write-Host "FAIL $($t.Name): $_" -ForegroundColor Red }
}
if ($fail -eq 0) { Write-Host "EVAL PASS personal-ask-like-expert ($pass)" -ForegroundColor Green; exit 0 }
else { Write-Host "EVAL FAIL personal-ask-like-expert ($fail of $($pass+$fail))" -ForegroundColor Red; exit 1 }
