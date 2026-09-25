#requires -Version 7
# jev.ps1 -- the "mail clerk" for personal-jev. Sends ONE batch of typed questions to
# TypeSafe Jev (POST /v1/systemone) and renders the answers.
#
# Safety contract (the reason this script exists instead of ad-hoc curl):
#   1. Shape check    -- malformed Noul/Choice/Score or non-ASCII payload is rejected (exit 3).
#   2. Leak tripwire  -- emails, company name, GUIDs, connection strings, SQL, SP names, key-shaped
#                        tokens are refused (exit 4). Prints the category, never the match.
#   3. Preview        -- the exact body is always printed. Without -Send or -Fake, nothing
#                        leaves the machine (exit 0, "preview only").
#   4. Key hygiene    -- TYPESAFE_API_KEY is never printed on any path, nor written to a receipt.
#   5. Approval bind  -- the preview prints a fingerprint of the exact body; -Send refuses unless
#                        -Approve carries that fingerprint, so what is sent is what was approved.
#   6. Receipt        -- every real send writes a local JSON record (full odds, contract, result)
#                        to a folder in the user profile, never inside a repo.
#
# Usage:
#   pwsh jev.ps1 -Payload q.json                        # preview only (default), prints fingerprint
#   pwsh jev.ps1 -Payload q.json -Send -Approve <fp>    # after Ping approves that preview
#   pwsh jev.ps1 -Payload q.json -Fake a.json           # canned answers, no network (evals)
#   options: -Threshold 0.6  -Weights w.json  -Json  -ReceiptDir <dir>  -KeyFile <file>
#
# Exit codes: 0 ok | 1 usage/key error | 2 bad JSON | 3 bad shape | 4 leak refused | 5 HTTP error
#             6 approval fingerprint missing or does not match the payload
# ASCII only (Windows PowerShell cp1252 pitfall).
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Payload,
    [switch]$Send,
    [string]$Approve,
    [string]$Fake,
    [double]$Threshold = 0.6,
    [string]$Weights,
    [switch]$Json,
    # Receipts: written on every -Send; on -Fake only when -ReceiptDir is given (evals).
    [string]$ReceiptDir,
    # Key fallback file (one TYPESAFE_API_KEY= line), checked after the env var and ./.env.local.
    [string]$KeyFile = (Join-Path $HOME '.claude/jev.env'),
    # Eval-only overrides: point at an unreachable/local endpoint, shorten the wait.
    [string]$Endpoint = 'https://api.typesafe.ai/v1/systemone',
    [int]$TimeoutSec = 30
)

$ErrorActionPreference = 'Stop'

function Stop-Jev([int]$Code, [string]$Msg) {
    if ($Json) { [ordered]@{ ok = $false; exit = $Code; error = $Msg } | ConvertTo-Json -Compress | Write-Output }
    else { Write-Host $Msg -ForegroundColor Red }
    exit $Code
}

if ($Send -and $Fake) { Stop-Jev 1 'Use -Send or -Fake, not both.' }
if (-not (Test-Path -LiteralPath $Payload)) { Stop-Jev 1 "Payload not found: $Payload" }

# ---- 1. Parse + shape check -------------------------------------------------------------
$bytes = [System.IO.File]::ReadAllBytes((Resolve-Path -LiteralPath $Payload))
for ($i = 0; $i -lt $bytes.Length; $i++) {
    if ($bytes[$i] -gt 127) { Stop-Jev 3 "SHAPE: non-ASCII byte at offset $i (use plain ASCII punctuation)." }
}
$raw = [System.Text.Encoding]::ASCII.GetString($bytes)
try { $p = $raw | ConvertFrom-Json } catch { Stop-Jev 2 "BAD JSON: $($_.Exception.Message)" }

$problems = [System.Collections.Generic.List[string]]::new()
if ($p.state -isnot [string] -or -not $p.state.Trim()) { $problems.Add('state must be a non-empty string') }
$qs = @()
if ($null -eq $p.questions -or -not $p.questions.PSObject.Properties.Count) { $problems.Add('questions must be a non-empty object') }
else { $qs = @($p.questions.PSObject.Properties) }
foreach ($q in $qs) {
    $id = $q.Name; $v = $q.Value
    if ($v.type -notin 'noul', 'choice', 'score') { $problems.Add("$id : type must be noul, choice or score"); continue }
    if ($null -eq $v.instructions) { $problems.Add("$id : instructions missing") }
    switch ($v.type) {
        'choice' {
            $n = if ($v.criteria) { @($v.criteria.PSObject.Properties).Count } else { 0 }
            if ($n -lt 1 -or $n -gt 255) { $problems.Add("$id : choice needs 1-255 options in criteria (has $n)") }
        }
        'score' {
            $n = if ($v.criteria -is [array]) { $v.criteria.Count } else { 0 }
            if ($n -lt 2 -or $n -gt 10) { $problems.Add("$id : score needs a criteria array of 2-10 levels, low to high (has $n)") }
        }
        'noul' {
            if ($null -ne $v.criteria) {
                $bad = @($v.criteria.PSObject.Properties.Name | Where-Object { $_ -notin 'true', 'false' })
                if ($bad) { $problems.Add("$id : noul criteria keys must be only true/false (found: $($bad -join ', '))") }
            }
        }
    }
}
if ($problems.Count) { Stop-Jev 3 ("SHAPE:`n  - " + ($problems -join "`n  - ")) }

# ---- 2. Leak tripwire -------------------------------------------------------------------
# ponytail: regex tripwire catches obvious identifiers only; a client's situation described in
# plain words passes. The human preview + OK is the real gate; this is the backstop.
$leakRules = [ordered]@{
    'email address'     = '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'
    'company name'      = '(?i)\bacme\b'   # set to your company name
    'GUID'              = '(?i)\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b'
    'connection string' = '(?i)\b(server|data source|initial catalog|user id|password|pwd)\s*='
    'SQL statement'     = '(?i)(\bselect\s+(\*|top\s+\d|distinct\b)|\binsert\s+into\b|\bexec(ute)?\s+[a-z_]\w*\.|\bdbo\.)'
    'stored proc name'  = '\bp(Get|Insert|Update|Delete|Browse|Save|Load)[A-Z]\w*'
    'ASP/VB code'       = '(<%|CreateObject\s*\()'
    'key or token'      = '(?i)(\bsk-[A-Za-z0-9_-]{8,}|\bbearer\s+[A-Za-z0-9._-]{8,}|[A-Za-z0-9+/=_-]{40,})'
}
$hits = @($leakRules.Keys | Where-Object { $raw -match $leakRules[$_] })
if ($hits) { Stop-Jev 4 ("LEAK TRIPWIRE: refused to send. Found: " + ($hits -join ', ') + ". Rewrite generically and retry.") }

# ---- 3. Preview -------------------------------------------------------------------------
$model = if ($p.model) { $p.model } else { 'jev-latest' }
$body = [ordered]@{ state = $p.state; model = $model; questions = $p.questions }
$bodyJson = $body | ConvertTo-Json -Depth 30
$wire = $body | ConvertTo-Json -Depth 30 -Compress
# Fingerprint = first 12 hex of SHA-256 over the exact bytes that would be sent.
$fingerprint = [Convert]::ToHexString([System.Security.Cryptography.SHA256]::HashData([System.Text.Encoding]::UTF8.GetBytes($wire))).Substring(0, 12).ToLower()
if (-not $Json) {
    Write-Host "---- PAYLOAD ($($qs.Count) question(s), model $model) ----"
    Write-Host $bodyJson
    Write-Host "---- END PAYLOAD ----"
}
if (-not $Send -and -not $Fake) {
    if ($Json) { [ordered]@{ ok = $true; sent = $false; previewOnly = $true; fingerprint = $fingerprint; payload = $body } | ConvertTo-Json -Depth 30 | Write-Output }
    else { Write-Host "Preview only -- nothing sent. After approval re-run with: -Send -Approve $fingerprint" -ForegroundColor Yellow }
    exit 0
}
if ($Send -and $Approve -ne $fingerprint) {
    Stop-Jev 6 "APPROVAL: -Send needs -Approve <fingerprint of the approved preview>. The given value does not match this payload (it changed, or no preview was approved). Preview again and get a fresh OK."
}

# ---- 4. Send (or fake) ------------------------------------------------------------------
function Read-KeyLine([string]$Path) {
    if (-not $Path -or -not (Test-Path -LiteralPath $Path)) { return $null }
    $line = Get-Content -LiteralPath $Path | Where-Object { $_ -match '^\s*TYPESAFE_API_KEY\s*=' } | Select-Object -First 1
    if ($line) { ($line -replace '^\s*TYPESAFE_API_KEY\s*=\s*', '').Trim().Trim('"', "'") }
}
if ($Fake) {
    if (-not (Test-Path -LiteralPath $Fake)) { Stop-Jev 1 "Fake answers not found: $Fake" }
    $resp = Get-Content -LiteralPath $Fake -Raw | ConvertFrom-Json
}
else {
    # Fixed locations only -- never search parent folders (could pick up another repo's key).
    $key = $env:TYPESAFE_API_KEY
    if (-not $key) { $key = Read-KeyLine '.env.local' }
    if (-not $key) { $key = Read-KeyLine $KeyFile }
    if (-not $key) { Stop-Jev 1 "No TYPESAFE_API_KEY: set the env var, or put TYPESAFE_API_KEY=... in $KeyFile (or .env.local in the current folder)." }
    try {
        $resp = Invoke-RestMethod -Method Post -Uri $Endpoint -ContentType 'application/json' `
            -Headers @{ Authorization = "Bearer $key" } -Body $wire -TimeoutSec $TimeoutSec
    }
    catch {
        $code = $_.Exception.Response.StatusCode.value__
        $msg = ("$($_.ErrorDetails.Message) $($_.Exception.Message)").Trim()
        Stop-Jev 5 ("HTTP ERROR {0}: {1}" -f ($code ?? 'no-response'), $msg.Replace($key, '<redacted>'))
    }
}

# ---- 5. Render --------------------------------------------------------------------------
$results = [System.Collections.Generic.List[object]]::new()
foreach ($q in $qs) {
    $id = $q.Name; $spec = $q.Value; $a = $resp.answers.$id
    if ($null -eq $a) { $results.Add([ordered]@{ id = $id; type = $spec.type; missing = $true; yourCall = $true }); continue }
    $r = [ordered]@{ id = $id; type = $spec.type }
    switch ($spec.type) {
        'choice' {
            $r.value = $a.choice
            $r.probability = [math]::Round([double]$a.probabilities.($a.choice), 2)
            $r.confidence = [math]::Round([double]$a.confidence, 2)
            $r.normalized = $null
            $r.yourCall = $r.confidence -lt $Threshold
        }
        'score' {
            # Top level from the response legend when present, else criteria count - 1 (0-based levels).
            $top = if ($a.legend) { ($a.legend.PSObject.Properties.Name | ForEach-Object { [double]$_ } | Measure-Object -Maximum).Maximum } else { $spec.criteria.Count - 1 }
            $r.value = [math]::Round([double]$a.score, 2)
            $r.normalized = [math]::Round([double]$a.score / $top, 2)
            $r.confidence = [math]::Round([double]$a.confidence, 2)
            $r.yourCall = $r.confidence -lt $Threshold
        }
        'noul' {
            $n = [double]$a.noul
            $r.value = [math]::Round($n, 2)
            $r.normalized = $r.value
            $r.band = if ($n -ge $Threshold) { 'yes' } elseif ($n -le (1 - $Threshold)) { 'no' } else { 'unsure' }
            $r.yourCall = $r.band -eq 'unsure'
        }
    }
    $results.Add($r)
}

# Composite: weights {question_id: weight}. Ids shaped "<option>__<dimension>" get one composite
# per option; other ids share the group "all". Levels must be ordered worst -> best.
# Each composite also reports how many weighted scores it actually used and the least-sure one:
# a missing weighted answer makes the composite null (incomplete), and any unsure input marks the
# whole composite YOUR CALL -- a flat number must not hide that Jev was guessing.
$composites = [ordered]@{}
$compositeDetail = [ordered]@{}
$w = $null
if ($Weights) {
    $w = Get-Content -LiteralPath $Weights -Raw | ConvertFrom-Json
    $byId = @{}; foreach ($r in $results) { $byId[$r.id] = $r }
    $groups = @{}
    foreach ($id in @($w.PSObject.Properties.Name)) {
        $g = if ($id -match '^(.+?)__') { $Matches[1] } else { 'all' }
        if (-not $groups[$g]) { $groups[$g] = @{ sum = 0.0; wsum = 0.0; used = 0; of = 0; minConf = $null; missing = @(); unsure = $false } }
        $grp = $groups[$g]
        $r = $byId[$id]
        if ($r -and -not $r.missing -and $null -eq $r.normalized) { continue }   # choice: not on a scale, not weightable
        $grp.of++
        if ($null -eq $r -or $r.missing) { $grp.missing += $id; continue }
        $grp.sum += [double]$w.$id * $r.normalized
        $grp.wsum += [double]$w.$id
        $grp.used++
        $c = if ($r.type -eq 'noul') { [math]::Abs($r.value - 0.5) * 2 } else { $r.confidence }
        if ($null -eq $grp.minConf -or $c -lt $grp.minConf) { $grp.minConf = [math]::Round($c, 2) }
        if ($r.yourCall) { $grp.unsure = $true }
    }
    foreach ($g in ($groups.Keys | Sort-Object)) {
        $grp = $groups[$g]
        if ($grp.of -eq 0) { continue }
        $val = if ($grp.missing.Count -or $grp.wsum -le 0) { $null } else { [math]::Round($grp.sum / $grp.wsum, 2) }
        $composites[$g] = $val
        $compositeDetail[$g] = [ordered]@{ value = $val; used = $grp.used; of = $grp.of; leastSure = $grp.minConf
            missing = $grp.missing; yourCall = ($grp.unsure -or $grp.missing.Count -gt 0) }
    }
}

$yourCall = @($results | Where-Object { $_.yourCall } | ForEach-Object { $_.id })

# ---- 6. Receipt -------------------------------------------------------------------------
# Written only here: after the shape check, tripwire and approval all passed and an answer came
# back. Holds the full answer (all odds) for later calibration; never the key or headers.
$receiptPath = $null
if ($Send -or ($Fake -and $ReceiptDir)) {
    $dir = if ($ReceiptDir) { $ReceiptDir } else { Join-Path $HOME '.claude/jev-receipts' }
    $null = New-Item -ItemType Directory -Force -Path $dir
    $stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
    $receiptPath = Join-Path $dir "$stamp-$fingerprint.json"
    [ordered]@{
        receiptSchema = 1; id = "$stamp-$fingerprint"; fingerprint = $fingerprint; sentAtUtc = $stamp
        sent = [bool]$Send; contract = $p.contract; modelRequested = $model; modelAnswered = $resp.model
        threshold = $Threshold; weights = $w; state = $p.state; questions = $p.questions
        answers = $resp.answers; results = $results; composites = $compositeDetail; yourCall = $yourCall
        decision = $null   # filled in later with Ping's actual call, for agreement tracking
    } | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $receiptPath
}

if ($Json) {
    [ordered]@{ ok = $true; sent = [bool]$Send; fake = [bool]$Fake; model = $resp.model; threshold = $Threshold
        fingerprint = $fingerprint; results = $results; composites = $composites; compositeDetail = $compositeDetail
        yourCall = $yourCall; receipt = $receiptPath } | ConvertTo-Json -Depth 10 | Write-Output
    exit 0
}
Write-Host "---- JEV ANSWERS ($($resp.model)) ----"
foreach ($r in $results) {
    $flag = if ($r.yourCall) { '  <- YOUR CALL' } else { '' }
    $line = switch ($r.type) {
        'choice' { "{0} [choice]: {1} (p {2}, confidence {3})" -f $r.id, $r.value, $r.probability, $r.confidence }
        'score' { "{0} [score]: {1} -> {2} of 1 (confidence {3})" -f $r.id, $r.value, $r.normalized, $r.confidence }
        'noul' { "{0} [noul]: {1} ({2})" -f $r.id, $r.value, $r.band }
    }
    if ($r.missing) { $line = "{0}: no answer returned" -f $r.id }
    Write-Host ($line + $flag)
}
foreach ($g in $compositeDetail.Keys) {
    $d = $compositeDetail[$g]
    $v = if ($null -eq $d.value) { 'incomplete (missing ' + ($d.missing -join ', ') + ')' } else { $d.value }
    $flag = if ($d.yourCall) { '  <- YOUR CALL' } else { '' }
    Write-Host ("composite {0}: {1} ({2} of {3} scores, least sure {4}){5}" -f $g, $v, $d.used, $d.of, $d.leastSure, $flag)
}
if ($receiptPath) { Write-Host "receipt: $receiptPath" }
if ($yourCall) { Write-Host ("YOUR CALL: Jev is split on " + ($yourCall -join ', ') + " -- weigh the tradeoff yourself.") -ForegroundColor Yellow }
