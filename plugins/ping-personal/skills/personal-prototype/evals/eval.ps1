#requires -Version 7
# Eval grader for personal-prototype. See evals/eval-plan.md for the failure-mode map.
# Code-based grader (deterministic). Exit 0 = all checks pass; exit 1 = at least one fails.
# Runnable standalone OR from plugins/ping-personal/evals/run-all.ps1.
$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'   # cp1252 console guard (CLAUDE.md Windows pitfall)

$SkillDir = Resolve-Path (Join-Path $PSScriptRoot '..')          # personal-prototype/
$Skill    = Join-Path $SkillDir 'SKILL.md'
$Refs     = Join-Path $SkillDir 'references'
$Scripts  = Join-Path $SkillDir 'scripts'
$Fixtures = Join-Path $PSScriptRoot 'fixtures'

# Files whose source must stay pure ASCII (CLAUDE.md: no em-dash / smart-quote in parsed-adjacent files).
$AsciiFiles = @(
    $Skill,
    (Join-Path $Refs 'ui-mode.md'),
    (Join-Path $Refs 'non-ui-mode.md'),
    (Join-Path $Scripts 'check_prototype.py')
)

$tests = @(
    @{
        Name = 'F01 skill_frontmatter: SKILL.md declares name=personal-prototype + a description'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?m)^name:\s*personal-prototype\s*$') { throw "frontmatter name not personal-prototype" }
            if ($s -notmatch '(?m)^description:\s*\S') { throw "frontmatter description missing" }
        }
    },
    @{
        Name = 'F02 default_count_documented: default of 5 and the 2..8 clamp are stated'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch 'default[s]?\s+5|Default\s+5') { throw "default of 5 not documented" }
            if ($s -notmatch '2\.\.8') { throw "2..8 clamp not documented" }
        }
    },
    @{
        Name = 'F03 both_modes_documented: UI mode + NON-UI mode named and reference files exist'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch 'UI mode')     { throw "UI mode not documented" }
            if ($s -notmatch 'NON-UI mode') { throw "NON-UI mode not documented" }
            foreach ($r in @('ui-mode.md','non-ui-mode.md')) {
                $p = Join-Path $Refs $r
                if (-not (Test-Path $p)) { throw "missing reference: references/$r" }
            }
        }
    },
    @{
        Name = 'F04 delegates_present: /browse, an iterate beat, a durable-run option, and a ship path are all named'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '/browse')   { throw "/browse (PREVIEW delegate) not named" }
            if ($s -notmatch '(?i)iterate') { throw "iterate beat (ITERATE) not named" }
            if ($s -notmatch '/personal-workflow|/personal-goal') { throw "no durable-run option (personal-workflow/personal-goal) named" }
            if ($s -notmatch '/ship|commit-push-pr') { throw "no ship path named" }
        }
    },
    @{
        Name = 'F05 choose_beat_present: recommend + a choose/AskUserQuestion mention'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?i)recommend')        { throw "recommendation beat missing" }
            if ($s -notmatch 'AskUserQuestion|choose|pick') { throw "choose beat missing" }
        }
    },
    @{
        Name = 'F06 verify_beat_present: VERIFY phase + screenshot documented'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?i)verif')     { throw "verify beat missing" }
            if ($s -notmatch '(?i)screenshot'){ throw "screenshot not documented" }
        }
    },
    @{
        Name = 'F07 no_chrome_mcp: SKILL.md does not reference the chrome MCP'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -match 'mcp__claude-in-chrome') { throw "chrome MCP referenced -- violates CLAUDE.md browsing rule" }
        }
    },
    @{
        Name = 'F08 ascii_only: SKILL.md + both references contain no non-ASCII bytes'
        Run = {
            foreach ($f in $AsciiFiles) {
                if (-not (Test-Path $f)) { throw "missing file: $f" }
                $bytes = [System.IO.File]::ReadAllBytes($f)
                for ($i = 0; $i -lt $bytes.Length; $i++) {
                    if ($bytes[$i] -gt 127) {
                        throw ("non-ASCII byte 0x{0:X2} at offset {1} in {2}" -f $bytes[$i], $i, (Split-Path $f -Leaf))
                    }
                }
            }
        }
    },
    @{
        Name = 'F09 model_guidance: a Model selection section names both sonnet and opus'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?im)^##\s+Model selection') { throw "Model selection section missing" }
            if ($s -notmatch '(?i)\bsonnet\b') { throw "sonnet tier not named" }
            if ($s -notmatch '(?i)\bopus\b')   { throw "opus tier not named" }
        }
    },
    @{
        Name = 'F10 fidelity_principle: fidelity-from-real-artifacts stated'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?i)fidelity')      { throw "fidelity principle missing" }
            if ($s -notmatch '(?i)real artifacts') { throw "real-artifacts framing missing" }
        }
    },
    @{
        Name = 'F11 gates_separate: behavior gate and visual gate documented separately'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?i)behavior gate') { throw "behavior gate missing" }
            if ($s -notmatch '(?i)visual gate')   { throw "visual gate missing" }
        }
    },
    @{
        Name = 'F12 tournament_beat: --tournament escalation names personal-critic-gate'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '--tournament')        { throw "--tournament flag/beat missing" }
            if ($s -notmatch 'personal-critic-gate'){ throw "critic-gate selection not named" }
        }
    },
    @{
        Name = 'F13 referential_integrity: every scripts/*.py named in SKILL resolves on disk'
        Run = {
            $s = Get-Content $Skill -Raw
            $names = [regex]::Matches($s, 'scripts/([A-Za-z0-9_\-]+\.py)') | ForEach-Object { $_.Groups[1].Value } | Select-Object -Unique
            if (@($names).Count -eq 0) { throw "SKILL names no scripts/*.py (expected check_prototype.py)" }
            foreach ($n in $names) {
                if (-not (Test-Path (Join-Path $Scripts $n))) { throw "referenced script missing on disk: scripts/$n" }
            }
        }
    },
    @{
        Name = 'F14 check_script_calibration: good fixture CHECK-OK; every bad fixture CHECK-FAIL'
        Run = {
            $py = (Get-Command python -ErrorAction SilentlyContinue).Source
            if (-not $py) { $py = 'python' }
            $chk = Join-Path $Scripts 'check_prototype.py'
            if (-not (Test-Path $chk)) { throw "check_prototype.py missing" }
            $good = Join-Path $Fixtures 'good-prototype.html'
            $out = & $py $chk $good 2>&1 | Out-String
            if ($LASTEXITCODE -ne 0 -or $out -notmatch 'CHECK-OK') { throw "good fixture did not pass: $out" }
            $bads = @(
                @{ f = 'bad-external-img.html';   a = @() },
                @{ f = 'bad-fixed-footer.html';   a = @() },
                @{ f = 'bad-nonascii.html';       a = @() },
                @{ f = 'bad-missing-marker.html'; a = @('--marker','Allocate') }
            )
            foreach ($b in $bads) {
                $fp = Join-Path $Fixtures $b.f
                if (-not (Test-Path $fp)) { throw "fixture missing: $($b.f)" }
                $o = & $py $chk $fp @($b.a) 2>&1 | Out-String
                if ($LASTEXITCODE -eq 0 -or $o -notmatch 'CHECK-FAIL') { throw "$($b.f) should CHECK-FAIL but did not: $o" }
            }
        }
    }
)

$pass = 0; $fail = 0
foreach ($t in $tests) {
    try { & $t.Run; $pass++; Write-Host "PASS $($t.Name)" -ForegroundColor Green }
    catch { $fail++; Write-Host "FAIL $($t.Name): $_" -ForegroundColor Red }
}
if ($fail -eq 0) { Write-Host "EVAL PASS personal-prototype ($pass)" -ForegroundColor Green; exit 0 }
else { Write-Host "EVAL FAIL personal-prototype ($fail of $($pass+$fail))" -ForegroundColor Red; exit 1 }
