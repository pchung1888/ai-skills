#requires -Version 7
# Eval grader for personal-fable-mode. See evals/eval-plan.md for the failure-mode map.
# Deterministic red/green grader. Exit 0 = all checks pass; exit 1 = at least one fails.
# ASCII only (no em-dashes/smart-quotes -- Windows PowerShell 5.1 cp1252 pitfall).
$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'

$SkillDir = Resolve-Path (Join-Path $PSScriptRoot '..')
$Skill    = Join-Path $SkillDir 'SKILL.md'

# The five gates ARE the skill. Smells table and ecosystem notes reference
# them by name; losing one silently breaks the loop.
$gates = @(
    'Scope before work',
    'Evidence before reasoning',
    'Reason adversarially',
    'Verify before declaring done',
    'Report calibrated'
)

# Shared by the real graders AND the calibration mutations below, so the two
# can never desync: a calibration test exercises the same code path it certifies.
function Test-GateNames([string]$text) {
    # Returns the first missing/renamed gate heading, or $null if all present.
    for ($i = 0; $i -lt $gates.Count; $i++) {
        $n = $i + 1
        if ($text -notmatch "Gate $n - $([regex]::Escape($gates[$i]))") { return "Gate $n - $($gates[$i])" }
    }
    return $null
}

# Full CLAUDE.md ASCII rule: ALL Unicode dashes (em, en, figure, horizontal bar,
# minus sign), smart quotes, ellipsis, arrows, and NBSP.
$BannedChars = [char[]]@(0x2014, 0x2013, 0x2012, 0x2015, 0x2212,
                         0x2018, 0x2019, 0x201C, 0x201D,
                         0x2026, 0x2192, 0x21D2, 0x00A0)
function Find-BannedChar([string]$text) {
    # Returns @{Char;Offset} for the first banned char, or $null if clean.
    foreach ($ch in $BannedChars) {
        $idx = $text.IndexOf($ch)
        if ($idx -ge 0) { return @{ Char = $ch; Offset = $idx } }
    }
    return $null
}

$tests = @(
    @{
        Name = 'skill_frontmatter: right name, description present, "fable mode" trigger phrase kept'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?m)^name:\s*personal-fable-mode\s*$') { throw "frontmatter name not personal-fable-mode" }
            if ($s -notmatch '(?m)^description:\s*\S') { throw "frontmatter description missing" }
            if ($s -notmatch '(?i)"fable mode"') { throw 'activation phrase "fable mode" missing from skill' }
        }
    },
    @{
        Name = 'model_inherit: model key present and set to inherit (skill upgrades the running model)'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?m)^model:\s*inherit\s*$') { throw "model: inherit missing or changed" }
        }
    },
    @{
        Name = 'five_gates: all five gate names present, numbered 1-5'
        Run = {
            $s = Get-Content $Skill -Raw
            $missing = Test-GateNames $s
            if ($missing) { throw "gate missing or renamed: $missing" }
        }
    },
    @{
        Name = 'contract_lines: verification-layer rule + Honesty Protocol labels + smells + effort dial'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch [regex]::Escape('"It ran" is not verification')) { throw "verification-layer rule missing" }
            if ($s -notmatch 'EXTRACTED / INFERRED / SUGGESTION /\s*UNKNOWN') { throw "Honesty Protocol label set missing" }
            if ($s -notmatch '(?i)Smells that mean a gate got skipped') { throw "smells section missing" }
            if ($s -notmatch '(?i)effort dial') { throw "effort dial section missing" }
            if ($s -notmatch '3-5 for a medium task') { throw "effort scaling numbers missing" }
        }
    },
    @{
        Name = 'ascii_purity: no unicode dashes (em/en/figure/bar/minus), smart quotes, ellipsis, arrows, or NBSP in SKILL.md'
        Run = {
            $hit = Find-BannedChar ([System.IO.File]::ReadAllText($Skill))
            if ($hit) { throw ("banned non-ASCII char U+{0:X4} at offset {1}" -f [int]$hit.Char, $hit.Offset) }
        }
    },
    @{
        Name = 'calibration: a mutated copy missing Gate 3 FAILS the gate grader'
        Run = {
            $s = Get-Content $Skill -Raw
            $bad = $s -replace 'Gate 3 - Reason adversarially', 'Gate 3 - Think hard'
            if (-not (Test-GateNames $bad)) { throw "gate grader passed a copy without Reason adversarially -- dead metric" }
        }
    },
    @{
        Name = 'calibration: a mutated copy with an em-dash FAILS the ascii grader'
        Run = {
            $s = Get-Content $Skill -Raw
            $bad = $s -replace 'Gate 1 - Scope', ('Gate 1 ' + [char]0x2014 + ' Scope')
            if (-not (Find-BannedChar $bad)) { throw "ascii grader passed a copy containing an em-dash -- dead metric" }
        }
    }
)

$pass = 0; $fail = 0
foreach ($t in $tests) {
    try { & $t.Run; $pass++; Write-Host "PASS $($t.Name)" -ForegroundColor Green }
    catch { $fail++; Write-Host "FAIL $($t.Name): $_" -ForegroundColor Red }
}
if ($fail -eq 0) { Write-Host "EVAL PASS personal-fable-mode ($pass)" -ForegroundColor Green; exit 0 }
else { Write-Host "EVAL FAIL personal-fable-mode ($fail of $($pass+$fail))" -ForegroundColor Red; exit 1 }
