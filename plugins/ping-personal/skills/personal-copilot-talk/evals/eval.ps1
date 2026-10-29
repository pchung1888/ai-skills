#requires -Version 7
# Eval grader for personal-copilot-talk. See evals/eval-plan.md for the failure-mode map.
# Deterministic red/green grader. Exit 0 = all checks pass; exit 1 = at least one fails.
#
# Usage:
#   pwsh eval.ps1                      # run every check
#   pwsh eval.ps1 -ReplyFile reply.md  # grade one saved reply against the reply shape only
#                                      # Example: a reply a test session wrote to the scratchpad
[CmdletBinding()]
param([string]$ReplyFile)
$ErrorActionPreference = 'Stop'

$Skill    = Join-Path (Resolve-Path (Join-Path $PSScriptRoot '..')) 'SKILL.md'
$Fixtures = Join-Path $PSScriptRoot 'fixtures'
$MaxWords = 20   # ASD-STE100 cap for procedural sentences

function Read-Text([string]$Path) { (Get-Content $Path -Raw) -replace "`r`n", "`n" }

# Returns the list of reply-shape problems in one reply. An empty list means the shape is right.
function Get-ShapeProblems([string]$Text) {
    $problems = [System.Collections.Generic.List[string]]::new()
    $Text = $Text -replace "`r`n", "`n"

    # Fenced blocks are code. Everything else is prose.
    $p = [System.Collections.Generic.List[string]]::new(); $fence = $false
    foreach ($l in ($Text -split "`n")) {
        if ($l -match '^\s*(```|~~~)') { $fence = -not $fence; continue }
        if (-not $fence) { $p.Add($l) }
    }
    $heads = @($p | Where-Object { $_ -match '^\*\*' })

    if ($Text -match '[^\x00-\x7F]') { $problems.Add('non-ASCII character (em dash, smart quote, arrow)') }
    if ($p -match '^#{1,6}\s') { $problems.Add('markdown # heading; blocks use bold headings') }
    if ($Text -match '(?i)TL;DR') { $problems.Add('TL;DR section') }
    if ($p -match '(?i)^\W*(Insight|Mechanism)\b') { $problems.Add('Insight or mechanism block') }
    if ($heads.Count -gt 1 -and -not ($p -contains '---')) { $problems.Add('no --- line between blocks') }
    if (-not ($heads -match '^\*\*Tell me\b')) { $problems.Add('no **Tell me** block') }
    elseif ($heads[-1] -notmatch '^\*\*Tell me\b') { $problems.Add("**Tell me** is not the last block (last: $($heads[-1]))") }
    $steps = @($heads | Where-Object { $_ -match '^\*\*Step\s+\d' -and $_ -notmatch '(?i)\b(passed|failed)\.\*\*\s*$' }).Count
    if ($steps -gt 1) { $problems.Add("$steps step headings; one step per reply") }

    # Prose units: a list item or bold heading starts a unit, wrapped lines join it.
    $units = [System.Collections.Generic.List[string]]::new(); $cur = ''
    foreach ($l in $p) {
        if ($l.Trim() -eq '' -or $l -eq '---') { if ($cur) { $units.Add($cur) }; $cur = ''; continue }
        if ($l -match '^\s*([-*+]|\d+\.)\s' -or $l -match '^\*\*') { if ($cur) { $units.Add($cur) }; $cur = $l.Trim(); continue }
        $cur = ($cur + ' ' + $l.Trim()).Trim()
    }
    if ($cur) { $units.Add($cur) }

    # Inline code counts as one word. The list marker is stripped so "1." is not a sentence end.
    foreach ($u in $units) {
        $u = ($u -replace '`[^`]*`', 'CODE') -replace '^([-*+]|\d+\.)\s+', ''
        if ($u -match ';') { $problems.Add('semicolon in prose; write two sentences') }
        foreach ($s in ($u -split '(?<=[.!?]["'')*]*)\s+')) {
            $n = @($s -split '\s+' | Where-Object { $_ -match '\w' }).Count
            if ($n -gt $MaxWords) { $problems.Add("sentence of $n words: $($s.Substring(0, [Math]::Min(60, $s.Length)))...") }
        }
    }
    return , $problems
}

if ($ReplyFile) {
    $p = Get-ShapeProblems (Read-Text $ReplyFile)
    if ($p.Count -eq 0) { Write-Host "SHAPE PASS $ReplyFile" -ForegroundColor Green; exit 0 }
    $p | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
    Write-Host "SHAPE FAIL $ReplyFile ($($p.Count) problems)" -ForegroundColor Red; exit 1
}

$tests = @(
    @{
        Name = 'skill_frontmatter: name, description, ASCII, no trigger that collides with personal-wizard'
        Run = {
            $s = Read-Text $Skill
            if ($s -notmatch '(?m)^name:\s*personal-copilot-talk\s*$') { throw "frontmatter name not personal-copilot-talk" }
            if ($s -notmatch '(?m)^description:\s*Use when') { throw "description must start with 'Use when'" }
            $desc = ([regex]::Match($s, '(?m)^description:(.*)$')).Groups[1].Value
            if ($desc -match '(?i)walk me through') { throw "description uses 'walk me through', which personal-wizard owns" }
            $bad = @([System.IO.File]::ReadAllBytes($Skill) | Where-Object { $_ -gt 127 }).Count
            if ($bad) { throw "$bad non-ASCII bytes in SKILL.md" }
        }
    },
    @{
        Name = 'skill_contract: the talking-style rules are still in SKILL.md'
        Run = {
            $s = Read-Text $Skill
            foreach ($k in @('stop copilot talk', 'TL;DR', 'A `---` line', 'exactly one step', 'fenced code block',
                    'Stop here', 'never starts the next step', 'always the last block', 'smallest safe answer',
                    '20 words or fewer', '**Verdicts.**', '**One name, one verb.**', '**Condition first.**',
                    '**Single verbs.**', '**Full sentences.**', '**No new facts.**', '**No semicolons.**',
                    '**Your decision:', '**Honesty labels.**', 'speech-to-text')) {
                if ($s -notmatch [regex]::Escape($k)) { throw "SKILL.md lost: $k" }
            }
        }
    },
    @{
        Name = 'calibration: good-*.md fixtures pass, bad-*.md fixtures fail'
        Run = {
            foreach ($f in Get-ChildItem $Fixtures -Filter 'good-*.md') {
                $p = Get-ShapeProblems (Read-Text $f.FullName)
                if ($p.Count) { throw "$($f.Name) failed: $($p -join '; ')" }
            }
            foreach ($f in Get-ChildItem $Fixtures -Filter 'bad-*.md') {
                if ((Get-ShapeProblems (Read-Text $f.FullName)).Count -eq 0) { throw "$($f.Name) passed but should fail" }
            }
        }
    },
    @{
        Name = 'grader_live: each rule alone turns a good reply red with its own message'
        Run = {
            $base = Read-Text (Join-Path $Fixtures 'good-pass-then-step.md')
            $split = $base.LastIndexOf("---`n`n**Tell me")
            $head = $base.Substring(0, $split); $tail = $base.Substring($split)
            $long = 'This sentence is far too long because it keeps adding words that a person on a live box does not need to read now.'
            $mutants = @(
                @('two steps', ($head + "---`n`n**Step 2: next thing**`n`n" + $tail), 'step headings'),
                @('no Tell me', ($base -replace '\*\*Tell me', '**Report'), 'no **Tell me**'),
                @('Tell me not last', ($base + "`n---`n`n**Later, in the repo**`n`nFix it later.`n"), 'not the last block'),
                @('no --- line', ($base -replace '(?m)^---$', ''), 'no --- line'),
                @('hash heading', ("## Step 1b`n" + $base), '# heading'),
                @('TL;DR', ($head + "TL;DR`n`n" + $tail), 'TL;DR section'),
                @('Insight', ("* Insight: this step matters.`n`n" + $base), 'Insight'),
                @('long sentence', ($head + "$long`n`n" + $tail), 'sentence of'),
                @('em dash', ($head + "Wait " + [char]0x2014 + " here.`n`n" + $tail), 'non-ASCII'),
                @('semicolon', ($head + "Open SSMS, then connect; wait.`n`n" + $tail), 'semicolon')
            )
            foreach ($m in $mutants) {
                $p = Get-ShapeProblems $m[1]
                if (-not ($p | Where-Object { $_ -like "*$($m[2])*" })) { throw "mutant '$($m[0])' did not raise '$($m[2])' (got: $($p -join '; '))" }
            }
        }
    }
)

$pass = 0; $fail = 0
foreach ($t in $tests) {
    try { & $t.Run; $pass++; Write-Host "PASS $($t.Name)" -ForegroundColor Green }
    catch { $fail++; Write-Host "FAIL $($t.Name): $_" -ForegroundColor Red }
}
if ($fail -eq 0) { Write-Host "EVAL PASS personal-copilot-talk ($pass)" -ForegroundColor Green; exit 0 }
else { Write-Host "EVAL FAIL personal-copilot-talk ($fail of $($pass+$fail))" -ForegroundColor Red; exit 1 }
