#requires -Version 7
# Eval grader for personal-create-eval. See evals/eval-plan.md for the failure-mode map.
# Dogfoods the skill's own lib scripts: scaffold smoke + audit calibration (good->0, bad->1).
# Exit 0 = all checks pass; exit 1 = at least one fails. ASCII only (Windows cp1252 pitfall).
$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'

$SkillDir = Resolve-Path (Join-Path $PSScriptRoot '..')   # personal-create-eval/
$Skill    = Join-Path $SkillDir 'SKILL.md'
$Refs     = Join-Path $SkillDir 'references'
$Lib      = Join-Path $SkillDir 'lib'
$GoodFix  = Join-Path $PSScriptRoot 'fixtures/good-skill'
$BadFix   = Join-Path $PSScriptRoot 'fixtures/bad-skill'

function Invoke-Py([string]$script, [string[]]$rest) {
    python (Join-Path $Lib $script) @rest *> $null
    return $LASTEXITCODE
}

$tests = @(
    @{
        Name = 'skill_frontmatter: SKILL.md declares name=personal-create-eval + a description'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?m)^name:\s*personal-create-eval\s*$') { throw "frontmatter name not personal-create-eval" }
            if ($s -notmatch '(?m)^description:\s*\S') { throw "frontmatter description missing" }
        }
    },
    @{
        Name = 'both_modes_documented: SKILL.md documents CREATE and ENHANCE modes'
        Run = {
            $s = Get-Content $Skill -Raw
            foreach ($m in @('CREATE mode','ENHANCE mode')) {
                if ($s -notmatch [regex]::Escape($m)) { throw "mode '$m' not documented in SKILL.md" }
            }
        }
    },
    @{
        Name = 'references_present: field guide + eval-plan/eval-grader/judge-rubric templates'
        Run = {
            if (-not (Test-Path (Join-Path $Refs 'how-to-create-an-eval.md'))) { throw "missing references/how-to-create-an-eval.md" }
            foreach ($t in @('eval-plan-template.md','eval-grader-template.ps1','judge-rubric-template.md')) {
                if (-not (Test-Path (Join-Path $Refs "templates/$t"))) { throw "missing references/templates/$t" }
            }
        }
    },
    @{
        Name = 'lib_scripts_present: scaffold_eval.py + audit_eval.py exist'
        Run = {
            foreach ($f in @('scaffold_eval.py','audit_eval.py')) {
                if (-not (Test-Path (Join-Path $Lib $f))) { throw "missing lib/$f" }
            }
        }
    },
    @{
        Name = 'scaffold_smoke: scaffold_eval.py --dry-run on good-skill fixture exits 0 + plans actions [F05]'
        Run = {
            $out = (python (Join-Path $Lib 'scaffold_eval.py') --dry-run --skill $GoodFix 2>&1 | Out-String)
            if ($LASTEXITCODE -ne 0) { throw "scaffold --dry-run exited $LASTEXITCODE. Output:`n$out" }
            if ($out -notmatch 'would ') { throw "scaffold --dry-run printed no planned action. Output:`n$out" }
        }
    },
    @{
        Name = 'audit_calibration: audit good-skill ALLOWS (0); bad-skill REJECTS (1) [F06]'
        Run = {
            $good = Invoke-Py 'audit_eval.py' @('--skill', $GoodFix)
            if ($good -ne 0) { throw "auditor flagged the HEALTHY good-skill fixture (exit $good) -- F06" }
            $bad = Invoke-Py 'audit_eval.py' @('--skill', $BadFix)
            if ($bad -eq 0) { throw "auditor PASSED the broken bad-skill fixture (no eval.ps1) -- F06 (auditor measures nothing)" }
        }
    }
)

$pass = 0; $fail = 0
foreach ($t in $tests) {
    try { & $t.Run; $pass++; Write-Host "PASS $($t.Name)" -ForegroundColor Green }
    catch { $fail++; Write-Host "FAIL $($t.Name): $_" -ForegroundColor Red }
}
if ($fail -eq 0) { Write-Host "EVAL PASS personal-create-eval ($pass)" -ForegroundColor Green; exit 0 }
else { Write-Host "EVAL FAIL personal-create-eval ($fail of $($pass+$fail))" -ForegroundColor Red; exit 1 }
