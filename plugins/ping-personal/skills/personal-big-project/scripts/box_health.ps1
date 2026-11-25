# Read-only machine-health check for /personal-big-project. A long unattended run can slow to a crawl
# while CPU and RAM look fine, because handles, the nonpaged pool, ephemeral ports or leftover
# processes run out first. This script only reads and reports. It never stops a process or changes a setting.
# Prints one line per check: "PASS|WARN|FAIL <name> <detail>", then HINT lines (commands the owner may run
# by hand), then NEW lines (with -StateDir), then a last line: BOX OK, BOX WARN (<n>) or BOX FAIL (<n>).
# Exit 1 only on FAIL. Runs on PowerShell 7 and Windows PowerShell 5.1.
#
# Example:
#   pwsh -NoProfile -File scripts/box_health.ps1 -StateDir docs/proj-123/autopilot

param(
    # Drive letters to watch. Example: C:,D:
    [string[]]$Disks = @('C:', 'D:'),
    # FAIL when a disk has less free space than this many GB. Example: 5
    [double]$MinGB = 5,
    # WARN when available RAM is below this many MB. Example: 4096
    [int]$MinAvailMB = 4096,
    # WARN when committed memory is above this percent of the commit limit (FAIL above 95). Example: 85
    [int]$MaxCommitPct = 85,
    # WARN when the total handle count of all processes is above this. Example: 600000
    [long]$MaxHandles = 600000,
    # WARN when the nonpaged pool is above this many MB. Example: 1500
    [int]$MaxNonpagedMB = 1500,
    # A process older than this many hours counts as a leftover. Example: 12
    [int]$OrphanHours = 12,
    # Process names to count as possible leftovers (claude is only counted, never flagged).
    # Example: codex,node,pwsh
    [string[]]$OrphanNames = @('codex', 'node', 'pwsh', 'powershell', 'conhost', 'bash', 'dotnet'),
    # How many hours back to scan the System event log. Example: 12
    [int]$EventHours = 12,
    # Run folder (the one with log/). Appends a row to log/box-health.md and prints NEW lines. Example: docs/proj-123/autopilot
    [string]$StateDir = '',
    # Print one JSON object instead of text lines.
    [switch]$Json,
    # Test only: read probe values from this JSON file instead of the live box. Example: C:\temp\fake.json
    [string]$FakeJson = ''
)
$ErrorActionPreference = 'Stop'
$checks = New-Object System.Collections.ArrayList
$hints = New-Object System.Collections.ArrayList
function Add-Check($status, $name, $detail) { [void]$checks.Add([pscustomobject]@{ name = $name; status = $status; detail = $detail }) }

# --- probes: live box, or the fake file in tests ---
$now = Get-Date
if ($FakeJson) {
    $f = Get-Content -LiteralPath $FakeJson -Raw | ConvertFrom-Json
    $disk = @{}; foreach ($p in $f.diskFreeGB.PSObject.Properties) { $disk[$p.Name] = [double]$p.Value }
    $availMB = [double]$f.availMB; $commitPct = [double]$f.commitPct
    $totalHandles = [long]$f.totalHandles; $topName = [string]$f.topProc.name; $topHandles = [long]$f.topProc.handles
    $poolMB = [double]$f.nonpagedMB
    $procs = @($f.procs | ForEach-Object { [pscustomobject]@{ Name = $_.name; Start = $now.AddHours(-[double]$_.ageHours) } })
    $eventIds = @($f.eventIds | ForEach-Object { [int]$_ })
    $hookGaps = @($f.hooks | ForEach-Object { "$($_.plugin) $($_.event)" })
    $hookError = ''
} else {
    $disk = @{}
    foreach ($d in $Disks) { try { $disk[$d] = [IO.DriveInfo]::new($d).AvailableFreeSpace / 1GB } catch { $disk[$d] = $null } }
    $os = Get-CimInstance Win32_OperatingSystem
    $availMB = $os.FreePhysicalMemory / 1KB
    $commitPct = ($os.TotalVirtualMemorySize - $os.FreeVirtualMemory) * 100 / $os.TotalVirtualMemorySize
    $all = @(Get-Process)
    $totalHandles = [long]($all | Measure-Object Handles -Sum).Sum
    $top = $all | Sort-Object Handles -Descending | Select-Object -First 1
    $topName = $top.ProcessName; $topHandles = [long]$top.Handles
    $procs = @($all | ForEach-Object { $st = $null; try { $st = $_.StartTime } catch { }; [pscustomobject]@{ Name = $_.ProcessName; Start = $st } })
    try { $poolMB = (Get-Counter '\Memory\Pool Nonpaged Bytes' -ErrorAction Stop).CounterSamples[0].CookedValue / 1MB }
    catch { $poolMB = (Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory).PoolNonpagedBytes / 1MB }
    $eventIds = @()
    try {
        $eventIds = @(Get-WinEvent -FilterHashtable @{ LogName = 'System'; Id = 2004, 10010, 4231, 243, 244; StartTime = $now.AddHours(-$EventHours) } -ErrorAction Stop | ForEach-Object { $_.Id })
    } catch { }   # "no events found" is an error to Get-WinEvent; it means zero here
    $hookGaps = @(); $hookError = ''
    try {
        $claudeHome = Join-Path $HOME '.claude'
        $settings = Get-Content -LiteralPath (Join-Path $claudeHome 'settings.json') -Raw | ConvertFrom-Json
        $enabled = @($settings.enabledPlugins.PSObject.Properties | Where-Object { $_.Value -eq $true } | ForEach-Object { $_.Name })
        foreach ($key in $enabled) {
            $plugin, $market = $key -split '@', 2
            $base = Join-Path $claudeHome "plugins/cache/$market/$plugin"
            if (-not (Test-Path -LiteralPath $base)) { continue }
            $ver = Get-ChildItem -LiteralPath $base -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1
            if (-not $ver) { continue }
            $hooksFile = Join-Path $ver.FullName 'hooks/hooks.json'
            $manifest = Join-Path $ver.FullName '.claude-plugin/plugin.json'
            $inline = $null
            if (Test-Path -LiteralPath $manifest) {
                $m = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
                if ($m.hooks -is [string]) { $hooksFile = Join-Path $ver.FullName $m.hooks }
                elseif ($m.hooks) { $inline = $m.hooks }
            }
            $h = $inline
            if (-not $h -and (Test-Path -LiteralPath $hooksFile)) { $h = (Get-Content -LiteralPath $hooksFile -Raw | ConvertFrom-Json).hooks }
            if (-not $h) { continue }
            foreach ($ev in 'UserPromptSubmit', 'PreToolUse', 'SessionStart') {
                foreach ($group in @($h.$ev)) {
                    foreach ($cmd in @($group.hooks)) {
                        if ($cmd.type -eq 'command' -and $null -eq $cmd.timeout) { $hookGaps += "$plugin $ev" }
                    }
                }
            }
        }
    } catch { $hookError = $_.Exception.Message }
}

# --- box-disk ---
$low = @(); $parts = @()
foreach ($d in $Disks) {
    $v = $disk[$d]
    if ($null -eq $v) { $parts += "$d absent"; continue }
    $parts += ('{0} {1:N1} GB' -f $d, $v)
    if ($v -lt $MinGB) { $low += $d }
}
if ($low) { Add-Check FAIL box-disk ("below $MinGB GB on $($low -join ',') (" + ($parts -join ', ') + ')') }
else { Add-Check PASS box-disk ($parts -join ', ') }

# --- box-memory ---
$memDetail = ('available {0:N0} MB, commit {1:N0}%' -f $availMB, $commitPct)
if ($commitPct -gt 95) { Add-Check FAIL box-memory "$memDetail (commit above 95%)" }
elseif ($availMB -lt $MinAvailMB) { Add-Check WARN box-memory "$memDetail (available below $MinAvailMB MB)" }
elseif ($commitPct -gt $MaxCommitPct) { Add-Check WARN box-memory "$memDetail (commit above $MaxCommitPct%)" }
else { Add-Check PASS box-memory $memDetail }

# --- box-handles ---
$hd = "total $totalHandles, top $topName $topHandles"
if ($topHandles -gt 1000000) { Add-Check WARN box-handles "$hd (one process holds over 1M handles: likely a leak)" }
elseif ($totalHandles -gt $MaxHandles) { Add-Check WARN box-handles "$hd (total above $MaxHandles)" }
else { Add-Check PASS box-handles $hd }

# --- box-pool ---
$pd = ('nonpaged pool {0:N0} MB' -f $poolMB)
if ($poolMB -gt $MaxNonpagedMB) { Add-Check WARN box-pool "$pd (above $MaxNonpagedMB MB)" } else { Add-Check PASS box-pool $pd }

# --- box-orphans ---
$cut = $now.AddHours(-$OrphanHours)
$od = @(); $orphanWarn = $false; $hintNames = @()
foreach ($n in $OrphanNames) {
    $old = @($procs | Where-Object { $_.Name -eq $n -and $_.Start -and $_.Start -lt $cut } | Sort-Object Start)
    if ($old.Count -eq 0) { continue }
    $od += ('{0}={1} (oldest {2:MM-dd HH:mm})' -f $n, $old.Count, $old[0].Start)
    if ($n -in 'codex', 'node' -or $old.Count -gt 10) { $orphanWarn = $true }
    if ($n -in 'codex', 'node') { $hintNames += $n }
}
$od += 'claude=' + @($procs | Where-Object { $_.Name -eq 'claude' }).Count + ' (counted, never flagged)'
if ($orphanWarn) { Add-Check WARN box-orphans ("older than $OrphanHours h: " + ($od -join '; ')) }
else { Add-Check PASS box-orphans ("none older than $OrphanHours h; " + ($od -join '; ')) }
foreach ($n in $hintNames) {
    $note = if ($n -eq 'node') { ' (check live sessions first: node also runs MCP servers of open sessions)' } else { '' }
    [void]$hints.Add("HINT close old ${n}${note}: Get-Process $n | Where-Object { `$_.StartTime -lt (Get-Date).AddHours(-$OrphanHours) } | Stop-Process")
}

# --- box-events ---
$ev = @($eventIds | Group-Object | Sort-Object Name | ForEach-Object { "id $($_.Name) x$($_.Count)" })
if ($eventIds.Count -gt 0) { Add-Check WARN box-events ("$($eventIds.Count) in last $EventHours h: " + ($ev -join ', ') + ' (2004 resources, 10010 DCOM, 4231 ephemeral ports, 243/244 desktop heap)') }
else { Add-Check PASS box-events "none in last $EventHours h" }

# --- box-hooks ---
if ($hookError) { Add-Check WARN box-hooks "could not read: $hookError" }
elseif ($hookGaps.Count -gt 0) {
    Add-Check WARN box-hooks ((($hookGaps | Select-Object -Unique) -join ', ') + ' have no timeout. Default is 30 s; on a starved box each such event can stall up to 30 s.')
} else { Add-Check PASS box-hooks 'every UserPromptSubmit, PreToolUse, SessionStart command hook declares a timeout' }

# --- result ---
$nFail = @($checks | Where-Object status -eq 'FAIL').Count
$nWarn = @($checks | Where-Object status -eq 'WARN').Count
$result = if ($nFail) { "BOX FAIL ($nFail)" } elseif ($nWarn) { "BOX WARN ($nWarn)" } else { 'BOX OK' }
$bad = @($checks | Where-Object status -ne 'PASS' | ForEach-Object { $_.name })

# --- state log: one row per run; NEW = problems none of the last 4 rows had ---
$new = @()
if ($StateDir) {
    $log = Join-Path $StateDir 'log/box-health.md'
    $prev = @()
    if (Test-Path -LiteralPath $log) {
        # The last 4 rows, so a warning that clears for a tick and comes back is not phoned again; the first
        # row is pre-flight check 17's run, so warnings the owner accepted at the door are never new.
        $recent = @(Get-Content -LiteralPath $log | Where-Object { $_ -like '| *' -and $_ -notlike '| When *' -and $_ -notlike '|---*' }) | Select-Object -Last 4
        foreach ($row in $recent) { $prev += @(($row -split '\|')[3].Trim() -split ',' | Where-Object { $_ -and $_ -ne '-' }) }
    } else {
        New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null
        Set-Content -LiteralPath $log -Encoding ASCII -Value @('| When | Result | Warnings |', '|---|---|---|')
    }
    $word = if ($result -eq 'BOX OK') { 'OK' } else { ($result -split ' ')[1] }
    $cell = if ($bad) { $bad -join ',' } else { '-' }
    Add-Content -LiteralPath $log -Encoding ASCII -Value ('| {0} | {1} | {2} |' -f (Get-Date -Format 'ddd MM-dd HH:mm'), $word, $cell)
    $new = @($bad | Where-Object { $_ -notin $prev })
}

if ($Json) {
    [pscustomobject]@{ checks = @($checks); result = $result; hints = @($hints); new = @($new) } | ConvertTo-Json -Depth 4
} else {
    foreach ($c in $checks) { "$($c.status) $($c.name) $($c.detail)" }
    foreach ($h2 in $hints) { $h2 }
    foreach ($n in $new) { "NEW $n" }
    $result
}
if ($nFail) { exit 1 } else { exit 0 }
