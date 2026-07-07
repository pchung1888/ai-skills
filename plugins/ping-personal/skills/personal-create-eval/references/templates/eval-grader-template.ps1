#requires -Version 7
# Eval grader for <skill-name>. See evals/eval-plan.md for the failure-mode map.
# Deterministic red/green grader. Exit 0 = all checks pass; exit 1 = at least one fails.
# Runnable standalone OR from plugins/ping-personal/evals/run-all.ps1 (auto-discovered by glob).
# ASCII only (no em-dashes/smart-quotes -- Windows PowerShell 5.1 cp1252 pitfall).
$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'   # cp1252 console guard

$SkillDir = Resolve-Path (Join-Path $PSScriptRoot '..')   # <skill-name>/
$Skill    = Join-Path $SkillDir 'SKILL.md'
$Fix      = Join-Path $PSScriptRoot 'fixtures'
# $Lib    = Join-Path $SkillDir 'lib'      # uncomment for script-backed skills

$tests = @(
    @{
        # Every skill: frontmatter integrity (catches a rename/corruption that stops triggering).
        Name = 'skill_frontmatter: SKILL.md declares the right name + a description'
        Run = {
            $s = Get-Content $Skill -Raw
            $namePat = '(?m)^name:\s*' + [regex]::Escape('<skill-name>') + '\s*$'
            if ($s -notmatch $namePat) { throw "frontmatter name not <skill-name>" }
            if ($s -notmatch '(?m)^description:\s*\S') { throw "frontmatter description missing" }
        }
    },
    @{
        # CODE-grader pattern (script-backed skill): run the skill's script on a fixture,
        # assert a deterministic, KNOWN answer. Calibrate the value by hand first.
        Name = '<behavior>: <script> on a locked fixture yields the known result'
        Run = {
            # $out = (python (Join-Path $Lib '<script>.py') (Join-Path $Fix '<input>') 2>&1) -join "`n"
            # if ($LASTEXITCODE -ne 0) { throw "<script> failed: $out" }
            # if ($out -notmatch '<expected token>') { throw "expected <X>; got:`n$out" }
            throw 'TODO: replace with a real check (delete this block if not script-backed)'
        }
    },
    @{
        # CALIBRATION pattern: the grader must ACCEPT good and REJECT bad.
        # A grader that passes everything measures nothing.
        Name = 'calibration: known-good fixture passes AND known-bad fixtures fail'
        Run = {
            # foreach ($g in Get-ChildItem (Join-Path $Fix 'good-*')) { <assert checker exits 0> }
            # foreach ($b in Get-ChildItem (Join-Path $Fix 'bad-*'))  { <assert checker exits 1> }
            throw 'TODO: replace with real calibration (or delete if no bundled checker)'
        }
    },
    @{
        # STRUCTURAL pattern (instruction-only skill): required sections present, referential
        # integrity (any skill/agent/file this one references must exist on disk).
        Name = 'required_sections / referential_integrity'
        Run = {
            $s = Get-Content $Skill -Raw
            foreach ($h in @('<## Required Heading>')) {
                if ($s -notmatch [regex]::Escape($h)) { throw "missing required section: $h" }
            }
            throw 'TODO: replace with real structural + referential checks'
        }
    }
)

$pass = 0; $fail = 0
foreach ($t in $tests) {
    try { & $t.Run; $pass++; Write-Host "PASS $($t.Name)" -ForegroundColor Green }
    catch { $fail++; Write-Host "FAIL $($t.Name): $_" -ForegroundColor Red }
}
if ($fail -eq 0) { Write-Host "EVAL PASS <skill-name> ($pass)" -ForegroundColor Green; exit 0 }
else { Write-Host "EVAL FAIL <skill-name> ($fail of $($pass+$fail))" -ForegroundColor Red; exit 1 }
