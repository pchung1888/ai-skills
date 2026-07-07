#requires -Version 7
# Eval grader for personal-cs-escalate-to-dev. See evals/eval-plan.md for the failure-mode map.
# Deterministic red/green grader. Exit 0 = all checks pass; exit 1 = at least one fails.
# ASCII only (no em-dashes/smart-quotes -- Windows PowerShell 5.1 cp1252 pitfall).
$ErrorActionPreference = 'Stop'

$SkillDir   = Resolve-Path (Join-Path $PSScriptRoot '..')
$Skill      = Join-Path $SkillDir 'SKILL.md'
$SchemaPath = Join-Path $SkillDir '..\personal-cs-client-question\cs-metric-schema.json'

$tests = @(
    @{
        Name = 'skill_frontmatter: SKILL.md declares the right name + a description'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?m)^name:\s*personal-cs-escalate-to-dev\s*$') { throw "frontmatter name not personal-cs-escalate-to-dev" }
            if ($s -notmatch '(?m)^description:\s*\S') { throw "frontmatter description missing" }
        }
    },
    @{
        Name = 'db_touch_rule_present: Trigger B DB-touch keywords still enumerated'
        Run = {
            $s = Get-Content $Skill -Raw
            foreach ($kw in @('Connection string', 'Raw SQL', 'Table mutations', 'Credential')) {
                if ($s -notmatch [regex]::Escape($kw)) { throw "Trigger B no longer mentions '$kw'" }
            }
        }
    },
    @{
        Name = 'no_direct_answer_rule: skill still forbids composing a direct answer'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch 'DO NOT\*\* compose a direct answer') { throw "the 'DO NOT compose a direct answer' rule is missing" }
        }
    },
    @{
        Name = 'metric_shape_matches_schema: documented metric-JSON field names all exist in cs-metric-schema.json'
        Run = {
            $s = Get-Content $Skill -Raw
            $blockMatch = [regex]::Match($s, '(?s)Metric JSON shape.*?```json\s*(\{.*?\})\s*```')
            if (-not $blockMatch.Success) { throw "could not locate the Metric JSON shape code block in SKILL.md" }
            $fieldNames = [regex]::Matches($blockMatch.Groups[1].Value, '"(\w+)"\s*:') | ForEach-Object { $_.Groups[1].Value } | Select-Object -Unique
            $schema = Get-Content $SchemaPath -Raw | ConvertFrom-Json
            $knownProps = @($schema.properties.PSObject.Properties.Name)
            foreach ($p in $fieldNames) {
                if ($knownProps -notcontains $p) { throw "documented field '$p' is not in cs-metric-schema.json" }
            }
        }
    }
)

$pass = 0; $fail = 0
foreach ($t in $tests) {
    try { & $t.Run; $pass++; Write-Host "PASS $($t.Name)" -ForegroundColor Green }
    catch { $fail++; Write-Host "FAIL $($t.Name): $_" -ForegroundColor Red }
}
if ($fail -eq 0) { Write-Host "EVAL PASS personal-cs-escalate-to-dev ($pass)" -ForegroundColor Green; exit 0 }
else { Write-Host "EVAL FAIL personal-cs-escalate-to-dev ($fail of $($pass+$fail))" -ForegroundColor Red; exit 1 }
