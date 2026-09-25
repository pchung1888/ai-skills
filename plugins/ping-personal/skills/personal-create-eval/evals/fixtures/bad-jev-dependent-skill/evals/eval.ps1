#requires -Version 7
# Healthy fixture grader: has a real check (a throw), no placeholders, references no missing script.
$ErrorActionPreference = 'Stop'
$SkillDir = Resolve-Path (Join-Path $PSScriptRoot '..')
$Skill    = Join-Path $SkillDir 'SKILL.md'
# The defect under test: this eval needs the optional Jev skill, its key and the network.
$Jev = Join-Path $SkillDir '../personal-jev/jev.ps1'
$pass = 0; $fail = 0
try {
    $s = Get-Content $Skill -Raw
    if ($s -notmatch '(?m)^name:\s*bad-jev-dependent-skill\s*$') { throw 'frontmatter name not bad-jev-dependent-skill' }
    $pass++; Write-Host 'PASS frontmatter'
}
catch { $fail++; Write-Host "FAIL frontmatter: $_" }
if ($fail -eq 0) { Write-Host "EVAL PASS bad-jev-dependent-skill ($pass)"; exit 0 }
else { Write-Host 'EVAL FAIL bad-jev-dependent-skill'; exit 1 }
