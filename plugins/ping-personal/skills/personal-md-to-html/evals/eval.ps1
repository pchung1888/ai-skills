#requires -Version 7
# Eval grader for personal-md-to-html. See evals/eval-plan.md for the failure-mode map.
# Wraps the existing tests/smoke.py (validator self-test + golden render-diff + 6
# negative tests) and adds frontmatter + script-presence checks. Exit 0 = pass.
$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'   # cp1252 console guard (CLAUDE.md Windows pitfall)

$SkillDir = Resolve-Path (Join-Path $PSScriptRoot '..')          # personal-md-to-html/
$Skill    = Join-Path $SkillDir 'SKILL.md'
$Smoke    = Join-Path $SkillDir 'tests/smoke.py'

$tests = @(
    @{
        Name = 'skill_frontmatter: SKILL.md declares name=personal-md-to-html + a description'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?m)^name:\s*personal-md-to-html\s*$') { throw "frontmatter name not personal-md-to-html" }
            if ($s -notmatch '(?m)^description:\s*\S') { throw "frontmatter description missing" }
        }
    },
    @{
        Name = 'scripts_present: md-to-html.py and md-to-html-check.py exist'
        Run = {
            foreach ($f in @('md-to-html.py','md-to-html-check.py')) {
                if (-not (Test-Path (Join-Path $SkillDir $f))) { throw "missing load-bearing script: $f" }
            }
        }
    },
    @{
        Name = 'vendor_html_plan: copied runtime is ASCII and ships its MIT LICENSE'
        Run = {
            $v = Join-Path $SkillDir 'vendor/html-plan'
            foreach ($f in @('htmlplan.js','htmlplan.css','LICENSE')) {
                $p = Join-Path $v $f
                if (-not (Test-Path $p)) { throw "missing vendor/html-plan/$f" }
                if ([System.IO.File]::ReadAllBytes($p) | Where-Object { $_ -gt 127 } | Select-Object -First 1) { throw "vendor/html-plan/$f is not ASCII; rerun vendor/vendor_html_plan.py" }
            }
            if ((Get-Content (Join-Path $v 'LICENSE') -Raw) -notmatch 'MIT License') { throw "vendor LICENSE lost its MIT text" }
        }
    },
    @{
        Name = 'smoke_suite_passes: tests/smoke.py runs fully green (exit 0)'
        Run = {
            if (-not (Test-Path $Smoke)) { throw "tests/smoke.py missing at $Smoke" }
            python $Smoke *> $null
            if ($LASTEXITCODE -ne 0) { throw "wrapped smoke suite failed (exit $LASTEXITCODE) -- run python tests/smoke.py to see which layer" }
        }
    }
)

$pass = 0; $fail = 0
foreach ($t in $tests) {
    try { & $t.Run; $pass++; Write-Host "PASS $($t.Name)" -ForegroundColor Green }
    catch { $fail++; Write-Host "FAIL $($t.Name): $_" -ForegroundColor Red }
}
if ($fail -eq 0) { Write-Host "EVAL PASS personal-md-to-html ($pass)" -ForegroundColor Green; exit 0 }
else { Write-Host "EVAL FAIL personal-md-to-html ($fail of $($pass+$fail))" -ForegroundColor Red; exit 1 }
