#requires -Version 7
# Eval grader for personal-cs-client-question. See evals/eval-plan.md for the failure-mode map.
# Deterministic red/green grader. Exit 0 = all checks pass; exit 1 = at least one fails.
# ASCII only (no em-dashes/smart-quotes -- Windows PowerShell 5.1 cp1252 pitfall).
$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'

$SkillDir   = Resolve-Path (Join-Path $PSScriptRoot '..')
$Skill      = Join-Path $SkillDir 'SKILL.md'
$Wrapper    = Join-Path $SkillDir 'cs-metric-write.ps1'
$SchemaPath = Join-Path $SkillDir 'cs-metric-schema.json'
$RefDoc     = Join-Path $SkillDir 'references\ticket-system-search.md'

function New-Row {
    param([hashtable]$Override = @{})
    $row = @{
        skill = "personal-cs-client-question"
        question = "test question"
        confidence = "EXTRACTED"
        escalated = $false
        cited = $true
        sources_read = @("app/PositionsBrowse.ext:262")
        suggestion = "Main Menu -> Browse -> Positions"
        graph_hit = $true
        graph_queries = @("positions browse")
        tool_uses_self_count = 2
        notes = ""
    }
    foreach ($k in $Override.Keys) { $row[$k] = $Override[$k] }
    return ($row | ConvertTo-Json -Compress)
}

function New-Markdown {
    return @'
---
id: {{id}}
ts: {{ts}}
host: {{host}}
skill: {{skill}}
confidence: {{confidence}}
escalated: {{escalated}}
---

# Question
test question

# Answer (rendered to support engineer)
1. Main Menu -> Browse -> Positions.

SOURCE: app/PositionsBrowse.ext:262

# Suggestion
Main Menu -> Browse -> Positions

# Dev concern
_(none -- straight extraction)_
'@
}

$tests = @(
    @{
        Name = 'skill_frontmatter: SKILL.md declares the right name + a description'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?m)^name:\s*personal-cs-client-question\s*$') { throw "frontmatter name not personal-cs-client-question" }
            if ($s -notmatch '(?m)^description:\s*\S') { throw "frontmatter description missing" }
        }
    },
    @{
        Name = 'referential_integrity: SKILL.md-referenced files exist on disk'
        Run = {
            foreach ($p in @($Wrapper, $SchemaPath, $RefDoc)) {
                if (-not (Test-Path $p)) { throw "referenced file missing: $p" }
            }
        }
    },
    @{
        Name = 'schema_enum_matches_skills: schema skill enum lists exactly the 3 shipped cs-* skills'
        Run = {
            $schema = Get-Content $SchemaPath -Raw | ConvertFrom-Json
            $enum = $schema.properties.skill.enum
            $expected = @('personal-cs-client-question','personal-cs-step-by-step','personal-cs-escalate-to-dev')
            $diff = Compare-Object $enum $expected
            if ($diff) { throw "schema enum drifted from expected skill list: $($enum -join ', ')" }
        }
    },
    @{
        Name = 'step_by_step_extension_fields_valid: a row shaped exactly like personal-cs-step-by-step SKILL.md documents it validates'
        Run = {
            $testRoot = Join-Path ([System.IO.Path]::GetTempPath()) "cs-eval-$(Get-Random)"
            New-Item -ItemType Directory -Path $testRoot -Force | Out-Null
            try {
                $env:CS_METRIC_ROOT_OVERRIDE = $testRoot
                $row = New-Row -Override @{
                    skill = "personal-cs-step-by-step"
                    cs_client_question_confidence = "EXTRACTED"
                    located_file = "app/PositionsBrowse.ext:262"
                    branching_workflow = $false
                    watch_out_for_added = $false
                    steps_emitted = 3
                }
                & $Wrapper -SkillName "personal-cs-step-by-step" -MetricJson $row -AnswerMarkdown (New-Markdown) | Out-Null
                if ($LASTEXITCODE -ne 0) { throw "wrapper rejected a row shaped exactly like SKILL.md's documented example (exit $LASTEXITCODE) -- schema and docs have drifted again" }
            } finally {
                Remove-Item Env:\CS_METRIC_ROOT_OVERRIDE -ErrorAction SilentlyContinue
                Remove-Item $testRoot -Recurse -Force -ErrorAction SilentlyContinue
            }
        }
    },
    @{
        Name = 'escalate_trigger_fields_valid: a row shaped exactly like personal-cs-escalate-to-dev SKILL.md documents it validates'
        Run = {
            $testRoot = Join-Path ([System.IO.Path]::GetTempPath()) "cs-eval-$(Get-Random)"
            New-Item -ItemType Directory -Path $testRoot -Force | Out-Null
            try {
                $env:CS_METRIC_ROOT_OVERRIDE = $testRoot
                $row = New-Row -Override @{
                    skill = "personal-cs-escalate-to-dev"
                    confidence = "N/A"
                    escalated = $true
                    cited = $false
                    sources_read = @()
                    dev_concern = "raw SQL request, per DB-escalation rule"
                    trigger = "db_touch"
                    upstream_skill = $null
                    upstream_confidence = $null
                    msg_path = 'C:\Users\example\AppData\Local\Temp\escalate-to-dev-latest.md'
                }
                & $Wrapper -SkillName "personal-cs-escalate-to-dev" -MetricJson $row -AnswerMarkdown (New-Markdown) | Out-Null
                if ($LASTEXITCODE -ne 0) { throw "wrapper rejected a row shaped exactly like SKILL.md's documented example (exit $LASTEXITCODE) -- schema and docs have drifted again" }
            } finally {
                Remove-Item Env:\CS_METRIC_ROOT_OVERRIDE -ErrorAction SilentlyContinue
                Remove-Item $testRoot -Recurse -Force -ErrorAction SilentlyContinue
            }
        }
    },
    @{
        Name = 'gc_grace_window: a fresh (non-stale) orphan .md file survives the GC pass'
        Run = {
            $testRoot = Join-Path ([System.IO.Path]::GetTempPath()) "cs-eval-$(Get-Random)"
            New-Item -ItemType Directory -Path $testRoot -Force | Out-Null
            try {
                $env:CS_METRIC_ROOT_OVERRIDE = $testRoot
                $hostName = $env:COMPUTERNAME.ToLower()
                $today = Get-Date -Format "yyyy-MM-dd"
                $dateDir = Join-Path $testRoot "personal-cs-client-question\$hostName\$today"
                New-Item -ItemType Directory -Path $dateDir -Force | Out-Null
                $freshOrphan = Join-Path $dateDir "$today`T00-00-00-cafe01.md"
                "written moments ago, jsonl append still in flight" | Set-Content -Path $freshOrphan
                & $Wrapper -SkillName "personal-cs-client-question" -MetricJson (New-Row) -AnswerMarkdown (New-Markdown) | Out-Null
                if (-not (Test-Path $freshOrphan)) { throw "GC pass deleted a fresh (< grace window) orphan -- a concurrent in-flight write would lose its sidecar" }
            } finally {
                Remove-Item Env:\CS_METRIC_ROOT_OVERRIDE -ErrorAction SilentlyContinue
                Remove-Item $testRoot -Recurse -Force -ErrorAction SilentlyContinue
            }
        }
    },
    @{
        Name = 'schema_valid_row: wrapper writes a row that validates against cs-metric-schema.json'
        Run = {
            $testRoot = Join-Path ([System.IO.Path]::GetTempPath()) "cs-eval-$(Get-Random)"
            New-Item -ItemType Directory -Path $testRoot -Force | Out-Null
            try {
                $env:CS_METRIC_ROOT_OVERRIDE = $testRoot
                & $Wrapper -SkillName "personal-cs-client-question" -MetricJson (New-Row) -AnswerMarkdown (New-Markdown) | Out-Null
                if ($LASTEXITCODE -ne 0) { throw "wrapper exited $LASTEXITCODE on a valid row" }
                $hostName = $env:COMPUTERNAME.ToLower()
                $jsonl = Join-Path $testRoot "personal-cs-client-question\$hostName\cs-metrics.jsonl"
                if (-not (Test-Path $jsonl)) { throw "jsonl not written at $jsonl" }
                $lastRow = Get-Content $jsonl | Select-Object -Last 1
                $schemaText = Get-Content $SchemaPath -Raw
                if (-not ($lastRow | Test-Json -Schema $schemaText)) { throw "written row failed schema validation" }
            } finally {
                Remove-Item Env:\CS_METRIC_ROOT_OVERRIDE -ErrorAction SilentlyContinue
                Remove-Item $testRoot -Recurse -Force -ErrorAction SilentlyContinue
            }
        }
    },
    @{
        Name = 'reject_missing_suggestion: non-escalated row with empty suggestion fails loud'
        Run = {
            $testRoot = Join-Path ([System.IO.Path]::GetTempPath()) "cs-eval-$(Get-Random)"
            New-Item -ItemType Directory -Path $testRoot -Force | Out-Null
            try {
                $env:CS_METRIC_ROOT_OVERRIDE = $testRoot
                $stderr = & $Wrapper -SkillName "personal-cs-client-question" -MetricJson (New-Row -Override @{ suggestion = "" }) -AnswerMarkdown (New-Markdown) 2>&1
                if ($LASTEXITCODE -eq 0) { throw "wrapper accepted a non-escalated row with no suggestion" }
                if (($stderr -join "`n") -notmatch 'suggestion') { throw "error text did not name 'suggestion'" }
            } finally {
                Remove-Item Env:\CS_METRIC_ROOT_OVERRIDE -ErrorAction SilentlyContinue
                Remove-Item $testRoot -Recurse -Force -ErrorAction SilentlyContinue
            }
        }
    },
    @{
        Name = 'reject_missing_dev_concern: INFERRED row with empty dev_concern fails loud'
        Run = {
            $testRoot = Join-Path ([System.IO.Path]::GetTempPath()) "cs-eval-$(Get-Random)"
            New-Item -ItemType Directory -Path $testRoot -Force | Out-Null
            try {
                $env:CS_METRIC_ROOT_OVERRIDE = $testRoot
                $stderr = & $Wrapper -SkillName "personal-cs-client-question" -MetricJson (New-Row -Override @{ confidence = "INFERRED" }) -AnswerMarkdown (New-Markdown) 2>&1
                if ($LASTEXITCODE -eq 0) { throw "wrapper accepted an INFERRED row with no dev_concern" }
                if (($stderr -join "`n") -notmatch 'dev_concern') { throw "error text did not name 'dev_concern'" }
            } finally {
                Remove-Item Env:\CS_METRIC_ROOT_OVERRIDE -ErrorAction SilentlyContinue
                Remove-Item $testRoot -Recurse -Force -ErrorAction SilentlyContinue
            }
        }
    },
    @{
        Name = 'reject_unresolved_placeholder: a stray {{token}} in the markdown fails loud'
        Run = {
            $testRoot = Join-Path ([System.IO.Path]::GetTempPath()) "cs-eval-$(Get-Random)"
            New-Item -ItemType Directory -Path $testRoot -Force | Out-Null
            try {
                $env:CS_METRIC_ROOT_OVERRIDE = $testRoot
                $md = (New-Markdown) + "`n`n{{unresolved_token}}`n"
                $stderr = & $Wrapper -SkillName "personal-cs-client-question" -MetricJson (New-Row) -AnswerMarkdown $md 2>&1
                if ($LASTEXITCODE -eq 0) { throw "wrapper accepted markdown with an unresolved placeholder" }
                if (($stderr -join "`n") -notmatch 'unresolved') { throw "error text did not name 'unresolved'" }
            } finally {
                Remove-Item Env:\CS_METRIC_ROOT_OVERRIDE -ErrorAction SilentlyContinue
                Remove-Item $testRoot -Recurse -Force -ErrorAction SilentlyContinue
            }
        }
    }
)

$pass = 0; $fail = 0
foreach ($t in $tests) {
    try { & $t.Run; $pass++; Write-Host "PASS $($t.Name)" -ForegroundColor Green }
    catch { $fail++; Write-Host "FAIL $($t.Name): $_" -ForegroundColor Red }
}
if ($fail -eq 0) { Write-Host "EVAL PASS personal-cs-client-question ($pass)" -ForegroundColor Green; exit 0 }
else { Write-Host "EVAL FAIL personal-cs-client-question ($fail of $($pass+$fail))" -ForegroundColor Red; exit 1 }
