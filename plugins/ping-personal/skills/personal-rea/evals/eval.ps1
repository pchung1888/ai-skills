#requires -Version 7
# Eval grader for personal-rea. See evals/eval-plan.md for the failure-mode map.
# Deterministic red/green grader. Exit 0 = all checks pass; exit 1 = at least one fails.
# ASCII only (no em-dashes/smart-quotes -- Windows PowerShell 5.1 cp1252 pitfall).
$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'

$SkillDir = Resolve-Path (Join-Path $PSScriptRoot '..')
$Skill    = Join-Path $SkillDir 'SKILL.md'

# Lines that keep the skill safe and honest. Shared by the real grader and the
# calibration mutation so the two cannot desync.
$contract = @(
    '**Authorization**',
    'ask whether analysis is allowed before any call',
    'Never help bypass licensing',
    'runs the\s+target with the user''s permissions: ask before doing it',
    'Do not install anything silently',
    'Load the `reverse-engineer-anything` skill',
    '`EXTRACTED`',
    '`INFERRED`',
    '`UNKNOWN`'
)
function Test-Contract([string]$text) {
    # Returns the first missing contract line, or $null if all present.
    foreach ($c in $contract) {
        $pat = if ($c -match '\\s') { $c } else { [regex]::Escape($c) }
        if ($text -notmatch $pat) { return $c }
    }
    return $null
}

$BannedChars = [char[]]@(0x2014, 0x2013, 0x2012, 0x2015, 0x2212,
                         0x2018, 0x2019, 0x201C, 0x201D,
                         0x2026, 0x2192, 0x21D2, 0x00A0)
function Find-BannedChar([string]$text) {
    foreach ($ch in $BannedChars) {
        $idx = $text.IndexOf($ch)
        if ($idx -ge 0) { return @{ Char = $ch; Offset = $idx } }
    }
    return $null
}

$tests = @(
    @{
        Name = 'skill_frontmatter: name, description, "use rea" and /personal-rea triggers'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?m)^name:\s*personal-rea\s*$') { throw "frontmatter name not personal-rea" }
            if ($s -notmatch '(?m)^description:\s*\S') { throw "frontmatter description missing" }
            if ($s -notmatch '"use rea"') { throw 'trigger "use rea" missing' }
            if ($s -notmatch '/personal-rea') { throw 'trigger /personal-rea missing' }
        }
    },
    @{
        Name = 'model_inherit: model key set to inherit'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?m)^model:\s*inherit\s*$') { throw "model: inherit missing or changed" }
        }
    },
    @{
        Name = 'safety_lines + delegates_routing + report_labels: contract lines present'
        Run = {
            $missing = Test-Contract (Get-Content $Skill -Raw)
            if ($missing) { throw "contract line missing: $missing" }
        }
    },
    @{
        Name = 'ascii_purity: no banned non-ASCII characters'
        Run = {
            $hit = Find-BannedChar ([System.IO.File]::ReadAllText($Skill))
            if ($hit) { throw ("banned non-ASCII char U+{0:X4} at offset {1}" -f [int]$hit.Char, $hit.Offset) }
        }
    },
    @{
        Name = 'calibration: a copy without the authorization ask FAILS the contract grader'
        Run = {
            $bad = (Get-Content $Skill -Raw) -replace 'ask whether analysis is allowed before any call', 'just analyze it'
            if (-not (Test-Contract $bad)) { throw "contract grader passed a copy without the authorization ask -- dead metric" }
        }
    },
    @{
        Name = 'calibration: a copy without the runtime-capture ask FAILS the contract grader'
        Run = {
            $bad = (Get-Content $Skill -Raw) -replace ': ask before doing it', ': go ahead'
            if (-not (Test-Contract $bad)) { throw "contract grader passed a copy without the runtime ask -- dead metric" }
        }
    },
    @{
        Name = 'calibration: a copy with an em-dash FAILS the ascii grader'
        Run = {
            $bad = (Get-Content $Skill -Raw) -replace 'Step 1 - Pin', ('Step 1 ' + [char]0x2014 + ' Pin')
            if (-not (Find-BannedChar $bad)) { throw "ascii grader passed a copy containing an em-dash -- dead metric" }
        }
    }
)

$pass = 0; $fail = 0
foreach ($t in $tests) {
    try { & $t.Run; $pass++; Write-Host "PASS $($t.Name)" -ForegroundColor Green }
    catch { $fail++; Write-Host "FAIL $($t.Name): $_" -ForegroundColor Red }
}
if ($fail -eq 0) { Write-Host "EVAL PASS personal-rea ($pass)" -ForegroundColor Green; exit 0 }
else { Write-Host "EVAL FAIL personal-rea ($fail of $($pass+$fail))" -ForegroundColor Red; exit 1 }
