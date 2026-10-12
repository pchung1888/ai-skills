#requires -Version 7
# Eval grader for personal-quota. See evals/eval-plan.md for the failure-mode map.
# Deterministic red/green grader. Exit 0 = all checks pass; exit 1 = at least one fails.
# Runnable standalone OR from plugins/ping-personal/evals/run-all.ps1 (auto-discovered by glob).
# ASCII only (no em-dashes/smart-quotes -- Windows PowerShell 5.1 cp1252 pitfall).
#
# The graders NEVER hit the network: every quota.ps1 invocation passes -NoFetch AND a bogus
# -CredentialsPath, so only the cache/context/token-safety paths are exercised. The live-fetch
# path needs a real token + network and is validated manually (see eval-plan.md "Not covered").
#
# Freshness is made deterministic + zone-robust: each fixture is copied to a temp file whose
# LastWriteTime is set RELATIVE to a single base instant, and -Now is that same base. Because
# .LocalDateTime + read-back-with-local-offset round-trips the instant, the (now - mtime) delta
# is preserved on any timezone, not just ET.

$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'   # cp1252 console guard

$SkillDir = Resolve-Path (Join-Path $PSScriptRoot '..')   # personal-quota/
$Skill    = Join-Path $SkillDir 'SKILL.md'
$Fix      = Join-Path $PSScriptRoot 'fixtures'
$Quota    = Join-Path $SkillDir 'quota.ps1'

$BASE   = [datetimeoffset]'2026-07-15T12:00:00-04:00'
$NONE   = Join-Path $PSScriptRoot '__nonexistent__.json'   # a path guaranteed not to exist

# Run quota.ps1 -Json against injected fixtures; return the parsed object.
# $ageMinutes sets the temp usage file's mtime to BASE minus that many minutes (freshness lever).
function Invoke-Quota {
    param([string]$Usage, [string]$Ctx, [int]$AgeMinutes = 5,
          [switch]$AllowFetch, [string]$CredFixture, [string]$UrlOverride)
    $usagePath = $NONE
    if ($Usage) {
        $usagePath = Join-Path ([System.IO.Path]::GetTempPath()) ("pq-usage-{0}.json" -f ([guid]::NewGuid().ToString('N')))
        Copy-Item -LiteralPath (Join-Path $Fix $Usage) -Destination $usagePath -Force
        (Get-Item -LiteralPath $usagePath).LastWriteTime = $BASE.AddMinutes(-$AgeMinutes).LocalDateTime
    }
    $ctxPath  = if ($Ctx) { Join-Path $Fix $Ctx } else { $NONE }
    $credPath = if ($CredFixture) { Join-Path $Fix $CredFixture } else { $NONE }
    $a = @('-NoProfile','-File',$Quota,'-Json',
           '-Now', $BASE.ToString('o'),
           '-CredentialsPath', $credPath,
           '-UsageJsonPath', $usagePath,
           '-CtxJsonPath', $ctxPath)
    if (-not $AllowFetch) { $a += '-NoFetch' }
    if ($UrlOverride)     { $a += @('-UsageUrlOverride', $UrlOverride) }
    $raw = (& pwsh @a 2>&1) -join "`n"
    if ($Usage -and (Test-Path -LiteralPath $usagePath)) { Remove-Item -LiteralPath $usagePath -Force -ErrorAction SilentlyContinue }
    $obj = $null
    try { $obj = $raw | ConvertFrom-Json } catch { throw "quota.ps1 -Json did not emit valid JSON:`n$raw" }
    return [pscustomobject]@{ raw = $raw; o = $obj }
}

# Run plan.ps1 -Json with an injected quota snapshot; return the parsed plan object.
$Plan = Join-Path $SkillDir 'plan.ps1'
function Invoke-Plan {
    param([string]$QuotaJson, [string]$Tasks, [string]$NowIso)
    $a = @('-NoProfile','-File',$Plan,'-Json','-QuotaJson',$QuotaJson,'-Tasks',$Tasks)
    if ($NowIso) { $a += @('-Now',$NowIso) }
    $raw = (& pwsh @a 2>&1) -join "`n"
    try { return ($raw | ConvertFrom-Json) } catch { throw "plan.ps1 -Json bad output:`n$raw" }
}

# Run quota.ps1 -Provider <p> -Json against a fixture snapshot dir and Codex dir; return array.
# Network stays off (-NoFetch, bogus creds); the ccstatusline cache is optional.
function Invoke-Prov {
    param([string]$Provider, [string]$Snap, [string]$Usage, [int]$AgeMinutes = 5, [int]$NowShiftMin = 0)
    $usagePath = $NONE
    if ($Usage) {
        $usagePath = Join-Path ([System.IO.Path]::GetTempPath()) ("pq-usage-{0}.json" -f ([guid]::NewGuid().ToString('N')))
        Copy-Item -LiteralPath (Join-Path $Fix $Usage) -Destination $usagePath -Force
        (Get-Item -LiteralPath $usagePath).LastWriteTime = $BASE.AddMinutes($NowShiftMin - $AgeMinutes).LocalDateTime
    }
    $snapDir = if ($Snap) { Join-Path $Fix $Snap } else { $NONE }
    $a = @('-NoProfile','-File',$Quota,'-Json','-NoFetch','-Provider',$Provider,
           '-Now', $BASE.AddMinutes($NowShiftMin).ToString('o'),
           '-CredentialsPath', $NONE, '-UsageJsonPath', $usagePath, '-CtxJsonPath', $NONE,
           '-SnapshotDir', $snapDir, '-CodexDir', (Join-Path $Fix 'codex'))
    $raw = (& pwsh @a 2>&1) -join "`n"
    if ($Usage) { Remove-Item -LiteralPath $usagePath -Force -ErrorAction SilentlyContinue }
    try { $o = @($raw | ConvertFrom-Json) } catch { throw "quota.ps1 -Provider did not emit valid JSON:`n$raw" }
    return [pscustomobject]@{ raw = $raw; o = $o }
}

$tests = @(
    @{
        Name = 'provider_claude_snapshot: fresh mod snapshot -> two claude windows, source=mod-snapshot'
        Run = {
            $r = Invoke-Prov -Provider claude -Snap 'snap-good'
            if ($r.o.Count -ne 2) { throw "expected 2 entries; got $($r.o.Count): $($r.raw)" }
            $five = $r.o | Where-Object { $_.window -eq '5h' }
            if ($five.provider -ne 'claude' -or [int]$five.percentUsed -ne 31) { throw "bad 5h entry: $($r.raw)" }
            if ($five.source -ne 'mod-snapshot') { throw "expected source mod-snapshot; got '$($five.source)'" }
            if ([int]$five.ageSec -ne 120) { throw "expected ageSec 120; got '$($five.ageSec)'" }
            if (-not $five.resetsAt) { throw "resetsAt missing" }
            if ([int]($r.o | Where-Object { $_.window -eq '7d' }).percentUsed -ne 64) { throw "bad 7d entry" }
            if ($r.raw -match '(?i)token') { throw "output has a token field" }
        }
    },
    @{
        Name = 'provider_codex: newest rollout log -> codex 5h=12 7d=3, source=codex-log'
        Run = {
            $r = Invoke-Prov -Provider codex -Snap $null
            if ($r.o.Count -ne 2) { throw "expected 2 codex entries; got $($r.raw)" }
            if ([int]($r.o | Where-Object { $_.window -eq '5h' }).percentUsed -ne 12) { throw "codex 5h should be 12: $($r.raw)" }
            if ([int]($r.o | Where-Object { $_.window -eq '7d' }).percentUsed -ne 3)  { throw "codex 7d should be 3" }
            if (@($r.o | Where-Object { $_.provider -ne 'codex' -or $_.source -ne 'codex-log' }).Count) { throw "bad provider/source: $($r.raw)" }
        }
    },
    @{
        Name = 'provider_all: claude + codex entries in one array'
        Run = {
            $r = Invoke-Prov -Provider all -Snap 'snap-good'
            if ($r.o.Count -ne 4) { throw "expected 4 entries; got $($r.raw)" }
            if (@($r.o | Where-Object provider -eq 'claude').Count -ne 2) { throw "expected 2 claude" }
        }
    },
    @{
        # Review Focus 3: a snapshot read mid-write is torn JSON -> treat as no snapshot.
        Name = 'torn_snapshot_falls_back: truncated JSON -> ccstatusline cache, not mod-snapshot'
        Run = {
            $r = Invoke-Prov -Provider claude -Snap 'snap-torn' -Usage 'good-usage-fresh.json'
            if ($r.o.Count -ne 2) { throw "expected 2 fallback entries; got $($r.raw)" }
            if (@($r.o | Where-Object source -eq 'mod-snapshot').Count) { throw "torn snapshot was used" }
            if ([int]($r.o | Where-Object window -eq '5h').percentUsed -ne 57) { throw "expected cache 57: $($r.raw)" }
        }
    },
    @{
        Name = 'old_snapshot_ignored: snapshot older than 15 min -> not used'
        Run = {
            $r = Invoke-Prov -Provider claude -Snap 'snap-good' -NowShiftMin 30
            if (@($r.o | Where-Object source -eq 'mod-snapshot').Count) { throw "32m-old snapshot was used: $($r.raw)" }
        }
    },
    @{
        Name = 'default_provider_runtime: no -Provider in Codex -> codex entries; CLAUDECODE wins'
        Run = {
            $saved = @{ CLAUDECODE = $env:CLAUDECODE; CODEX_SANDBOX = $env:CODEX_SANDBOX }
            $a = @('-NoProfile','-File',$Quota,'-NoFetch','-Now',$BASE.ToString('o'),'-CredentialsPath',$NONE,
                   '-UsageJsonPath',$NONE,'-CtxJsonPath',$NONE,'-SnapshotDir',$NONE,'-CodexDir',(Join-Path $Fix 'codex'))
            try {
                $env:CLAUDECODE = $null; $env:CODEX_SANDBOX = 'seatbelt'
                $raw = (& pwsh @a 2>&1) -join "`n"
                $o = @($raw | ConvertFrom-Json)
                if (-not $o.Count -or @($o | Where-Object provider -ne 'codex').Count) { throw "Codex runtime did not default to codex:`n$raw" }
                $env:CLAUDECODE = '1'
                $raw = (& pwsh @a 6>&1 2>&1) -join "`n"
                if ($raw -notmatch 'Claude Usage') { throw "Claude runtime did not default to the claude report:`n$raw" }
            } finally { $env:CLAUDECODE = $saved.CLAUDECODE; $env:CODEX_SANDBOX = $saved.CODEX_SANDBOX }
        }
    },
    @{
        Name = 'default_output_unchanged: no -Provider still prints the human report'
        Run = {
            $raw = (& pwsh -NoProfile -File $Quota -NoFetch -Now $BASE.ToString('o') -CredentialsPath $NONE -UsageJsonPath $NONE -CtxJsonPath $NONE 6>&1 2>&1) -join "`n"
            if ($raw -notmatch 'Claude Usage') { throw "default output changed:`n$raw" }
        }
    },
    @{
        Name = 'skill_frontmatter: SKILL.md declares name personal-quota + model + description'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?m)^name:\s*personal-quota\s*$') { throw "frontmatter name not personal-quota" }
            if ($s -notmatch '(?m)^model:\s*\S')                { throw "frontmatter model missing" }
            if ($s -notmatch '(?m)^description:\s*\S')          { throw "frontmatter description missing" }
        }
    },
    @{
        Name = 'referential_integrity: quota.ps1 + plan.ps1 + both ctx-sidecar shims exist on disk'
        Run = {
            foreach ($f in @('quota.ps1','plan.ps1','ctx-sidecar.ps1','ctx-sidecar.sh')) {
                if (-not (Test-Path -LiteralPath (Join-Path $SkillDir $f))) { throw "missing referenced file: $f" }
            }
        }
    },
    @{
        Name = 'fresh_cache_selected: fresh usage.json -> source=cache, not stale, numbers present'
        Run = {
            $r = Invoke-Quota -Usage 'good-usage-fresh.json' -AgeMinutes 5
            if ($r.o.source -notmatch '^cache') { throw "expected source 'cache*'; got '$($r.o.source)'" }
            if ($r.o.stale -ne $false)          { throw "expected stale=false; got '$($r.o.stale)'" }
            if ([int]$r.o.sessionPct -ne 57)    { throw "expected sessionPct 57; got '$($r.o.sessionPct)'" }
            if ([int]$r.o.weeklyPct  -ne 73)    { throw "expected weeklyPct 73; got '$($r.o.weeklyPct)'" }
        }
    },
    @{
        Name = 'stale_by_age: cache older than freshness window -> stale=true, numbers still emitted'
        Run = {
            $r = Invoke-Quota -Usage 'good-usage-fresh.json' -AgeMinutes 60
            if ($r.o.stale -ne $true)        { throw "expected stale=true for 60m-old cache; got '$($r.o.stale)'" }
            if ($r.o.source -notmatch 'STALE') { throw "expected source to say STALE; got '$($r.o.source)'" }
            if ([int]$r.o.sessionPct -ne 57) { throw "stale cache should still emit numbers; got '$($r.o.sessionPct)'" }
        }
    },
    @{
        Name = 'stale_by_reset_past: fresh mtime but session reset in the past -> stale=true'
        Run = {
            $r = Invoke-Quota -Usage 'bad-usage-stale-reset.json' -AgeMinutes 5
            if ($r.o.stale -ne $true) { throw "reset-in-past must be treated as stale; got stale='$($r.o.stale)' source='$($r.o.source)'" }
        }
    },
    @{
        Name = 'missing_cache_unknown: no cache + no fetch -> UNKNOWN (null pcts, null source)'
        Run = {
            $r = Invoke-Quota -Usage $null
            if ($null -ne $r.o.sessionPct) { throw "expected null sessionPct; got '$($r.o.sessionPct)'" }
            if ($null -ne $r.o.source)     { throw "expected null source; got '$($r.o.source)'" }
        }
    },
    @{
        # H2 regression: a valid-JSON but corrupt cache (bad date/pct) must fall back to UNKNOWN,
        # never throw a terminating error and crash the skill (SKILL.md's no-crash promise).
        Name = 'malformed_cache_no_crash: corrupt-but-valid-JSON cache -> UNKNOWN, no crash'
        Run = {
            $r = Invoke-Quota -Usage 'bad-usage-malformed.json' -AgeMinutes 5
            if ($null -ne $r.o.sessionPct) { throw "malformed cache should yield UNKNOWN; got '$($r.o.sessionPct)'" }
        }
    },
    @{
        Name = 'context_present: good ctx sidecar -> contextAvailable=true, contextPct=43'
        Run = {
            $r = Invoke-Quota -Usage 'good-usage-fresh.json' -Ctx 'good-ctx.json'
            if ($r.o.contextAvailable -ne $true) { throw "expected contextAvailable=true; got '$($r.o.contextAvailable)'" }
            if ([int]$r.o.contextPct -ne 43)     { throw "expected contextPct 43; got '$($r.o.contextPct)'" }
        }
    },
    @{
        Name = 'context_absent_and_malformed: no ctx AND ctx-without-pct both -> contextAvailable=false'
        Run = {
            $r1 = Invoke-Quota -Usage 'good-usage-fresh.json' -Ctx $null
            if ($r1.o.contextAvailable -ne $false) { throw "no ctx file should be contextAvailable=false; got '$($r1.o.contextAvailable)'" }
            $r2 = Invoke-Quota -Usage 'good-usage-fresh.json' -Ctx 'bad-ctx.json'
            if ($r2.o.contextAvailable -ne $false) { throw "ctx.json without contextPct should be contextAvailable=false; got '$($r2.o.contextAvailable)'" }
        }
    },
    @{
        Name = 'scoped_rendering: opus/sonnet weekly split surfaces in scoped[]'
        Run = {
            $r = Invoke-Quota -Usage 'good-usage-scoped.json'
            $scoped = @($r.o.scoped)
            $labels = ($scoped | ForEach-Object { $_.label }) -join ','
            if ($labels -notmatch 'Opus')   { throw "expected Opus in scoped; got '$labels'" }
            if ($labels -notmatch 'Sonnet') { throw "expected Sonnet in scoped; got '$labels'" }
        }
    },
    @{
        # SECURITY guardrail as CODE: the -Json output must never carry the token in any form.
        Name = 'token_safety: -Json output contains no token/credential material'
        Run = {
            $r = Invoke-Quota -Usage 'good-usage-fresh.json' -Ctx 'good-ctx.json'
            foreach ($needle in @('accessToken','refreshToken','Bearer','claudeAiOauth')) {
                if ($r.raw -match [regex]::Escape($needle)) { throw "output leaked '$needle'" }
            }
            $names = $r.o.PSObject.Properties.Name -join ','
            if ($names -match '(?i)token') { throw "output object has a token-like field: $names" }
        }
    },
    @{
        # H3 fix: exercise the ACTUAL token-bearing path. -UsageUrlOverride points the fetch at an
        # unreachable local port (connection refused, offline-safe) so Get-LiveUsage reads the sentinel
        # token, builds the Authorization header, and hits its error path. The sentinel must NOT leak.
        Name = 'token_safety_live_path: token never leaks even when the live fetch errors'
        Run = {
            $r = Invoke-Quota -Usage $null -AllowFetch -CredFixture 'creds-sentinel.json' -UrlOverride 'http://127.0.0.1:1/usage'
            if ($r.raw -match 'SENTINEL_TOKEN_DO_NOT_LEAK')   { throw "access token leaked into output:`n$($r.raw)" }
            if ($r.raw -match 'SENTINEL_REFRESH_DO_NOT_LEAK') { throw "refresh token leaked into output:`n$($r.raw)" }
            if ($null -ne $r.o.sessionPct) { throw "refused fetch should yield UNKNOWN; got sessionPct '$($r.o.sessionPct)'" }
        }
    },
    @{
        # M2 fix: a fresh cache must be used BEFORE any fetch. Fetch is ALLOWED but pointed at an
        # unreachable URL; correct ordering never touches the network -> source=cache, not stale.
        # If the ordering were reversed, the bogus fetch would run first and this would not say cache.
        Name = 'fresh_cache_prevents_fetch: fresh cache short-circuits the fetch'
        Run = {
            $r = Invoke-Quota -Usage 'good-usage-fresh.json' -AgeMinutes 5 -AllowFetch -CredFixture 'creds-sentinel.json' -UrlOverride 'http://127.0.0.1:1/usage'
            if ($r.o.source -notmatch '^cache') { throw "fresh cache must win over fetch; got source '$($r.o.source)'" }
            if ($r.o.stale -ne $false)          { throw "expected stale=false; got '$($r.o.stale)'" }
        }
    },
    @{
        # CALIBRATION: the good-* fixtures accept (fresh, not stale) and the bad-* fixtures reject
        # (stale / unavailable). A grader that passes everything measures nothing.
        Name = 'calibration: good-* usable, bad-* rejected'
        Run = {
            $good = Invoke-Quota -Usage 'good-usage-fresh.json' -AgeMinutes 5
            if ($good.o.stale -ne $false) { throw "good-usage-fresh should be fresh; got stale='$($good.o.stale)'" }
            $bad = Invoke-Quota -Usage 'bad-usage-stale-reset.json' -AgeMinutes 5
            if ($bad.o.stale -ne $true)  { throw "bad-usage-stale-reset should be stale" }
            $badctx = Invoke-Quota -Usage 'good-usage-fresh.json' -Ctx 'bad-ctx.json'
            if ($badctx.o.contextAvailable -ne $false) { throw "bad-ctx should be unavailable" }
        }
    },
    @{
        Name = 'plan_bands: bindingPct maps to the right band + per-size task decisions'
        Run = {
            $far = '2026-07-23T05:00:00-04:00'; $now = '2026-07-16T12:00:00-04:00'
            $mk = { param($s,$w) '{{"sessionPct":{0},"weeklyPct":{1},"sessionReset":"{2}","weeklyReset":"{2}"}}' -f $s,$w,$far }
            $proceed = Invoke-Plan -QuotaJson (& $mk 10 10) -Tasks 'a:heavy' -NowIso $now
            if ($proceed.band -ne 'PROCEED') { throw "10% -> PROCEED; got $($proceed.band)" }
            if ($proceed.tasks[0].decision -ne 'FITS_NOW') { throw "heavy should fit at 10%" }
            $conserve = Invoke-Plan -QuotaJson (& $mk 10 70) -Tasks 'h:heavy,m:medium' -NowIso $now
            if ($conserve.band -ne 'CONSERVE') { throw "70% -> CONSERVE; got $($conserve.band)" }
            if (($conserve.tasks | Where-Object { $_.size -eq 'heavy' }).decision -ne 'DEFER') { throw "heavy should DEFER at 70%" }
            if (($conserve.tasks | Where-Object { $_.size -eq 'medium' }).decision -ne 'FITS_NOW') { throw "medium should fit at 70%" }
            $lightonly = Invoke-Plan -QuotaJson (& $mk 10 88) -Tasks 'm:medium,l:light' -NowIso $now
            if ($lightonly.band -ne 'LIGHT_ONLY') { throw "88% -> LIGHT_ONLY; got $($lightonly.band)" }
            if (($lightonly.tasks | Where-Object { $_.size -eq 'medium' }).decision -ne 'DEFER') { throw "medium should DEFER at 88%" }
            if (($lightonly.tasks | Where-Object { $_.size -eq 'light' }).decision -ne 'FITS_NOW') { throw "light should fit at 88%" }
            $stop = Invoke-Plan -QuotaJson (& $mk 10 97) -Tasks 'l:light' -NowIso $now
            if ($stop.band -ne 'STOP') { throw "97% -> STOP; got $($stop.band)" }
            if ($stop.tasks[0].decision -ne 'DEFER') { throw "light should DEFER under STOP" }
            if (-not $stop.handoffRecommended) { throw "STOP must recommend handoff" }
        }
    },
    @{
        Name = 'plan_binding: the more-consumed meter binds; deferUntil is its reset'
        Run = {
            $now = '2026-07-16T12:00:00-04:00'
            $wk = Invoke-Plan -QuotaJson '{"sessionPct":30,"weeklyPct":70,"sessionReset":"2026-07-16T14:00:00-04:00","weeklyReset":"2026-07-23T05:00:00-04:00"}' -Tasks 'h:heavy' -NowIso $now
            if ($wk.binding -ne 'weekly') { throw "weekly 70 > session 30 -> weekly binds; got $($wk.binding)" }
            if (([datetimeoffset]$wk.tasks[0].deferUntil).ToString('yyyy-MM-dd') -ne '2026-07-23') { throw "deferUntil should be weekly reset; got $($wk.tasks[0].deferUntil)" }
            $se = Invoke-Plan -QuotaJson '{"sessionPct":80,"weeklyPct":40,"sessionReset":"2026-07-16T14:00:00-04:00","weeklyReset":"2026-07-23T05:00:00-04:00"}' -Tasks 'h:heavy' -NowIso $now
            if ($se.binding -ne 'session') { throw "session 80 > weekly 40 -> session binds; got $($se.binding)" }
        }
    },
    @{
        Name = 'plan_wake: <=55m to reset -> schedulewakeup; longer -> task-scheduler'
        Run = {
            $now = '2026-07-16T12:00:00-04:00'
            $soon = Invoke-Plan -QuotaJson '{"sessionPct":90,"weeklyPct":10,"sessionReset":"2026-07-16T12:30:00-04:00","weeklyReset":"2026-07-23T05:00:00-04:00"}' -Tasks 'h:heavy' -NowIso $now
            if ($soon.wakeMechanism -ne 'schedulewakeup') { throw "30m out -> schedulewakeup; got $($soon.wakeMechanism)" }
            if ([int]$soon.wakeDelaySeconds -lt 1500 -or [int]$soon.wakeDelaySeconds -gt 2100) { throw "30m -> ~1800s; got $($soon.wakeDelaySeconds)" }
            $farp = Invoke-Plan -QuotaJson '{"sessionPct":10,"weeklyPct":90,"sessionReset":"2026-07-16T12:30:00-04:00","weeklyReset":"2026-07-23T05:00:00-04:00"}' -Tasks 'h:heavy' -NowIso $now
            if ($farp.wakeMechanism -ne 'task-scheduler') { throw "days out -> task-scheduler; got $($farp.wakeMechanism)" }
        }
    },
    @{
        # Integration contract: the orchestration + handoff skills must actually reference the
        # quota sensor/planner. If a wiring is deleted, this guard fails (the quota skill owns the
        # contract, so it verifies its consumers here rather than in 4 separate evals).
        Name = 'integration_wiring: loop/workflow/goal/progress reference quota sensor+planner'
        Run = {
            $skillsDir = Resolve-Path (Join-Path $SkillDir '..')
            $checks = [ordered]@{
                'personal-loop/SKILL.md'     = 'plan\.ps1'
                'personal-workflow/SKILL.md' = 'plan\.ps1'
                'personal-goal/SKILL.md'     = 'personal-quota'
                'personal-handoff/SKILL.md' = 'quota\.ps1'
            }
            foreach ($rel in $checks.Keys) {
                $f = Join-Path $skillsDir $rel
                if (-not (Test-Path -LiteralPath $f)) { throw "missing consumer skill: $rel" }
                if ((Get-Content -LiteralPath $f -Raw) -notmatch $checks[$rel]) {
                    throw "$rel does not reference '$($checks[$rel])' -- quota wiring missing"
                }
            }
        }
    }
)

$pass = 0; $fail = 0
foreach ($t in $tests) {
    try { & $t.Run; $pass++; Write-Host "PASS $($t.Name)" -ForegroundColor Green }
    catch { $fail++; Write-Host "FAIL $($t.Name): $_" -ForegroundColor Red }
}
if ($fail -eq 0) { Write-Host "EVAL PASS personal-quota ($pass)" -ForegroundColor Green; exit 0 }
else { Write-Host "EVAL FAIL personal-quota ($fail of $($pass+$fail))" -ForegroundColor Red; exit 1 }
