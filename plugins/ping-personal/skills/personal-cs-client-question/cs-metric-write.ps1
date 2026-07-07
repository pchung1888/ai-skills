<#
.SYNOPSIS
  Wrapper that writes a personal-cs-* metric row + markdown sidecar atomically.
.PARAMETER SkillName
  One of: personal-cs-client-question, personal-cs-step-by-step, personal-cs-escalate-to-dev.
.PARAMETER MetricJson
  JSON string of the metric row WITHOUT id/ts/host/answer_path/answer_sha256.
  Wrapper stamps those itself.
.PARAMETER AnswerMarkdown
  Markdown body with {{id}} {{ts}} {{host}} {{skill}} {{confidence}} {{escalated}}
  placeholders in the YAML frontmatter (between two --- delimiters).
.NOTES
  Exit 0 = wrote both files. Exit 1 = validation/io failure; nothing left on disk.

  Error exits use [Console]::Error.WriteLine() + exit 1 rather than Write-Error
  so that $LASTEXITCODE is reliably 1 even when called from Pester or other
  contexts where $ErrorActionPreference = Stop would propagate the exception.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidateSet('personal-cs-client-question','personal-cs-step-by-step','personal-cs-escalate-to-dev')]
    [string]$SkillName,
    [Parameter(Mandatory)][string]$MetricJson,
    [Parameter(Mandatory)][string]$AnswerMarkdown
)

# Helper: write msg to PowerShell's error stream (so 2>&1 captures it) then exit 1.
# We set $ErrorActionPreference = 'Continue' locally so Write-Error emits to
# stream 2 without throwing -- this lets exit 1 always execute and lets Pester's
# "2>&1" redirect capture the text in $stderr.
function Fail {
    param([string]$Msg, [string]$CleanupPath = '')
    if ($CleanupPath -and (Test-Path $CleanupPath)) {
        Remove-Item $CleanupPath -Force -ErrorAction SilentlyContinue
    }
    $ErrorActionPreference = 'Continue'
    Write-Error $Msg
    exit 1
}

# ---- 0. Resolve roots (test harness can override via env var) ----
$repoRoot   = Resolve-Path (Join-Path $PSScriptRoot '..\..\..\..\')
$schemaPath = Join-Path $PSScriptRoot 'cs-metric-schema.json'
$rootBase   = if ($env:CS_METRIC_ROOT_OVERRIDE) { $env:CS_METRIC_ROOT_OVERRIDE } else { Join-Path $repoRoot '.claude\score-history' }

# ---- 1. Stamp id, ts, host, today ----
$hostName = $env:COMPUTERNAME.ToLower()
$ts       = Get-Date -Format "yyyy-MM-ddTHH:mm:sszzz"
$today    = Get-Date -Format "yyyy-MM-dd"
$idTime   = Get-Date -Format "yyyy-MM-ddTHH-mm-ss"
$rand     = '{0:x6}' -f (Get-Random -Maximum 0xFFFFFF)
$id       = "$idTime-$rand"

$root      = Join-Path $rootBase "personal-cs-client-question\$hostName"
$dateDir   = Join-Path $root $today
$jsonlPath = Join-Path $root "cs-metrics.jsonl"
$mdPath    = Join-Path $dateDir "$id.md"

New-Item -ItemType Directory -Path $dateDir -Force | Out-Null

# ---- 0bis. Gitignore safety check (only outside test harness) ----
if (-not $env:CS_METRIC_ROOT_OVERRIDE) {
    $gitignorePath = Join-Path $repoRoot '.gitignore'
    if (-not (Test-Path $gitignorePath) -or -not (Select-String -Path $gitignorePath -Pattern 'score-history' -Quiet)) {
        Fail "[CS-METRIC] gitignore safety check failed: '.claude/score-history/' not in .gitignore. Refusing to write audit data."
    }
}

# ---- 2. GC pass: delete orphan .md files in today's date folder ----
# Grace window: a concurrent invocation may have written its .md (step 6) but
# not yet appended its jsonl row (step 9) -- only treat a file as orphaned
# once it's old enough that any in-flight sibling write must have finished.
$gcGraceSeconds = 60
$existingMds = Get-ChildItem -Path $dateDir -Filter '*.md' -ErrorAction SilentlyContinue
if ($existingMds) {
    $todayRows = @()
    if (Test-Path $jsonlPath) {
        $todayRows = Get-Content $jsonlPath -ErrorAction SilentlyContinue | ForEach-Object {
            try { ($_ | ConvertFrom-Json).id } catch { $null }
        } | Where-Object { $_ }
    }
    foreach ($md in $existingMds) {
        $mdId = [System.IO.Path]::GetFileNameWithoutExtension($md.Name)
        $isStale = $md.LastWriteTimeUtc -lt (Get-Date).ToUniversalTime().AddSeconds(-$gcGraceSeconds)
        if ($isStale -and ($todayRows -notcontains $mdId)) {
            Remove-Item $md.FullName -Force
        }
    }
}

# ---- 3. Parse input JSON ----
try {
    $rowObj = $MetricJson | ConvertFrom-Json
} catch {
    Fail "[CS-METRIC] MetricJson parse error: $($_.Exception.Message)"
}

# ---- 4. Substitute frontmatter-only placeholders ----
function Replace-FrontmatterPlaceholders {
    param([string]$Markdown, [hashtable]$Vals)
    $lines = $Markdown -split "`r?`n"
    if ($lines.Count -lt 2 -or $lines[0].Trim() -ne '---') {
        return $null, "[CS-METRIC] markdown must begin with '---' (YAML frontmatter)"
    }
    $endIdx = -1
    for ($i = 1; $i -lt $lines.Count; $i++) {
        if ($lines[$i].Trim() -eq '---') { $endIdx = $i; break }
    }
    if ($endIdx -lt 0) { return $null, "[CS-METRIC] frontmatter missing closing '---'" }
    for ($i = 0; $i -le $endIdx; $i++) {
        foreach ($k in $Vals.Keys) {
            $lines[$i] = $lines[$i] -replace [regex]::Escape("{{$k}}"), [string]$Vals[$k]
        }
    }
    return ($lines -join "`n"), $null
}

$substitutions = @{
    id         = $id
    ts         = $ts
    host       = $hostName
    skill      = $SkillName
    confidence = "$($rowObj.confidence)"
    escalated  = "$($rowObj.escalated)".ToLower()
}

$rendered, $fmErr = Replace-FrontmatterPlaceholders -Markdown $AnswerMarkdown -Vals $substitutions
if ($fmErr) { Fail $fmErr }

# ---- 5. Unresolved-placeholder gate ----
if ($rendered -match '\{\{[^}]+\}\}') {
    Fail "[CS-METRIC] unresolved placeholder(s) survived substitution: $($Matches[0])"
}

# ---- 6. Write sidecar, compute SHA-256 ----
[System.IO.File]::WriteAllText($mdPath, $rendered, [System.Text.Encoding]::UTF8)
$sha = (Get-FileHash -Path $mdPath -Algorithm SHA256).Hash.ToLower()

# ---- 7. Inject id/ts/host/answer_path/answer_sha256 ----
$answerPathRel = "score-history/personal-cs-client-question/$hostName/$today/$id.md"
$rowObj | Add-Member -NotePropertyName id -NotePropertyValue $id -Force
$rowObj | Add-Member -NotePropertyName ts -NotePropertyValue $ts -Force
$rowObj | Add-Member -NotePropertyName host -NotePropertyValue $hostName -Force
$rowObj | Add-Member -NotePropertyName answer_path -NotePropertyValue $answerPathRel -Force
$rowObj | Add-Member -NotePropertyName answer_sha256 -NotePropertyValue $sha -Force

# Drop any caller-supplied keys we don't trust
$rowObj.PSObject.Properties.Remove('host_override')

# ---- 8a. Explicit cross-field pre-validation ----
# Mirror the allOf conditions from the schema with named error messages so tests
# can assert field names in stderr. Test-Json's conditional-allOf errors are
# often generic ("JSON does not match schema") and do not name the field.
$escalatedVal  = $rowObj.escalated
$confidenceVal = "$($rowObj.confidence)"
$suggestionVal = "$($rowObj.suggestion)"
$devConcernVal = "$($rowObj.dev_concern)"

if (-not $escalatedVal -and [string]::IsNullOrWhiteSpace($suggestionVal)) {
    Fail "[CS-METRIC] validation failed: 'suggestion' is required when escalated=false" -CleanupPath $mdPath
}
if ($confidenceVal -eq 'INFERRED' -and [string]::IsNullOrWhiteSpace($devConcernVal)) {
    Fail "[CS-METRIC] validation failed: 'dev_concern' is required when confidence=INFERRED" -CleanupPath $mdPath
}

# ---- 8b. Validate against JSON schema ----
$rowJsonOneLine = $rowObj | ConvertTo-Json -Compress -Depth 10
$schemaText = Get-Content $schemaPath -Raw
try {
    $valid = $rowJsonOneLine | Test-Json -Schema $schemaText -ErrorAction Stop
} catch {
    Fail "[CS-METRIC] schema validation failed: $($_.Exception.Message)" -CleanupPath $mdPath
}
if (-not $valid) {
    Fail "[CS-METRIC] schema validation returned false" -CleanupPath $mdPath
}

# ---- 9. Atomic append ----
try {
    [System.IO.File]::AppendAllText($jsonlPath, $rowJsonOneLine + "`n", [System.Text.Encoding]::UTF8)
} catch {
    Start-Sleep -Milliseconds 100
    try {
        [System.IO.File]::AppendAllText($jsonlPath, $rowJsonOneLine + "`n", [System.Text.Encoding]::UTF8)
    } catch {
        Fail "[CS-METRIC] jsonl append failed: $($_.Exception.Message)" -CleanupPath $mdPath
    }
}

Write-Output "[CS-METRIC] wrote $mdPath"
Write-Output "[CS-METRIC] appended row to $jsonlPath"

# ---- 10. Regenerate cs-metrics-data.js for Chrome file:// auto-load ----
# <script src="./cs-metrics-data.js"> is not subject to Chrome's file:// fetch block,
# so the viewer HTML can load data without a server or folder picker.
# Base64 chars (A-Za-z0-9+/=) contain no quotes or backslashes -- injection is safe.
$dataJsPath = Join-Path $PSScriptRoot 'cs-metrics-data.js'
try {
    $jsonlBytes = [System.IO.File]::ReadAllBytes($jsonlPath)
    $b64 = [Convert]::ToBase64String($jsonlBytes)
    [System.IO.File]::WriteAllText($dataJsPath, "window.__CS_METRICS_B64=`"$b64`";", [System.Text.Encoding]::UTF8)
    Write-Output "[CS-METRIC] refreshed $dataJsPath"
} catch {
    Write-Warning "[CS-METRIC] cs-metrics-data.js refresh failed (non-fatal): $($_.Exception.Message)"
}

exit 0
