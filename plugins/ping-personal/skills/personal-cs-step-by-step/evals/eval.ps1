#requires -Version 7
# Eval grader for personal-cs-step-by-step. See evals/eval-plan.md for the failure-mode map.
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
            if ($s -notmatch '(?m)^name:\s*personal-cs-step-by-step\s*$') { throw "frontmatter name not personal-cs-step-by-step" }
            if ($s -notmatch '(?m)^description:\s*\S') { throw "frontmatter description missing" }
        }
    },
    @{
        Name = 'referential_integrity: delegates to personal-cs-client-question rather than duplicating its logic'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch 'personal-cs-client-question') { throw "SKILL.md does not reference personal-cs-client-question" }
            if ($s -notmatch 'personal-cs-escalate-to-dev') { throw "SKILL.md does not reference personal-cs-escalate-to-dev" }
            if (-not (Test-Path $SchemaPath)) { throw "sibling schema file missing: $SchemaPath" }
        }
    },
    @{
        Name = 'metric_shape_matches_schema: documented metric-JSON field names all exist in cs-metric-schema.json'
        Run = {
            $s = Get-Content $Skill -Raw
            $blockMatch = [regex]::Match($s, '(?s)Metric JSON shape.*?```json\s*(\{.*?\})\s*```')
            if (-not $blockMatch.Success) { throw "could not locate the Metric JSON shape code block in SKILL.md" }
            # The block is illustrative pseudo-JSON (contains "..." and <N> placeholders),
            # not valid JSON -- extract top-level-looking field names by regex instead of parsing.
            $fieldNames = [regex]::Matches($blockMatch.Groups[1].Value, '"(\w+)"\s*:') | ForEach-Object { $_.Groups[1].Value } | Select-Object -Unique
            $schema = Get-Content $SchemaPath -Raw | ConvertFrom-Json
            $knownProps = @($schema.properties.PSObject.Properties.Name)
            foreach ($p in $fieldNames) {
                if ($knownProps -contains $p) { continue }
                throw "documented field '$p' is not in cs-metric-schema.json (the schema is the single source of truth for every skill's allowed fields)"
            }
        }
    }
)

$pass = 0; $fail = 0
foreach ($t in $tests) {
    try { & $t.Run; $pass++; Write-Host "PASS $($t.Name)" -ForegroundColor Green }
    catch { $fail++; Write-Host "FAIL $($t.Name): $_" -ForegroundColor Red }
}
if ($fail -eq 0) { Write-Host "EVAL PASS personal-cs-step-by-step ($pass)" -ForegroundColor Green; exit 0 }
else { Write-Host "EVAL FAIL personal-cs-step-by-step ($fail of $($pass+$fail))" -ForegroundColor Red; exit 1 }
