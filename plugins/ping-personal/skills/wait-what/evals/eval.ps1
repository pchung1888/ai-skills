#requires -Version 7
# Eval grader for the wait-what alias. It must forward to personal-wait-what, and that skill must accept the call.
# Deterministic red/green grader. Exit 0 = all checks pass; exit 1 = at least one fails.
$ErrorActionPreference = 'Stop'

$SkillDir = Resolve-Path (Join-Path $PSScriptRoot '..')
$Skill    = Join-Path $SkillDir 'SKILL.md'
$Target   = Join-Path $SkillDir '../personal-wait-what/SKILL.md'

$tests = @(
    @{
        Name = 'alias_frontmatter: name wait-what, a description, and disable-model-invocation: true'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?m)^name:\s*wait-what\s*$') { throw "frontmatter name is not wait-what" }
            if ($s -notmatch '(?m)^description:\s*\S') { throw "frontmatter description missing" }
            if ($s -notmatch '(?m)^disable-model-invocation:\s*true\s*$') { throw "disable-model-invocation must be true" }
        }
    },
    @{
        Name = 'alias_forwards: the alias calls ping-personal:personal-wait-what, which exists and the Skill tool may call'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch [regex]::Escape('Call the Skill tool with `ping-personal:personal-wait-what`')) { throw "alias does not forward to ping-personal:personal-wait-what" }
            if (-not (Test-Path $Target)) { throw "personal-wait-what/SKILL.md missing" }
            $t = Get-Content $Target -Raw
            if ($t -match '(?m)^disable-model-invocation:\s*true\s*$') { throw "personal-wait-what is manual-only, so the Skill tool would refuse the forward" }
        }
    }
)

$pass = 0; $fail = 0
foreach ($t in $tests) {
    try { & $t.Run; $pass++; Write-Host "PASS $($t.Name)" -ForegroundColor Green }
    catch { $fail++; Write-Host "FAIL $($t.Name): $_" -ForegroundColor Red }
}
if ($fail -eq 0) { Write-Host "EVAL PASS wait-what alias ($pass)" -ForegroundColor Green; exit 0 }
else { Write-Host "EVAL FAIL wait-what alias ($fail of $($pass+$fail))" -ForegroundColor Red; exit 1 }
