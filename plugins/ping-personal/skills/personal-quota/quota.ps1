# quota.ps1 -- report REAL Claude usage (5h session, weekly, context) for the current account.
#
# Data-flow (verified 2026-07-15 against ccstatusline v2.2.23 + live files):
#   SESSION / WEEKLY quota originate at Anthropic:
#     GET https://api.anthropic.com/api/oauth/usage
#     Authorization: Bearer <claudeAiOauth.accessToken from ~/.claude/.credentials.json>
#     anthropic-beta: oauth-2025-04-20
#   This is the SUBSCRIPTION OAuth token Claude Code already uses on the Team plan --
#   NOT the paid developer API, no separate key, no per-token cost (it reports usage).
#   ccstatusline is just a CLIENT that caches that response to ~/.cache/ccstatusline/usage.json.
#
#   CONTEXT % is native Claude Code data piped to the statusline command's stdin as
#   .context_window.used_percentage. A skill cannot read that stdin, so the ctx-sidecar
#   shim persists it to ~/.cache/personal-quota/ctx.json for this script to read.
#
# Resolution order (LOCKED design decision -- cache-first, OAuth fallback):
#   1. usage.json fresh?  (age < FreshnessMinutes AND resets not in the past) -> use it (free, no network)
#   2. else fetch /api/oauth/usage with the subscription token                  -> use it (ccstatusline-independent)
#   3. else                                                                     -> stale cache flagged STALE, or UNKNOWN
#
# SECURITY: the access token is read into a variable and sent ONLY as a request header.
#           It is NEVER printed, logged, or included in any output path (incl. -Json).
#
# Usage:
#   pwsh -NoProfile -File quota.ps1                 # normal: cache-first, OAuth fallback
#   pwsh -NoProfile -File quota.ps1 -Json           # machine-readable object (no token field)
#   pwsh -NoProfile -File quota.ps1 -NoFetch        # cache-only, never touch the network
#   pwsh -NoProfile -File quota.ps1 -FreshnessMinutes 5
# Test-injection hooks (used by evals; not for normal use):
#   -UsageJsonPath -CtxJsonPath -CredentialsPath -Now "<iso8601>" -SnapshotDir -CodexDir
#   pwsh -NoProfile -File quota.ps1 -Provider claude|codex|all   # JSON array of
#     {provider, window (5h|7d), percentUsed, resetsAt, source, ageSec}; claude order is
#     mod snapshot (<15 min old) -> OAuth fetch -> ccstatusline cache if present.
#   No -Provider: Claude report, unless run from Codex (CLAUDECODE unset and CODEX_SANDBOX,
#     CODEX_SANDBOX_NETWORK_DISABLED, CODEX_THREAD_ID or CODEX_HOME set) -> same as -Provider codex.

[CmdletBinding()]
param(
    [switch]$Json,
    [switch]$NoFetch,
    [int]$FreshnessMinutes = 15,
    [string]$UsageJsonPath,
    [string]$CtxJsonPath,
    [string]$CredentialsPath,
    [string]$UsageUrlOverride,   # test hook: point the fetch at an unreachable URL to exercise the error path offline
    [string]$Now,
    [ValidateSet('claude','codex','all')][string]$Provider,
    [string]$SnapshotDir,   # default ~/.claude/live-usage (ping-hud mod snapshots)
    [string]$CodexDir       # default ~/.codex/sessions (Codex rollout-*.jsonl logs)
)

$ErrorActionPreference = 'Stop'

# ---- paths (overridable for tests) --------------------------------------------------------------
$home_ = $env:USERPROFILE
if (-not $home_) { $home_ = $HOME }
if (-not $UsageJsonPath)   { $UsageJsonPath   = Join-Path $home_ '.cache\ccstatusline\usage.json' }
if (-not $CtxJsonPath)     { $CtxJsonPath     = Join-Path $home_ '.cache\personal-quota\ctx.json' }
if (-not $CredentialsPath) { $CredentialsPath = Join-Path $home_ '.claude\.credentials.json' }

$USAGE_URL   = if ($UsageUrlOverride) { $UsageUrlOverride } else { 'https://api.anthropic.com/api/oauth/usage' }
$OAUTH_BETA  = 'oauth-2025-04-20'
# NB: use a distinct name from the -Now param. PowerShell variable names are case-insensitive,
# so a variable named $now would alias the [string]-typed $Now param and be coerced to string.
$nowTs = if ($Now) { [datetimeoffset]::Parse($Now) } else { [datetimeoffset]::Now }

# ---- helpers ------------------------------------------------------------------------------------
function ConvertTo-EasternLabel {
    # Format a DateTimeOffset into "HH:mm ET" (EST/EDT) plus a "resets in Xd Yh Zm" delta.
    # $Reset is [object] not [datetimeoffset]: a value-type param can never be $null (it coerces
    # to MinValue), which would make the missing-reset guard below dead code and render year-0001.
    param([object]$Reset, [datetimeoffset]$From)
    if ($null -eq $Reset) { return @{ at = 'unknown'; inText = 'unknown' } }
    $Reset = [datetimeoffset]$Reset
    $local = $Reset.ToLocalTime()
    $offH  = $local.Offset.TotalHours
    $zone  = switch ($offH) { -4 { 'EDT' } -5 { 'EST' } default { 'UTC{0:+0;-0}' -f $offH } }
    # Same calendar day? show HH:mm; else show "Mon DD HH:mm".
    $sameDay = $local.Date -eq $From.ToLocalTime().Date
    $at = if ($sameDay) { '{0:HH:mm} {1}' -f $local, $zone } else { '{0:MMM d HH:mm} {1}' -f $local, $zone }

    $span = $Reset - $From
    $inText =
        if ($span.TotalSeconds -le 0) { 'now (reset elapsed)' }
        elseif ($span.TotalDays -ge 1) { '{0}d {1}h' -f [int]$span.Days, [int]$span.Hours }
        elseif ($span.TotalHours -ge 1) { '{0}h {1}m' -f [int]$span.Hours, [int]$span.Minutes }
        else { '{0}m' -f [int]$span.Minutes }
    return @{ at = $at; inText = $inText }
}

function Get-CacheUsage {
    # Read ccstatusline's usage.json. Returns a normalized hashtable or $null.
    if (-not (Test-Path -LiteralPath $UsageJsonPath)) { return $null }
    try {
        $raw = Get-Content -LiteralPath $UsageJsonPath -Raw
        $o = $raw | ConvertFrom-Json
    } catch { return $null }
    # Guard the parse too: a corrupt-but-valid-JSON cache (bad date/pct) must fall back, not crash.
    try {
    $mtime = [datetimeoffset](Get-Item -LiteralPath $UsageJsonPath).LastWriteTime
    $ageMin = ($nowTs - $mtime).TotalMinutes
    $sessReset = if ($o.sessionResetAt) { [datetimeoffset]::Parse([string]$o.sessionResetAt) } else { $null }
    $wkReset   = if ($o.weeklyResetAt)  { [datetimeoffset]::Parse([string]$o.weeklyResetAt) }  else { $null }
    $resetPast = ($sessReset -and $sessReset -lt $nowTs) -or ($wkReset -and $wkReset -lt $nowTs)
    $scoped = @()
    if ([int]$o.weeklyOpusUsage   -gt 0) { $scoped += @{ label = 'Opus';   pct = [int]$o.weeklyOpusUsage } }
    if ([int]$o.weeklySonnetUsage -gt 0) { $scoped += @{ label = 'Sonnet'; pct = [int]$o.weeklySonnetUsage } }
    return @{
        sessionPct   = [int]$o.sessionUsage
        sessionReset = $sessReset
        weeklyPct    = [int]$o.weeklyUsage
        weeklyReset  = $wkReset
        scoped       = $scoped
        ageMin       = [math]::Round($ageMin, 1)
        fresh        = ($ageMin -le $FreshnessMinutes) -and (-not $resetPast)
    }
    } catch { return $null }
}

function Get-LiveUsage {
    # Fetch /api/oauth/usage with the subscription token. Returns normalized hashtable or $null.
    # The token is used ONLY in the Authorization header and never returned/printed.
    if (-not (Test-Path -LiteralPath $CredentialsPath)) { return $null }
    try {
        $cred = Get-Content -LiteralPath $CredentialsPath -Raw | ConvertFrom-Json
        $tok  = $cred.claudeAiOauth.accessToken
    } catch { return $null }
    if (-not $tok) { return $null }
    $headers = @{
        'Authorization'  = "Bearer $tok"
        'anthropic-beta' = $OAUTH_BETA
        'User-Agent'     = 'personal-quota'
    }
    try {
        $r = Invoke-RestMethod -Uri $USAGE_URL -Headers $headers -Method Get -TimeoutSec 10
    } catch {
        return $null
    } finally {
        $tok = $null; $headers = $null   # drop the secret from memory ASAP
    }

    # Prefer the current limits[] array; fall back to top-level five_hour / seven_day.
    # Guarded: the endpoint shape is reverse-engineered, so a changed field type/format must fall
    # back (return null -> caller uses cache or reports UNKNOWN), never throw and crash the skill.
    try {
    $sessPct = $null; $sessReset = $null; $wkPct = $null; $wkReset = $null; $scoped = @()
    if ($r.limits) {
        foreach ($lim in $r.limits) {
            switch ($lim.kind) {
                'session'    { $sessPct = [int]$lim.percent; if ($lim.resets_at) { $sessReset = [datetimeoffset]::Parse([string]$lim.resets_at) } }
                'weekly_all' { $wkPct   = [int]$lim.percent; if ($lim.resets_at) { $wkReset   = [datetimeoffset]::Parse([string]$lim.resets_at) } }
                'weekly_scoped' {
                    $label = if ($lim.scope.model.display_name) { [string]$lim.scope.model.display_name } else { 'scoped' }
                    $scoped += @{ label = $label; pct = [int]$lim.percent }
                }
            }
        }
    }
    if ($null -eq $sessPct -and $r.five_hour) { $sessPct = [int]$r.five_hour.utilization; if ($r.five_hour.resets_at) { $sessReset = [datetimeoffset]::Parse([string]$r.five_hour.resets_at) } }
    if ($null -eq $wkPct   -and $r.seven_day) { $wkPct   = [int]$r.seven_day.utilization; if ($r.seven_day.resets_at) { $wkReset   = [datetimeoffset]::Parse([string]$r.seven_day.resets_at) } }
    if ($null -eq $sessPct -and $null -eq $wkPct) { return $null }
    return @{
        sessionPct = $sessPct; sessionReset = $sessReset
        weeklyPct  = $wkPct;   weeklyReset  = $wkReset
        scoped     = $scoped
    }
    } catch { return $null }
}

function Get-Context {
    if (-not (Test-Path -LiteralPath $CtxJsonPath)) { return $null }
    try {
        $c = Get-Content -LiteralPath $CtxJsonPath -Raw | ConvertFrom-Json
    } catch { return $null }
    if ($null -eq $c.contextPct) { return $null }
    $ctxAge = $null
    if ($c.ts) { try { $ctxAge = [math]::Round(($nowTs - [datetimeoffset]::Parse([string]$c.ts)).TotalMinutes, 1) } catch {} }
    return @{ pct = [int]$c.contextPct; model = [string]$c.model; ageMin = $ctxAge }
}

# ---- -Provider mode: one entry shape for Claude and Codex --------------------------------------
function Get-SnapshotEntries {
    # Newest ping-hud snapshot; torn/invalid JSON or older than 15 min = no snapshot.
    if (-not (Test-Path -LiteralPath $SnapshotDir)) { return @() }
    $f = Get-ChildItem -LiteralPath $SnapshotDir -Filter '*.json' -File -ErrorAction SilentlyContinue |
         Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $f) { return @() }
    try {
        $o = Get-Content -LiteralPath $f.FullName -Raw | ConvertFrom-Json
        $w = $o.writtenAt; $wt = if ($w -is [datetime]) { [datetimeoffset]$w.ToUniversalTime() } else { [datetimeoffset]::Parse([string]$w) }
        $age = [int]($nowTs - $wt).TotalSeconds
        if ($age -gt 900 -or $age -lt -60) { return @() }
        return @($o.claude | Where-Object { $_.window -in '5h','7d' } | ForEach-Object {
            [ordered]@{ provider = 'claude'; window = $_.window; percentUsed = $_.percentUsed
                        resetsAt = $_.resetsAt; source = 'mod-snapshot'; ageSec = $age } })
    } catch { return @() }
}

function ConvertTo-ClaudeEntries {
    param($D, [string]$Src, $AgeSec)
    $iso = { param($t) if ($t) { $t.ToString('o') } else { $null } }
    return @(
        [ordered]@{ provider = 'claude'; window = '5h'; percentUsed = $D.sessionPct; resetsAt = (& $iso $D.sessionReset); source = $Src; ageSec = $AgeSec },
        [ordered]@{ provider = 'claude'; window = '7d'; percentUsed = $D.weeklyPct;  resetsAt = (& $iso $D.weeklyReset);  source = $Src; ageSec = $AgeSec })
}

function Get-CodexEntries {
    # Newest rollout-*.jsonl -> its last rate_limits line (same rules as the mod's parseCodex).
    if (-not (Test-Path -LiteralPath $CodexDir)) { return @() }
    $f = Get-ChildItem -LiteralPath $CodexDir -Recurse -Filter 'rollout-*.jsonl' -File -ErrorAction SilentlyContinue |
         Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $f) { return @() }
    $lines = @(Get-Content -LiteralPath $f.FullName)
    for ($i = $lines.Count - 1; $i -ge 0; $i--) {
        if ($lines[$i] -notmatch '"rate_limits"') { continue }
        try { $rl = ($lines[$i] | ConvertFrom-Json).payload.rate_limits } catch { continue }
        if (-not $rl) { continue }
        $out = @()
        foreach ($w in @($rl.primary, $rl.secondary)) {
            if ($null -eq $w -or $null -eq $w.used_percent) { continue }
            $win = switch ([int]$w.window_minutes) { 300 { '5h' } 10080 { '7d' } default { $null } }
            if (-not $win) { continue }
            $reset = [datetimeoffset]::FromUnixTimeSeconds([long]$w.resets_at)
            $pct = if ($reset -le $nowTs) { 0 } else { $w.used_percent }
            $out += [ordered]@{ provider = 'codex'; window = $win; percentUsed = $pct; resetsAt = $reset.ToString('o'); source = 'codex-log'; ageSec = $null }
        }
        if ($out.Count) { return $out }
    }
    return @()
}

# No -Provider: report the runtime that called us. Claude Code sets CLAUDECODE=1 (checked first,
# because Claude sessions can carry CODEX_COMPANION_* vars); a Codex marker var means Codex.
if (-not $Provider -and -not $env:CLAUDECODE -and
    ($env:CODEX_SANDBOX -or $env:CODEX_SANDBOX_NETWORK_DISABLED -or $env:CODEX_THREAD_ID -or $env:CODEX_HOME)) {
    $Provider = 'codex'
}

if ($Provider) {
    if (-not $SnapshotDir) { $SnapshotDir = Join-Path $home_ '.claude\live-usage' }
    if (-not $CodexDir)    { $CodexDir    = Join-Path $home_ '.codex\sessions' }
    $entries = @()
    if ($Provider -in 'claude','all') {
        $claude = @(Get-SnapshotEntries)
        if (-not $claude.Count -and -not $NoFetch) {
            $live = Get-LiveUsage
            if ($live) { $claude = ConvertTo-ClaudeEntries $live 'oauth' 0 }
        }
        if (-not $claude.Count) {
            $c = Get-CacheUsage
            if ($c) { $claude = ConvertTo-ClaudeEntries $c 'ccstatusline-cache' ([int]($c.ageMin * 60)) }
        }
        $entries += $claude
    }
    if ($Provider -in 'codex','all') { $entries += @(Get-CodexEntries) }
    ConvertTo-Json -InputObject @($entries) -Depth 4
    exit 0
}

# ---- resolve quota (cache-first, OAuth fallback) ------------------------------------------------
$source = $null
$data   = $null
$stale  = $false

$cache = Get-CacheUsage
if ($cache -and $cache.fresh) {
    $data = $cache
    $source = "cache ($($cache.ageMin)m old)"
}
elseif (-not $NoFetch) {
    $live = Get-LiveUsage
    if ($live) {
        $data = $live
        $source = 'live fetch (oauth/usage)'
    }
}

if (-not $data -and $cache) {
    # network failed or -NoFetch: fall back to the (stale) cache, flagged.
    $data = $cache
    $stale = $true
    $source = "STALE cache ($($cache.ageMin)m old)"
}

$ctx = Get-Context

# ---- emit -------------------------------------------------------------------------------------
if ($Json) {
    # Machine-readable. NO token field, by construction.
    $out = [ordered]@{
        source     = $source
        stale      = $stale
        sessionPct = if ($data) { $data.sessionPct } else { $null }
        weeklyPct  = if ($data) { $data.weeklyPct }  else { $null }
        scoped     = if ($data) { $data.scoped } else { @() }
        sessionReset = if ($data -and $data.sessionReset) { $data.sessionReset.ToString('o') } else { $null }
        weeklyReset  = if ($data -and $data.weeklyReset)  { $data.weeklyReset.ToString('o') }  else { $null }
        contextPct = if ($ctx) { $ctx.pct } else { $null }
        contextAvailable = [bool]$ctx
    }
    $out | ConvertTo-Json -Depth 6
    exit 0
}

Write-Host ""
# .claude.json has case-conflicting project-path keys; plain ConvertFrom-Json throws on them,
# so parse -AsHashtable and read only the small oauthAccount block.
$acct = try { (Get-Content -LiteralPath (Join-Path $home_ '.claude.json') -Raw | ConvertFrom-Json -AsHashtable)['oauthAccount']['emailAddress'] } catch { $null }
$hdr = if ($acct) { "Claude Usage -- $acct" } else { "Claude Usage" }
Write-Host $hdr

if (-not $data) {
    Write-Host "  Session / Weekly : UNKNOWN -- no fresh cache and no fetch." -ForegroundColor Yellow
    if ($NoFetch) { Write-Host "  (ran with -NoFetch; ccstatusline cache is missing or unreadable)" }
    else { Write-Host "  (usage.json missing/stale AND the /api/oauth/usage fetch failed -- token expired or offline)" }
}
else {
    $s = ConvertTo-EasternLabel -Reset $data.sessionReset -From $nowTs
    $w = ConvertTo-EasternLabel -Reset $data.weeklyReset  -From $nowTs
    $sess = '{0,3}%' -f $data.sessionPct
    $wk   = '{0,3}%' -f $data.weeklyPct
    Write-Host ("  5h session   {0}   resets in {1}  ({2})" -f $sess, $s.inText, $s.at)
    $wkLine = "  Weekly       {0}   resets in {1}  ({2})" -f $wk, $w.inText, $w.at
    if ($data.scoped -and $data.scoped.Count -gt 0) {
        $wkLine += '   ' + (($data.scoped | ForEach-Object { '{0} {1}%' -f $_.label, $_.pct }) -join '  ')
    }
    Write-Host $wkLine
    if ($stale) { Write-Host "  !! STALE -- statusline not rendering; numbers may be out of date." -ForegroundColor Yellow }
}

if ($ctx) {
    $ctxAgeNote = if ($null -ne $ctx.ageMin) { " ({0}m old)" -f $ctx.ageMin } else { "" }
    Write-Host ("  Context      {0,3}%{1}" -f $ctx.pct, $ctxAgeNote)
} else {
    Write-Host "  Context       n/a   (sidecar not active -- see 'enable-ctx' in SKILL.md)"
}

Write-Host ""
Write-Host ("  source: {0}" -f $source) -ForegroundColor DarkGray
Write-Host ""
