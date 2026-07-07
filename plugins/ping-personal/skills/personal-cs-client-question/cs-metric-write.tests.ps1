BeforeAll {
    $script:wrapperPath = Join-Path $PSScriptRoot 'cs-metric-write.ps1'
    $script:schemaPath  = Join-Path $PSScriptRoot 'cs-metric-schema.json'
    $script:testRoot    = Join-Path ([System.IO.Path]::GetTempPath()) "cs-metric-write-tests-$(Get-Random)"
    New-Item -ItemType Directory -Path $script:testRoot -Force | Out-Null

    function New-ValidRowJson {
        param([string]$Question = "test question", [string]$Confidence = "EXTRACTED", [bool]$Escalated = $false, [hashtable]$Override = @{})
        $row = @{
            skill = "personal-cs-client-question"
            question = $Question
            confidence = $Confidence
            escalated = $Escalated
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

    function New-ValidMarkdown {
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

# Trajectory
graph_queries: ["positions browse"]
tool_uses_self_count: 2
'@
    }
}

AfterAll {
    Remove-Item -Path $script:testRoot -Recurse -Force -ErrorAction SilentlyContinue
}

Describe "cs-metric-write.ps1" {

    It "writes both files on a valid row" {
        $rowJson = New-ValidRowJson
        $md = New-ValidMarkdown
        $env:CS_METRIC_ROOT_OVERRIDE = $script:testRoot
        & $script:wrapperPath -SkillName "personal-cs-client-question" -MetricJson $rowJson -AnswerMarkdown $md
        $LASTEXITCODE | Should -Be 0
        $hostName = $env:COMPUTERNAME.ToLower()
        $today = Get-Date -Format "yyyy-MM-dd"
        $jsonl = Join-Path $script:testRoot "personal-cs-client-question/$hostName/cs-metrics.jsonl"
        Test-Path $jsonl | Should -BeTrue
        (Get-Content $jsonl).Count | Should -BeGreaterOrEqual 1
        $sidecars = Get-ChildItem (Join-Path $script:testRoot "personal-cs-client-question/$hostName/$today") -Filter "*.md"
        $sidecars.Count | Should -BeGreaterOrEqual 1
    }

    It "fails when suggestion missing on non-escalated row" {
        $rowJson = New-ValidRowJson -Override @{ suggestion = "" }
        $md = New-ValidMarkdown
        $env:CS_METRIC_ROOT_OVERRIDE = $script:testRoot
        $stderr = & $script:wrapperPath -SkillName "personal-cs-client-question" -MetricJson $rowJson -AnswerMarkdown $md 2>&1
        $LASTEXITCODE | Should -Not -Be 0
        ($stderr -join "`n") | Should -Match "suggestion"
    }

    It "fails when dev_concern missing on INFERRED row" {
        $rowJson = New-ValidRowJson -Confidence "INFERRED"
        $md = New-ValidMarkdown
        $env:CS_METRIC_ROOT_OVERRIDE = $script:testRoot
        $stderr = & $script:wrapperPath -SkillName "personal-cs-client-question" -MetricJson $rowJson -AnswerMarkdown $md 2>&1
        $LASTEXITCODE | Should -Not -Be 0
        ($stderr -join "`n") | Should -Match "dev_concern"
    }

    It "fails when unresolved {{...}} survives substitution" {
        $rowJson = New-ValidRowJson
        $md = (New-ValidMarkdown) + "`n`n# Bonus`n{{unresolved_token}}`n"
        $env:CS_METRIC_ROOT_OVERRIDE = $script:testRoot
        $stderr = & $script:wrapperPath -SkillName "personal-cs-client-question" -MetricJson $rowJson -AnswerMarkdown $md 2>&1
        $LASTEXITCODE | Should -Not -Be 0
        ($stderr -join "`n") | Should -Match "unresolved"
    }

    It "ignores caller-supplied host_override (does not trust caller for host)" {
        $rowJson = New-ValidRowJson -Override @{ host_override = "definitely-not-this-machine" }
        $md = New-ValidMarkdown
        $env:CS_METRIC_ROOT_OVERRIDE = $script:testRoot
        & $script:wrapperPath -SkillName "personal-cs-client-question" -MetricJson $rowJson -AnswerMarkdown $md
        $LASTEXITCODE | Should -Be 0
        $hostName = $env:COMPUTERNAME.ToLower()
        $jsonl = Join-Path $script:testRoot "personal-cs-client-question/$hostName/cs-metrics.jsonl"
        $lastRow = Get-Content $jsonl | Select-Object -Last 1 | ConvertFrom-Json
        $lastRow.host | Should -Be $hostName
        $lastRow.host_override | Should -BeNullOrEmpty
    }

    It "GC pass deletes orphan .md with no matching row" {
        $hostName = $env:COMPUTERNAME.ToLower()
        $today = Get-Date -Format "yyyy-MM-dd"
        $dateDir = Join-Path $script:testRoot "personal-cs-client-question/$hostName/$today"
        New-Item -ItemType Directory -Path $dateDir -Force | Out-Null
        $orphanId = "$today" + "T00-00-00-deadbe"
        $orphanPath = Join-Path $dateDir "$orphanId.md"
        "orphan content" | Set-Content -Path $orphanPath
        # Backdate past the GC grace window (60s) so this orphan reads as stale,
        # not as a concurrent in-flight write that hasn't appended its jsonl row yet.
        (Get-Item $orphanPath).LastWriteTimeUtc = (Get-Date).ToUniversalTime().AddMinutes(-5)
        Test-Path $orphanPath | Should -BeTrue
        $rowJson = New-ValidRowJson
        $md = New-ValidMarkdown
        $env:CS_METRIC_ROOT_OVERRIDE = $script:testRoot
        & $script:wrapperPath -SkillName "personal-cs-client-question" -MetricJson $rowJson -AnswerMarkdown $md | Out-Null
        Test-Path $orphanPath | Should -BeFalse
    }

    It "schema-valid row passes Test-Json with cs-metric-schema.json" {
        $rowJson = New-ValidRowJson
        $env:CS_METRIC_ROOT_OVERRIDE = $script:testRoot
        & $script:wrapperPath -SkillName "personal-cs-client-question" -MetricJson $rowJson -AnswerMarkdown (New-ValidMarkdown) | Out-Null
        $hostName = $env:COMPUTERNAME.ToLower()
        $jsonl = Join-Path $script:testRoot "personal-cs-client-question/$hostName/cs-metrics.jsonl"
        $lastRow = Get-Content $jsonl | Select-Object -Last 1
        $schema = Get-Content $script:schemaPath -Raw
        $lastRow | Test-Json -Schema $schema | Should -BeTrue
    }
}
