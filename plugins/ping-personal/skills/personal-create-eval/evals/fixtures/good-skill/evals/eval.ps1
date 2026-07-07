#requires -Version 7
# Healthy fixture grader: has a real check (a throw), no placeholders, references no missing script.
$ErrorActionPreference = 'Stop'
$SkillDir = Resolve-Path (Join-Path $PSScriptRoot '..')
$Skill    = Join-Path $SkillDir 'SKILL.md'
$pass = 0; $fail = 0
try {
    $s = Get-Content $Skill -Raw
    if ($s -notmatch '(?m)^name:\s*good-skill\s*$') { throw 'frontmatter name not good-skill' }
    $pass++; Write-Host 'PASS frontmatter'
}
catch { $fail++; Write-Host "FAIL frontmatter: $_" }
if ($fail -eq 0) { Write-Host "EVAL PASS good-skill ($pass)"; exit 0 }
else { Write-Host 'EVAL FAIL good-skill'; exit 1 }
