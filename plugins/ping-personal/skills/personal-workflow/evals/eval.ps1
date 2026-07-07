#requires -Version 7
# Eval grader for personal-workflow. See evals/eval-plan.md for the failure-mode map.
# Wraps the existing tests/smoke.ps1 (10 fence/discover/structure tests) -- the bulk
# grader -- and adds frontmatter + lib-presence checks. Exit 0 = pass, 1 = fail.
$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'   # cp1252 console guard (CLAUDE.md Windows pitfall)

$SkillDir    = Resolve-Path (Join-Path $PSScriptRoot '..')          # personal-workflow/
$Skill       = Join-Path $SkillDir 'SKILL.md'
$Lib         = Join-Path $SkillDir 'lib'
$Smoke       = Join-Path $SkillDir 'tests/smoke.ps1'
$BabysitTest = Join-Path $PSScriptRoot 'test-babysit.ps1'

$tests = @(
    @{
        Name = 'skill_frontmatter: SKILL.md declares name=personal-workflow + a description'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?m)^name:\s*personal-workflow\s*$') { throw "frontmatter name not personal-workflow" }
            if ($s -notmatch '(?m)^description:\s*\S') { throw "frontmatter description missing" }
        }
    },
    @{
        Name = 'lib_scripts_present: lib/discover.py and lib/fence.py exist'
        Run = {
            foreach ($f in @('discover.py','fence.py')) {
                if (-not (Test-Path (Join-Path $Lib $f))) { throw "missing load-bearing script: lib/$f" }
            }
        }
    },
    @{
        Name = 'smoke_suite_passes: tests/smoke.ps1 runs fully green (exit 0)'
        Run = {
            if (-not (Test-Path $Smoke)) { throw "tests/smoke.ps1 missing at $Smoke" }
            # Run in a child shell so its Set-Location does not leak into this session.
            pwsh -NoProfile -File $Smoke *> $null
            if ($LASTEXITCODE -ne 0) { throw "wrapped smoke suite failed (exit $LASTEXITCODE) -- run tests/smoke.ps1 to see which test" }
        }
    },
    @{
        Name = 'babysit_script_present: lib/babysit.py exists'
        Run = {
            if (-not (Test-Path (Join-Path $Lib 'babysit.py'))) {
                throw "missing lib/babysit.py"
            }
        }
    },
    @{
        Name = 'babysit_skill_doc: SKILL.md contains --babysit section'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '--babysit mode') { throw "SKILL.md missing --babysit section" }
        }
    },
    @{
        Name = 'babysit_behavioral: test-babysit.ps1 all assertions pass'
        Run = {
            if (-not (Test-Path $BabysitTest)) { throw "test-babysit.ps1 missing at $BabysitTest" }
            pwsh -NoProfile -File $BabysitTest *> $null
            if ($LASTEXITCODE -ne 0) { throw "babysit behavioral test failed (exit $LASTEXITCODE) -- run evals/test-babysit.ps1 to see which assertion" }
        }
    }
)

$pass = 0; $fail = 0
foreach ($t in $tests) {
    try { & $t.Run; $pass++; Write-Host "PASS $($t.Name)" -ForegroundColor Green }
    catch { $fail++; Write-Host "FAIL $($t.Name): $_" -ForegroundColor Red }
}
if ($fail -eq 0) { Write-Host "EVAL PASS personal-workflow ($pass)" -ForegroundColor Green; exit 0 }
else { Write-Host "EVAL FAIL personal-workflow ($fail of $($pass+$fail))" -ForegroundColor Red; exit 1 }
