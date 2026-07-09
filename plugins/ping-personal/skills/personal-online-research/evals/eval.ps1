#requires -Version 7
# Eval grader for personal-online-research. See evals/eval-plan.md for the failure-mode map.
# Deterministic red/green grader. Exit 0 = all checks pass; exit 1 = at least one fails.
# ASCII only (no em-dashes/smart-quotes -- Windows PowerShell 5.1 cp1252 pitfall).
$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'

$SkillDir = Resolve-Path (Join-Path $PSScriptRoot '..')
$Skill    = Join-Path $SkillDir 'SKILL.md'

# Shared by real graders and calibration mutations (never desync).
$Modes = @('## Mode: lookup', '## Mode: brief', '## Mode: storm')
function Find-MissingPhrase([string]$text, [string[]]$phrases) {
    return @($phrases | Where-Object { $text -notmatch [regex]::Escape($_) })
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
        Name = 'skill_frontmatter: right name, description, "online research" trigger, model inherit'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?m)^name:\s*personal-online-research\s*$') { throw "frontmatter name wrong" }
            if ($s -notmatch '(?m)^description:\s*\S') { throw "description missing" }
            if ($s -notmatch '(?i)"online research"') { throw 'trigger phrase "online research" missing' }
            if ($s -notmatch '(?m)^model:\s*inherit\s*$') { throw "model: inherit missing" }
        }
    },
    @{
        Name = 'three_modes: lookup, brief, and storm mode sections all present'
        Run = {
            $missing = Find-MissingPhrase (Get-Content $Skill -Raw) $Modes
            if ($missing.Count -gt 0) { throw "missing mode sections: $($missing -join ', ')" }
        }
    },
    @{
        Name = 'fetch_contract: firecrawl conventions kept (status check, .firecrawl/, quoted URLs, no re-scrape, degrade path)'
        Run = {
            $s = Get-Content $Skill -Raw
            foreach ($p in @('firecrawl --status', '.firecrawl/', 'quote URLs', 'never re-scrape', 'WebSearch')) {
                if ($s -notmatch [regex]::Escape($p)) { throw "fetch contract line missing: $p" }
            }
        }
    },
    @{
        Name = 'verification_contract: banner + UNVERIFIED handling + labels + fable-mode anchor'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch 'N/N checked') { throw "verification banner format missing" }
            if ($s -notmatch 'UNVERIFIED') { throw "UNVERIFIED verdict handling missing" }
            if ($s -notmatch 'EXTRACTED') { throw "Honesty Protocol labels missing" }
            if ($s -notmatch 'personal-fable-mode') { throw "fable-mode anchor missing" }
            if ($s -notmatch '(?i)DO NOT SKIP') { throw "verification phase not marked mandatory" }
        }
    },
    @{
        Name = 'budget_gate: storm fan-outs require confirmation per Process Budget rules'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?i)CONFIRM[^\r\n]*fan-out|fan-out[^\r\n]*CONFIRM') { throw "fan-out confirmation gate missing" }
            if ($s -notmatch '(?i)Process Budget') { throw "Process Budget rule reference missing" }
        }
    },
    @{
        Name = 'ascii_purity: no unicode dashes, smart quotes, ellipsis, arrows, or NBSP'
        Run = {
            $hit = Find-BannedChar ([System.IO.File]::ReadAllText($Skill))
            if ($hit) { throw ("banned non-ASCII char U+{0:X4} at offset {1}" -f [int]$hit.Char, $hit.Offset) }
        }
    },
    @{
        Name = 'calibration: a copy missing storm mode FAILS the mode grader'
        Run = {
            $bad = (Get-Content $Skill -Raw) -replace '## Mode: storm', '## Mode: tempest'
            if ((Find-MissingPhrase $bad $Modes).Count -eq 0) { throw "mode grader passed a copy without storm -- dead metric" }
        }
    },
    @{
        Name = 'calibration: a copy with an em-dash FAILS the ascii grader'
        Run = {
            $bad = (Get-Content $Skill -Raw) -replace 'Mode routing', ('Mode ' + [char]0x2014 + ' routing')
            if (-not (Find-BannedChar $bad)) { throw "ascii grader passed a copy containing an em-dash -- dead metric" }
        }
    }
)

$pass = 0; $fail = 0
foreach ($t in $tests) {
    try { & $t.Run; $pass++; Write-Host "PASS $($t.Name)" -ForegroundColor Green }
    catch { $fail++; Write-Host "FAIL $($t.Name): $_" -ForegroundColor Red }
}
if ($fail -eq 0) { Write-Host "EVAL PASS personal-online-research ($pass)" -ForegroundColor Green; exit 0 }
else { Write-Host "EVAL FAIL personal-online-research ($fail of $($pass+$fail))" -ForegroundColor Red; exit 1 }
