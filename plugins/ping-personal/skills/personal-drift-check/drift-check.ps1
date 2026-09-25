# drift-check.ps1 -- measure harness drift from Claude Code transcripts.
#
# Harness drift = the assistant progressively stops gathering evidence and
# stops behaving like the skill that was invoked, WITHOUT any user action and
# WITHOUT context compaction. See docs/harness-drift/ in the personal-plugin
# repo for the analysis this script operationalizes.
#
# Two independent signals are read from the JSONL transcript:
#
#   ADHERENCE  = share of tool calls that gather evidence (Read/Grep/Glob).
#                This is the LEADING indicator -- it collapses first.
#   ATTRIBUTION= share of tool calls the harness still stamps with
#                `attributionSkill`. This is the LAGGING indicator -- the
#                harness keeps crediting the skill for roughly one decile
#                after the behavior has already gone.
#
# Reading them together is the point: adherence falling while attribution is
# still 100% is the actual drift event. Waiting for attribution to fall means
# noticing one decile late.
#
# Usage:
#   pwsh drift-check.ps1                      # current project, latest session
#   pwsh drift-check.ps1 -Deciles 10          # granularity of the decay table
#   pwsh drift-check.ps1 -SessionFile <path>  # one specific transcript
#   pwsh drift-check.ps1 -ProjectDir  <path>  # override project dir
#   pwsh drift-check.ps1 -Cohort <glob>       # aggregate many sessions
#   pwsh drift-check.ps1 -Json                # machine-readable output

[CmdletBinding()]
param(
    [int]$Deciles = 10,
    [string]$SessionFile,
    [string]$ProjectDir,
    [string[]]$Cohort,
    [switch]$Json
)

$ErrorActionPreference = 'Stop'

# Tools that constitute looking at reality before speaking about it.
$EvidenceTools = @('Read', 'Grep', 'Glob')
# Tools that change the world. Tracked to show where the freed share went.
$ActionTools   = @('Edit', 'Write', 'NotebookEdit')
# Shell tools. Dual-use (can inspect or mutate), so reported separately.
$ShellTools    = @('Bash', 'PowerShell')

# The denominator. Deliberately NOT "every tool call": meta/UI calls
# (TaskUpdate, ToolSearch, AskUserQuestion, Skill), MCP calls, and Agent are
# excluded, because none of them is a choice between looking and acting --
# counting them dilutes the signal and makes the ratio depend on how chatty
# the harness UI happens to be that week.
#
# This list is calibrated against docs/harness-drift/2026-08-07-harness-drift-facts.md:
# it reproduces that analysis's denominators exactly (BASELINE 375, RECENT 733),
# so this meter's output is directly comparable to the published baseline.
# `Agent` is excluded from the denominator but reported separately -- delegating
# should never look like a drop in evidence share.
$WorkTools = $EvidenceTools + $ActionTools + $ShellTools

# Shell commands that inspect rather than change. Used to compute the companion
# "probe share" so that investigating via `grep`/`Select-String`/`git log`
# instead of the Read tool does not read as drift. Deliberately conservative:
# if a command mixes inspection and mutation, the mutating pattern wins.
$ReadOnlyShell = '(?i)\b(grep|rg|Select-String|cat|Get-Content|head|tail|less|wc|ls|dir|Get-ChildItem|find|Test-Path|stat|file|diff|git\s+(log|diff|status|show|blame|branch|remote|rev-parse)|Measure-Object|ConvertFrom-Json|Where-Object)\b'
$MutatingShell = '(?i)(\b(rm|del|mv|cp|Remove-Item|Set-Content|Out-File|New-Item|Copy-Item|Move-Item|npm|pip|dotnet|msbuild|git\s+(commit|push|add|checkout|reset|merge|rebase))\b|>|>>)'

function Get-ProjectSlugFromPath {
    param([string]$Path)
    # Mirrors personal-cache-stats: Claude Code sanitizes the project path by
    # replacing every non-alphanumeric character with a dash.
    return ($Path -replace '[^A-Za-z0-9]', '-')
}

function Resolve-Transcripts {
    $projectsRoot = Join-Path $env:USERPROFILE '.claude\projects'

    if ($Cohort) {
        # Each entry is a wildcard path (PowerShell globbing, not regex).
        # Pass several to build a cohort from specific sessions:
        #   -Cohort "<dir>\4542c564*.jsonl","<dir>\fb6a4425*.jsonl"
        $items = @($Cohort | ForEach-Object {
            Get-ChildItem -Path $_ -ErrorAction SilentlyContinue
        } | Sort-Object FullName -Unique)
        if (-not $items) { throw "Cohort pattern matched no files: $($Cohort -join ', ')" }
        return $items
    }
    if ($SessionFile) {
        return @(Get-Item -LiteralPath $SessionFile)
    }

    $dir = $ProjectDir
    if (-not $dir) {
        $dir = Join-Path $projectsRoot (Get-ProjectSlugFromPath (Get-Location).Path)
    }

    if (Test-Path $dir) {
        $candidates = @(Get-ChildItem (Join-Path $dir '*.jsonl') -ErrorAction SilentlyContinue)
    }
    else {
        Write-Host "Project dir not found ($dir); searching all transcripts..." -ForegroundColor Yellow
        $candidates = @(Get-ChildItem (Join-Path $projectsRoot '*\*.jsonl') -ErrorAction SilentlyContinue)
    }
    if (-not $candidates) { throw "No transcripts found under $projectsRoot" }

    return @($candidates | Sort-Object LastWriteTime -Descending | Select-Object -First 1)
}

function Read-ToolCalls {
    param([string]$Path)
    $calls = [System.Collections.Generic.List[object]]::new()
    $sidechain = 0
    foreach ($line in [System.IO.File]::ReadLines($Path)) {
        # Cheap prefilter: skip lines that cannot contain a tool call. Keeps
        # multi-MB transcripts streaming instead of parsing every record.
        if ($line -notlike '*"tool_use"*') { continue }
        try { $o = $line | ConvertFrom-Json } catch { continue }
        if ($o.type -ne 'assistant') { continue }
        # Subagent turns are excluded so the meter reports MAIN-session
        # behavior only. On CLI 2.1.224 these do not appear in the project
        # transcript at all, but the guard is kept: if a future build starts
        # writing them here, an unfiltered meter would silently read as
        # healthy because subagents do gather evidence.
        if ($o.isSidechain -eq $true) { $sidechain++; continue }
        foreach ($b in $o.message.content) {
            if ($b.type -ne 'tool_use') { continue }
            # Keep only the tools the denominator is defined over, plus Agent
            # (reported separately). Everything else is harness noise.
            if (($WorkTools -notcontains $b.name) -and ($b.name -ne 'Agent')) { continue }
            # A shell call that only inspects (grep, cat, git log, Select-String)
            # IS evidence gathering -- it just does not use the Read tool. Flag
            # it so a session that probes via the shell is not mislabelled as
            # drifted. This does NOT enter the calibrated evidence numerator;
            # it is reported as a separate companion signal.
            $probe = $false
            if ($ShellTools -contains $b.name) {
                $cmd = [string]$b.input.command
                $probe = ($cmd -match $ReadOnlyShell) -and ($cmd -notmatch $MutatingShell)
            }
            $calls.Add([pscustomobject]@{
                Tool  = [string]$b.name
                Attr  = [string]$o.attributionSkill
                Probe = $probe
                Stamp = [string]$o.timestamp
            })
        }
    }
    return [pscustomobject]@{ Calls = $calls; Sidechain = $sidechain }
}

function Measure-Slice {
    param($Slice)
    # Agent rides along in the slice for reporting but is not in the denominator.
    $ag   = @($Slice | Where-Object { $_.Tool -eq 'Agent' }).Count
    $work = @($Slice | Where-Object { $WorkTools -contains $_.Tool })
    $n = $work.Count
    if ($n -eq 0) { return $null }
    $ev = @($work | Where-Object { $EvidenceTools -contains $_.Tool }).Count
    $ac = @($work | Where-Object { $ActionTools   -contains $_.Tool }).Count
    $sh = @($work | Where-Object { $ShellTools    -contains $_.Tool }).Count
    $at = @($work | Where-Object { $_.Attr -ne '' }).Count
    # Probe share = evidence tools PLUS read-only shell calls. Broader than the
    # calibrated evidence share; answers "did it look at anything at all".
    $pr = $ev + @($work | Where-Object { $_.Probe }).Count
    return [pscustomobject]@{
        Calls       = $n
        Evidence    = $ev
        EvidencePct = [math]::Round($ev / $n * 100, 1)
        Action      = $ac
        ActionPct   = [math]::Round($ac / $n * 100, 1)
        Shell       = $sh
        ShellPct    = [math]::Round($sh / $n * 100, 1)
        Agent       = $ag
        Attributed  = $at
        AttrPct     = [math]::Round($at / $n * 100, 1)
        Probe       = $pr
        ProbePct    = [math]::Round($pr / $n * 100, 1)
    }
}

# ---------------------------------------------------------------- main

$targets = Resolve-Transcripts
$all = [System.Collections.Generic.List[object]]::new()
$perSession = [System.Collections.Generic.List[object]]::new()
$sidechainTotal = 0

foreach ($t in $targets) {
    $r = Read-ToolCalls -Path $t.FullName
    $sidechainTotal += $r.Sidechain
    if ($r.Calls.Count -eq 0) { continue }
    foreach ($c in $r.Calls) { $all.Add($c) }
    $m = Measure-Slice $r.Calls
    $perSession.Add([pscustomobject]@{
        Session     = $t.Name.Substring(0, [math]::Min(8, $t.Name.Length))
        Calls       = $m.Calls
        EvidencePct = $m.EvidencePct
        ShellPct    = $m.ShellPct
        ActionPct   = $m.ActionPct
        Agent       = $m.Agent
        AttrPct     = $m.AttrPct
    })
}

if ($all.Count -eq 0) {
    Write-Host "No main-session tool calls found in the selected transcript(s)." -ForegroundColor Yellow
    exit 0
}

$overall = Measure-Slice $all

# Decay table. Only meaningful for a single session -- across a cohort the
# concatenation order is arbitrary, so it is suppressed.
$decay = @()
if ($targets.Count -eq 1 -and $all.Count -ge $Deciles) {
    $bucket = [math]::Ceiling($all.Count / $Deciles)
    for ($d = 0; $d -lt $Deciles; $d++) {
        $lo = $d * $bucket
        if ($lo -ge $all.Count) { break }
        $hi = [math]::Min(($d + 1) * $bucket - 1, $all.Count - 1)
        $m = Measure-Slice $all[$lo..$hi]
        $decay += [pscustomobject]@{
            Part = $d + 1; Calls = $m.Calls
            EvidencePct = $m.EvidencePct; AttrPct = $m.AttrPct
        }
    }
}

# Verdict. Thresholds come from the measured cohorts in
# docs/harness-drift/2026-08-07-harness-drift-facts.md: a healthy BASELINE
# session ran 38.4% evidence share, the drifted RECENT window ran 10.6%.
$verdict = switch ($true) {
    ($overall.EvidencePct -ge 30) { 'HEALTHY  -- evidence share at or above the good-session baseline'; break }
    ($overall.EvidencePct -ge 20) { 'WATCH    -- below baseline, above the drifted window'; break }
    ($overall.EvidencePct -ge 10) { 'DRIFTED  -- matches the measured problem window'; break }
    default                       { 'SEVERE   -- the session is acting almost without looking' }
}

# Guard against the meter's main false positive: a session that investigates
# with `grep`/`git log`/`Select-String` instead of the Read tool scores low on
# the calibrated metric while genuinely gathering evidence. Detected by a probe
# share that is far healthier than the evidence share.
$shellProbeCaveat = ($overall.EvidencePct -lt 20) -and ($overall.ProbePct -ge 30)

# The cliff: first part where evidence share falls below a third of part 1.
$cliff = $null
if ($decay.Count -ge 2) {
    $first = $decay[0].EvidencePct
    foreach ($row in $decay[1..($decay.Count - 1)]) {
        if ($first -gt 0 -and $row.EvidencePct -lt ($first / 3)) { $cliff = $row; break }
    }
}

if ($Json) {
    [pscustomobject]@{
        sessions      = $targets.Count
        totalCalls    = $overall.Calls
        evidencePct   = $overall.EvidencePct
        probePct      = $overall.ProbePct
        shellProbeCaveat = $shellProbeCaveat
        shellPct      = $overall.ShellPct
        actionPct     = $overall.ActionPct
        agentCalls    = $overall.Agent
        attributedPct = $overall.AttrPct
        verdict       = $verdict.Split('--')[0].Trim()
        cliffAtPart   = if ($cliff) { $cliff.Part } else { $null }
        cliffAtCall   = if ($cliff) { ($cliff.Part - 1) * [math]::Ceiling($all.Count / $Deciles) } else { $null }
        decay         = $decay
        perSession    = $perSession
    } | ConvertTo-Json -Depth 5
    exit 0
}

Write-Host ""
Write-Host "Harness drift check"
Write-Host "Sessions : $($targets.Count)   Main-session tool calls : $($overall.Calls)"
if ($sidechainTotal -gt 0) { Write-Host "Excluded : $sidechainTotal subagent tool calls" }
Write-Host ""
Write-Host ("Evidence  (Read/Grep/Glob) : {0,6}  {1,5}%   <- the calibrated signal" -f $overall.Evidence, $overall.EvidencePct)
Write-Host ("Probe     (+ read-only sh) : {0,6}  {1,5}%   <- did it look at ANYTHING" -f $overall.Probe, $overall.ProbePct)
Write-Host ("Shell     (Bash/PowerShell): {0,6}  {1,5}%" -f $overall.Shell, $overall.ShellPct)
Write-Host ("Action    (Edit/Write)     : {0,6}  {1,5}%" -f $overall.Action, $overall.ActionPct)
Write-Host ("Delegated (Agent)          : {0,6}" -f $overall.Agent)
Write-Host ("Skill-attributed calls     : {0,6}  {1,5}%" -f $overall.Attributed, $overall.AttrPct)
Write-Host ""
Write-Host "Verdict  : $verdict"
Write-Host "Reference: healthy baseline 38.4% | drifted window 10.6% (docs/harness-drift)"
if ($shellProbeCaveat) {
    Write-Host ""
    Write-Host "CAVEAT: evidence share is low but probe share is $($overall.ProbePct)%. This session is" -ForegroundColor Yellow
    Write-Host "        investigating via read-only shell commands rather than the Read tool." -ForegroundColor Yellow
    Write-Host "        That is evidence gathering. Treat the DRIFTED verdict as unproven here." -ForegroundColor Yellow
}
Write-Host ""

if ($decay.Count -gt 0) {
    Write-Host "Decay across the session (part 1 = earliest calls):"
    Write-Host ""
    Write-Host "  part |  calls | evidence% | attributed% | "
    Write-Host "  -----+--------+-----------+-------------+------------------"
    foreach ($row in $decay) {
        $bar = '#' * [math]::Round($row.EvidencePct / 5)
        "  {0,4} | {1,6} | {2,8}% | {3,10}% | {4}" -f $row.Part, $row.Calls, $row.EvidencePct, $row.AttrPct, $bar
    }
    Write-Host ""
    if ($cliff) {
        $approxCall = ($cliff.Part - 1) * [math]::Ceiling($all.Count / $Deciles)
        Write-Host ("CLIFF: evidence share collapsed at part {0} (~tool call {1}), while the harness" -f $cliff.Part, $approxCall)
        Write-Host ("       still attributed {0}% of those calls to the invoked skill." -f $cliff.AttrPct)
        Write-Host "       Adherence leads, attribution lags. Do not wait for attribution to fall."
        Write-Host ""
    }
}

if ($perSession.Count -gt 1) {
    Write-Host "Per session:"
    $perSession | Format-Table -AutoSize Session, Calls, EvidencePct, ShellPct, ActionPct, Agent, AttrPct
}
