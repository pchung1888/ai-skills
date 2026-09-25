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
        Name = 'effort_routing: SKILL.md documents per-dispatch effort tiers (fable-mode effort dial made concrete)'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?i)## Effort routing') { throw "Effort routing section missing" }
            if ($s -notmatch "effort") { throw "effort dispatch knob not documented" }
            # The guard may be worded as "never ... by default" or, more strictly, as
            # "never ... unless the operator names the stage". Accept either; the second
            # is the stronger form and is what the 789K measurement produced.
            # (?s) so the match can cross a line wrap -- the guard sentence wraps between
            # "max" and "unless" in the shipped text.
            if ($s -notmatch '(?si)never.{0,120}(xhigh|max).{0,120}(by default|unless)') { throw "over-effort guard (never xhigh/max without an explicit ask) missing" }
            if ($s -notmatch '(?i)default is .low. for every workflow agent') { throw "effort-low default for every agent missing" }
        }
    },
    @{
        Name = 'skill_frontmatter: SKILL.md declares name=personal-workflow + a description'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?m)^name:\s*personal-workflow\s*$') { throw "frontmatter name not personal-workflow" }
            if ($s -notmatch '(?m)^description:\s*\S') { throw "frontmatter description missing" }
            if ($s -notmatch '(?m)^model:\s*inherit\s*$') { throw "model: inherit missing -- conductor runs at the session tier, never pinned" }
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
    },
    @{
        # A past incident entered through the shape-equals-authority shortcut: a findings
        # inventory looked like a plan, so it was executed without the owner seeing it.
        Name = 'no_plan_shape_bypass: the skip-to-phasing shortcut is gone'
        Run  = {
            $s = Get-Content $Skill -Raw
            if ($s -match '(?m)^-\s*Concrete plan/list -> skip to phasing\.') {
                throw "the unconditional skip-to-phasing bypass is still present"
            }
            if ($s -notmatch 'owner participation') { throw "the skip test is not keyed on owner participation" }
            if ($s -notmatch '(?i)whenever the phase list GROWS') { throw "no re-run rule for a growing phase list" }
        }
    },
    @{
        # Before this, the parallel path referenced the dispatch template nowhere, so N
        # agents ran with strictly less context than one agent doing the same work.
        Name = 'fanout_uses_dispatch_template: unit briefs carry the ask'
        Run  = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch 'agent-dispatch-template\.md') {
                throw "MODE step does not build unit briefs from the dispatch template"
            }
        }
    },
    @{
        Name = 'resume_rereads_ask: recovery reads requirement, decisions, detours'
        Run  = {
            $s = Get-Content $Skill -Raw
            foreach ($needle in @('## Requirement', '## Decisions', '## Detours')) {
                if ($s -notmatch [regex]::Escape($needle)) { throw "resume does not read $needle" }
            }
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
