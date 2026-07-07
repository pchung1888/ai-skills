#requires -Version 7
# Eval grader for personal-htsw. See evals/eval-plan.md for the failure-mode map.
# Code-based grader (deterministic). Exit 0 = all checks pass; exit 1 = at least one fails.
# Runnable standalone OR from plugins/ping-personal/evals/run-all.ps1.
$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'   # cp1252 console guard (CLAUDE.md Windows pitfall)

$SkillDir = Resolve-Path (Join-Path $PSScriptRoot '..')          # personal-htsw/
$Checker  = Join-Path $SkillDir 'htsw-check.py'
$Skill    = Join-Path $SkillDir 'SKILL.md'
$Refs     = Join-Path $SkillDir 'references'
$Fix      = Join-Path $PSScriptRoot 'fixtures'

# Run htsw-check.py on a fixture; return its exit code (no output).
function Invoke-Checker([string]$file) {
    python $Checker --input-file $file *> $null
    return $LASTEXITCODE
}

$tests = @(
    @{
        Name = 'skill_frontmatter: SKILL.md declares name=personal-htsw + a description'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?m)^name:\s*personal-htsw\s*$') { throw "frontmatter name not personal-htsw" }
            if ($s -notmatch '(?m)^description:\s*\S') { throw "frontmatter description missing" }
        }
    },
    @{
        Name = 'six_modes_documented: walk / pr / qa / boss / baby / code-explain all named in SKILL.md'
        Run = {
            $s = Get-Content $Skill -Raw
            foreach ($m in @('walk','pr','qa','boss','baby','code-explain')) {
                if ($s -notmatch [regex]::Escape("``$m``")) { throw "mode '$m' not documented (no backtick mention)" }
            }
        }
    },
    @{
        Name = 'reference_playbooks_present: references/{walk,pr,qa,boss,baby,code-explain}.md all exist'
        Run = {
            foreach ($m in @('walk','pr','qa','boss','baby','code-explain')) {
                $p = Join-Path $Refs "$m.md"
                if (-not (Test-Path $p)) { throw "missing reference playbook: references/$m.md" }
            }
        }
    },
    @{
        Name = 'checker_present: htsw-check.py exists'
        Run = { if (-not (Test-Path $Checker)) { throw "htsw-check.py missing at $Checker" } }
    },
    @{
        Name = 'checker_accepts_good: htsw-check.py exits 0 on fixtures/good-baby.md (E01)'
        Run = {
            $code = Invoke-Checker (Join-Path $Fix 'good-baby.md')
            if ($code -ne 0) { throw "grader rejected a conforming rendering (exit $code) -- F08 regression" }
        }
    },
    @{
        Name = 'checker_rejects_bad: htsw-check.py exits 1 on every fixtures/bad-*.md (E02,E03)'
        Run = {
            $bad = Get-ChildItem (Join-Path $Fix 'bad-*.md')
            if ($bad.Count -lt 1) { throw "no bad-*.md fixtures found" }
            foreach ($f in $bad) {
                $code = Invoke-Checker $f.FullName
                if ($code -eq 0) { throw "grader ACCEPTED a broken rendering: $($f.Name) -- F08 regression" }
            }
        }
    },
    @{
        Name = 'checker_accepts_code_explain_example: htsw-check.py exits 0 on references/examples/code-explain-examples.md'
        Run = {
            $ex = Join-Path $Refs 'examples/code-explain-examples.md'
            if (-not (Test-Path $ex)) { throw "missing code-explain-examples.md" }
            python $Checker --examples-file $ex *> $null
            if ($LASTEXITCODE -ne 0) { throw "checker rejected a conforming code-explain rendering (exit $LASTEXITCODE)" }
        }
    }
)

$pass = 0; $fail = 0
foreach ($t in $tests) {
    try { & $t.Run; $pass++; Write-Host "PASS $($t.Name)" -ForegroundColor Green }
    catch { $fail++; Write-Host "FAIL $($t.Name): $_" -ForegroundColor Red }
}
if ($fail -eq 0) { Write-Host "EVAL PASS personal-htsw ($pass)" -ForegroundColor Green; exit 0 }
else { Write-Host "EVAL FAIL personal-htsw ($fail of $($pass+$fail))" -ForegroundColor Red; exit 1 }
