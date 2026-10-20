#requires -Version 7
# Eval grader for the grill-me alias. It must forward to personal-grill-me, and that skill must accept the call.
# Deterministic red/green grader. Exit 0 = all checks pass; exit 1 = at least one fails.
$ErrorActionPreference = 'Stop'

$SkillDir = Resolve-Path (Join-Path $PSScriptRoot '..')
$Skill    = Join-Path $SkillDir 'SKILL.md'
$Target   = Join-Path $SkillDir '../personal-grill-me/SKILL.md'

$tests = @(
    @{
        Name = 'alias_frontmatter: name grill-me, a description, and disable-model-invocation: false'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?m)^name:\s*grill-me\s*$') { throw "frontmatter name is not grill-me" }
            if ($s -notmatch '(?m)^description:\s*\S') { throw "frontmatter description missing" }
            if ($s -notmatch '(?m)^disable-model-invocation:\s*false\s*$') { throw "disable-model-invocation must be false" }
        }
    },
    @{
        Name = 'alias_forwards: the alias calls ping-personal:personal-grill-me, which exists and the Skill tool may call'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch [regex]::Escape('Call the Skill tool with `ping-personal:personal-grill-me`')) { throw "alias does not forward to ping-personal:personal-grill-me" }
            if (-not (Test-Path $Target)) { throw "personal-grill-me/SKILL.md missing" }
            $t = Get-Content $Target -Raw
            if ($t -match '(?m)^disable-model-invocation:\s*true\s*$') { throw "personal-grill-me is manual-only, so the Skill tool would refuse the forward" }
        }
    }
)

$pass = 0; $fail = 0
foreach ($t in $tests) {
    try { & $t.Run; $pass++; Write-Host "PASS $($t.Name)" -ForegroundColor Green }
    catch { $fail++; Write-Host "FAIL $($t.Name): $_" -ForegroundColor Red }
}
if ($fail -eq 0) { Write-Host "EVAL PASS grill-me alias ($pass)" -ForegroundColor Green; exit 0 }
else { Write-Host "EVAL FAIL grill-me alias ($fail of $($pass+$fail))" -ForegroundColor Red; exit 1 }
