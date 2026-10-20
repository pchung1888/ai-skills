#requires -Version 7
# Eval grader for personal-diagnosing-bugs. See evals/eval-plan.md for the failure-mode map.
# Deterministic red/green grader. Exit 0 = all checks pass; exit 1 = at least one fails.
$ErrorActionPreference = 'Stop'

$SkillDir = Resolve-Path (Join-Path $PSScriptRoot '..')
$Skill    = Join-Path $SkillDir 'SKILL.md'
$Hitl     = Join-Path $SkillDir 'scripts/hitl-loop.template.ps1'

$tests = @(
    @{
        Name = 'skill_frontmatter: name and description present'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?m)^name:\s*personal-diagnosing-bugs\s*$') { throw "frontmatter name not personal-diagnosing-bugs" }
            if ($s -notmatch '(?m)^description:\s*\S') { throw "frontmatter description missing" }
        }
    },
    @{
        Name = 'six_phases: all six phases are present, in order'
        Run = {
            $s = Get-Content $Skill -Raw
            $last = -1
            foreach ($h in @('## Phase 1:','## Phase 2:','## Phase 3:','## Phase 4:','## Phase 5:','## Phase 6:')) {
                $i = $s.IndexOf($h)
                if ($i -lt 0) { throw "missing $h" }
                if ($i -le $last) { throw "$h is out of order" }
                $last = $i
            }
        }
    },
    @{
        Name = 'loop_before_theory: the no-hypothesis-without-a-loop gate and 3-5 ranked hypotheses stay'
        Run = {
            $s = Get-Content $Skill -Raw
            foreach ($k in @('Do not hypothesise without a loop', 'already run at least once', '3-5 ranked hypotheses', 'Show the ranked list to the owner')) {
                if ($s -notmatch [regex]::Escape($k)) { throw "SKILL.md lost: $k" }
            }
        }
    },
    @{
        Name = 'start_loops: the ASP Classic, T-SQL and VB6 COM feedback loops are documented'
        Run = {
            $s = Get-Content $Skill -Raw
            foreach ($k in @('Invoke-WebRequest', 'sqlcmd', 'cscript', 'CreateObject', 'IIS log', 'git bisect run')) {
                if ($s -notmatch [regex]::Escape($k)) { throw "feedback-loop ladder lost: $k" }
            }
        }
    },
    @{
        Name = 'shared_boxes_read_only: probes stay read-only on QA, DEV and client boxes'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch 'probes stay read-only') { throw "shared-box read-only rule missing" }
        }
    },
    @{
        Name = 'hitl_template: the referenced HITL template exists, is ASCII and parses'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch [regex]::Escape('scripts/hitl-loop.template.ps1')) { throw "SKILL.md does not point at the HITL template" }
            if (-not (Test-Path $Hitl)) { throw "hitl-loop.template.ps1 missing" }
            $bad = @([System.IO.File]::ReadAllBytes($Hitl) | Where-Object { $_ -gt 127 }).Count
            if ($bad) { throw "$bad non-ASCII bytes in the HITL template" }
            $errs = $null
            [void][System.Management.Automation.Language.Parser]::ParseFile($Hitl, [ref]$null, [ref]$errs)
            if ($errs) { throw "HITL template parse errors: $($errs[0].Message)" }
        }
    }
)

$pass = 0; $fail = 0
foreach ($t in $tests) {
    try { & $t.Run; $pass++; Write-Host "PASS $($t.Name)" -ForegroundColor Green }
    catch { $fail++; Write-Host "FAIL $($t.Name): $_" -ForegroundColor Red }
}
if ($fail -eq 0) { Write-Host "EVAL PASS personal-diagnosing-bugs ($pass)" -ForegroundColor Green; exit 0 }
else { Write-Host "EVAL FAIL personal-diagnosing-bugs ($fail of $($pass+$fail))" -ForegroundColor Red; exit 1 }
