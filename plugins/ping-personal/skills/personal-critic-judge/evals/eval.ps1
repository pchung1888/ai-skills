#requires -Version 7
# Eval grader for personal-critic-judge. See evals/eval-plan.md for the failure-mode map.
# Deterministic red/green grader. Exit 0 = all checks pass; exit 1 = at least one fails.
#
# Usage:
#   pwsh eval.ps1                       # run every check
#   pwsh eval.ps1 -TableFile table.md   # grade one saved judge table
#                                       # Example: the table a judge returned in a host-app review
[CmdletBinding()]
param([string]$TableFile)
$ErrorActionPreference = 'Stop'

$Skill    = Join-Path (Resolve-Path (Join-Path $PSScriptRoot '..')) 'SKILL.md'
$Fixtures = Join-Path $PSScriptRoot 'fixtures'
$Header   = '| # | Finding | Seats | Real | In scope | When | Why |'
$WhenOk   = @('fix now', 'later', 'later - flagged for the owner', 'never')

function Read-Text([string]$Path) { (Get-Content $Path -Raw) -replace "`r`n", "`n" }

# Returns the list of problems in one judge table. An empty list means the table is valid.
function Get-TableProblems([string]$Text) {
    $problems = [System.Collections.Generic.List[string]]::new()
    $rows = @(($Text -replace "`r`n", "`n") -split "`n" | Where-Object { $_ -match '^\|' })
    if (-not $rows -or $rows[0].Trim() -ne $Header) { $problems.Add("missing column: header must be $Header"); return , $problems }
    $v = [regex]::Match($Text, '(?m)^VERDICT: (FIX|CLEAN) \((\d+) fix now, (\d+) flagged, (\d+) later, (\d+) never\)')
    if (-not $v.Success) { $problems.Add('missing verdict: first line must be VERDICT: FIX or CLEAN (<n> fix now, <n> flagged, <n> later, <n> never)') }
    $count = @{ 'fix now' = 0; 'later - flagged for the owner' = 0; 'later' = 0; 'never' = 0 }
    foreach ($r in $rows[2..($rows.Count - 1)]) {
        $c = @($r.Trim().Trim('|') -split '\|' | ForEach-Object { $_.Trim() })
        if ($c.Count -ne 7) { $problems.Add("row has $($c.Count) cells, needs 7: $r"); continue }
        $id, $finding, $real, $scope, $when = $c[0], $c[1], $c[3], $c[4], $c[5]
        if ($real -notin @('yes', 'no') -or $scope -notin @('yes', 'no')) { $problems.Add("row ${id}: Real and In scope must be yes or no") }
        if ($when -notin $WhenOk) { $problems.Add("row ${id}: When must be one of: $($WhenOk -join ', ')") }
        if ($when -eq 'fix now' -and ($real -ne 'yes' -or $scope -ne 'yes')) { $problems.Add("row ${id}: fix now needs Real yes and In scope yes") }
        if ($finding -like '`[floor`]*' -and $when -eq 'never') { $problems.Add("row ${id}: floor finding ruled never") }
        $why = $c[6]
        if ($when -eq 'fix now' -and $why -notmatch 'EXTRACTED') { $problems.Add("row ${id}: fix now Why must say EXTRACTED (the judge re-read the code)") }
        if ($when -eq 'later - flagged for the owner' -and $why -notmatch 'EXTRACTED' -and $why -notmatch '^UNKNOWN') { $problems.Add("row ${id}: flagged Why must say EXTRACTED or start with UNKNOWN") }
        if ($count.ContainsKey($when)) { $count[$when]++ }
    }
    if ($v.Success) {
        $want = @([int]$v.Groups[2].Value, [int]$v.Groups[3].Value, [int]$v.Groups[4].Value, [int]$v.Groups[5].Value)
        $got = @($count['fix now'], $count['later - flagged for the owner'], $count['later'], $count['never'])
        if (($want -join ',') -ne ($got -join ',')) { $problems.Add("verdict counts $($want -join ',') do not match table $($got -join ',')") }
        if (($v.Groups[1].Value -eq 'FIX') -ne ($got[0] -gt 0)) { $problems.Add('verdict word: FIX needs at least one fix now row, CLEAN needs none') }
    }
    return , $problems
}

if ($TableFile) {
    $p = Get-TableProblems (Read-Text $TableFile)
    if ($p.Count -eq 0) { Write-Host "TABLE PASS $TableFile" -ForegroundColor Green; exit 0 }
    $p | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
    Write-Host "TABLE FAIL $TableFile ($($p.Count) problems)" -ForegroundColor Red; exit 1
}

$tests = @(
    @{
        Name = 'skill_frontmatter: name, description, ASCII, no trigger taken from personal-critic-gate'
        Run = {
            $s = Read-Text $Skill
            if ($s -notmatch '(?m)^name:\s*personal-critic-judge\s*$') { throw "frontmatter name not personal-critic-judge" }
            if ($s -notmatch '(?m)^description:\s*Use when') { throw "description must start with 'Use when'" }
            $desc = ([regex]::Match($s, '(?m)^description:(.*)$')).Groups[1].Value
            foreach ($t in @('critic gate this', 'gate this before ship')) { if ($desc -match [regex]::Escape($t)) { throw "description uses '$t', which personal-critic-gate owns" } }
            $bad = @([System.IO.File]::ReadAllBytes($Skill) | Where-Object { $_ -gt 127 }).Count
            if ($bad) { throw "$bad non-ASCII bytes in SKILL.md" }
        }
    },
    @{
        Name = 'skill_contract: SKILL.md keeps the inputs, seats, judge rules, floor and verify pass'
        Run = {
            $s = Read-Text $Skill
            $keys = @('Main goal', 'Subtask', 'Review purpose', 'stop and ask', 'Seats return findings only', 'claim-blind',
                'ms-mario', 'amanda', 'maggie', 'rhea', 'iris', 'Real?', 'In scope?', 'fix now', 'new capability',
                'Safety floor', '[floor]', 'floor_guard.py', 'verify pass', 'finds nothing new', 'no second panel',
                $Header, 'light run', 'Domain Routing Table', 'Seat 5 is in every run', 'English, ASCII only',
                'cheap probe', 'sizing probe', 'Never put a pipe', 'VERDICT: FIX', 'VERDICT: CLEAN', 'Reviewed: <sha>',
                'Saving the run', 'Never replace or strip', 'UNATTENDED', 'owner list', 'personal-critic-gate')
            foreach ($k in $keys) { if ($s -notmatch [regex]::Escape($k)) { throw "SKILL.md lost: $k" } }
        }
    },
    @{
        Name = 'calibration: good-*.md tables pass, bad-*.md tables fail'
        Run = {
            foreach ($f in Get-ChildItem $Fixtures -Filter 'good-*.md') {
                $p = Get-TableProblems (Read-Text $f.FullName)
                if ($p.Count) { throw "$($f.Name) failed: $($p -join '; ')" }
            }
            foreach ($f in Get-ChildItem $Fixtures -Filter 'bad-*.md') {
                if ((Get-TableProblems (Read-Text $f.FullName)).Count -eq 0) { throw "$($f.Name) passed but should fail" }
            }
        }
    },
    @{
        Name = 'table_rules: each bad table raises its own message'
        Run = {
            $expect = @{
                'bad-missing-column.md'      = 'missing column'
                'bad-fixnow-out-of-scope.md' = 'fix now needs Real yes and In scope yes'
                'bad-floor-never.md'         = 'floor finding ruled never'
                'bad-when-value.md'          = 'When must be'
                'bad-real-cell-text.md'      = 'Real and In scope must be yes or no'
                'bad-pipe-in-cell.md'        = 'cells, needs 7'
                'bad-verdict-count.md'       = 'do not match table'
                'bad-verdict-missing.md'     = 'missing verdict'
                'bad-fixnow-not-reread.md'   = 'fix now Why must say EXTRACTED'
            }
            foreach ($k in $expect.Keys) {
                $p = Get-TableProblems (Read-Text (Join-Path $Fixtures $k))
                if (-not ($p | Where-Object { $_ -like "*$($expect[$k])*" })) { throw "$k did not raise '$($expect[$k])' (got: $($p -join '; '))" }
            }
        }
    }
)

$pass = 0; $fail = 0
foreach ($t in $tests) {
    try { & $t.Run; $pass++; Write-Host "PASS $($t.Name)" -ForegroundColor Green }
    catch { $fail++; Write-Host "FAIL $($t.Name): $_" -ForegroundColor Red }
}
if ($fail -eq 0) { Write-Host "EVAL PASS personal-critic-judge ($pass)" -ForegroundColor Green; exit 0 }
else { Write-Host "EVAL FAIL personal-critic-judge ($fail of $($pass+$fail))" -ForegroundColor Red; exit 1 }
