#requires -Version 7
# Eval grader for personal-unslop. See evals/eval-plan.md for the failure-mode map.
# Deterministic red/green grader. Exit 0 = all checks pass; exit 1 = at least one fails.
# ASCII only (no em-dashes/smart-quotes -- Windows PowerShell 5.1 cp1252 pitfall).
$ErrorActionPreference = 'Stop'

$SkillDir = Resolve-Path (Join-Path $PSScriptRoot '..')
$Skill    = Join-Path $SkillDir 'SKILL.md'

$tests = @(
    @{
        Name = 'skill_frontmatter: name, description and model-invocable flag are present'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?m)^name:\s*personal-unslop\s*$') { throw "frontmatter name not personal-unslop" }
            if ($s -notmatch '(?m)^description:\s*\S') { throw "frontmatter description missing" }
            if ($s -notmatch '(?m)^disable-model-invocation:\s*false\s*$') { throw "disable-model-invocation: false missing (the model must be able to invoke this skill)" }
        }
    },
    @{
        Name = 'ascii_only: SKILL.md has no byte above 127'
        Run = {
            $bytes = [System.IO.File]::ReadAllBytes($Skill)
            $bad = @($bytes | Where-Object { $_ -gt 127 }).Count
            if ($bad -gt 0) { throw "$bad non-ASCII bytes in SKILL.md" }
        }
    },
    @{
        Name = 'rule13_allows_spaced_hyphen: rule 13 bans em/en dashes but allows " - " and " -- "'
        Run = {
            $s = Get-Content $Skill -Raw
            $m = [regex]::Match($s, '(?m)^13\. .*$')
            if (-not $m.Success) { throw "rule 13 not found" }
            $r = $m.Value
            if ($r -notmatch 'em dash' -or $r -notmatch 'en dash') { throw "rule 13 no longer names em and en dashes" }
            if ($r -notmatch '" - "' -or $r -notmatch '" -- "') { throw "rule 13 does not allow the spaced ASCII hyphen dash" }
            if ($r -match 'no hyphen-as-dash') { throw "rule 13 has the upstream ban on hyphen-as-dash again" }
        }
    },
    @{
        Name = 'rule_ids_stable: rules 3,5,7-20,22-33 present; retired ids 1,2,4,6,21 absent'
        Run = {
            $s = Get-Content $Skill -Raw
            $ids = [regex]::Matches($s, '(?m)^(\d+)\. \*\*') | ForEach-Object { [int]$_.Groups[1].Value }
            $expected = @(3, 5) + (7..20) + (22..33)
            $diff = Compare-Object $ids $expected
            if ($diff) { throw "rule ids drifted: found $($ids -join ',')" }
        }
    }
)

$pass = 0; $fail = 0
foreach ($t in $tests) {
    try { & $t.Run; $pass++; Write-Host "PASS $($t.Name)" -ForegroundColor Green }
    catch { $fail++; Write-Host "FAIL $($t.Name): $_" -ForegroundColor Red }
}
if ($fail -eq 0) { Write-Host "EVAL PASS personal-unslop ($pass)" -ForegroundColor Green; exit 0 }
else { Write-Host "EVAL FAIL personal-unslop ($fail of $($pass+$fail))" -ForegroundColor Red; exit 1 }
