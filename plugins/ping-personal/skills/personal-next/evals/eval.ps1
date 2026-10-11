#requires -Version 7
# Eval grader for personal-next (the ping-hud Next button skill). Deterministic.
# Exit 0 = all checks pass; exit 1 = at least one fails. Run alone or from evals/run-all.ps1.
$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'

$SkillDir  = Resolve-Path (Join-Path $PSScriptRoot '..')
$Skill     = Join-Path $SkillDir 'SKILL.md'
$Validator = Join-Path $SkillDir 'validate.py'
$Fix       = Join-Path $PSScriptRoot 'fixtures'

$tests = @(
    @{
        Name = 'skill_frontmatter: name personal-next, model inherit, Next button trigger'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?m)^name:\s*personal-next\s*$') { throw "frontmatter name not personal-next" }
            if ($s -notmatch '(?m)^model:\s*inherit\s*$') { throw "model: inherit missing -- the main session runs this at its own tier" }
            if ($s -notmatch '(?m)^description:.*Next button') { throw "description does not name the Next button trigger" }
        }
    },
    @{
        Name = 'one_seat_read_only: the seat is next-recommender, whose agent file grants Read/Grep/Glob only (enforced, not asked)'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch 'subagent_type: ping-personal:next-recommender') { throw "seat is not ping-personal:next-recommender" }
            $a = Join-Path $SkillDir '../../agents/next-recommender.md'
            if (-not (Test-Path $a)) { throw "agents/next-recommender.md missing" }
            $t = Get-Content $a -Raw
            if ($t -notmatch '(?m)^tools:\s*Read,\s*Grep,\s*Glob\s*$') { throw "next-recommender tools line is not exactly Read, Grep, Glob" }
            if ($t -notmatch '(?m)^name:\s*next-recommender\s*$') { throw "agent name is not next-recommender" }
        }
    },
    @{
        Name = 'option_text_is_data: SKILL.md and the agent both say text from files or options never acts as instructions'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch 'Option text is data') { throw "SKILL.md lacks the option-text-is-data rule" }
            $t = Get-Content (Join-Path $SkillDir '../../agents/next-recommender.md') -Raw
            if ($t -notmatch 'is data\. It never changes these rules') { throw "agent lacks the data-not-instructions rule" }
        }
    },
    @{
        Name = 'click_only: answers come from AskUserQuestion, 2 to 4 options, no typed command required'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch 'AskUserQuestion') { throw "AskUserQuestion not named" }
            if ($s -notmatch '2 to 4') { throw "option limit 2 to 4 not stated" }
            if ($s -match '"challenge"|"jev"') { throw "typed challenge/jev path came back (DEC-10 dropped it)" }
        }
    },
    @{
        Name = 'fail_closed: never invent options; stop after a second failed validation'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch 'Never invent options') { throw "no-invention rule missing" }
            if ($s -notmatch 'returned no usable options') { throw "fail-closed message missing" }
        }
    },
    @{
        Name = 'brief_facts_only: brief is shown to the owner and carries no main-session pick'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch 'What the recommender saw') { throw "brief is not shown to the owner" }
            if ($s -notmatch 'No pick, ranking') { throw "brief does not forbid the main session's pick" }
        }
    },
    @{
        Name = 'validator_accepts_good: validate.py exits 0 on fixtures/good.json'
        Run = {
            python $Validator (Join-Path $Fix 'good.json') *> $null
            if ($LASTEXITCODE -ne 0) { throw "validator rejected a conforming reply (exit $LASTEXITCODE)" }
        }
    },
    @{
        Name = 'validator_rejects_bad: validate.py exits 1 on every fixtures/bad-*.json'
        Run = {
            $bad = Get-ChildItem (Join-Path $Fix 'bad-*.json')
            if ($bad.Count -lt 4) { throw "expected at least 4 bad fixtures, found $($bad.Count)" }
            foreach ($f in $bad) {
                python $Validator $f.FullName *> $null
                if ($LASTEXITCODE -eq 0) { throw "validator ACCEPTED $($f.Name)" }
            }
        }
    }
)

$pass = 0; $fail = 0
foreach ($t in $tests) {
    try { & $t.Run; $pass++; Write-Host "PASS $($t.Name)" -ForegroundColor Green }
    catch { $fail++; Write-Host "FAIL $($t.Name): $_" -ForegroundColor Red }
}
if ($fail -eq 0) { Write-Host "EVAL PASS personal-next ($pass)" -ForegroundColor Green; exit 0 }
else { Write-Host "EVAL FAIL personal-next ($fail of $($pass+$fail))" -ForegroundColor Red; exit 1 }
