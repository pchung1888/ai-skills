#requires -Version 7
# Eval grader for personal-lesson-tooling (instruction-only). See evals/eval-plan.md.
# Structural grader: the skill has no scripts, so we verify its documented contract is intact.
$ErrorActionPreference = 'Stop'

$SkillDir = Resolve-Path (Join-Path $PSScriptRoot '..')
$Skill    = Join-Path $SkillDir 'SKILL.md'
$Name     = 'personal-lesson-tooling'

$tests = @(
    @{
        Name = 'skill_frontmatter: SKILL.md declares the right name + a description'
        Run = {
            $s = Get-Content $Skill -Raw
            $namePat = '(?m)^name:\s*' + [regex]::Escape($Name) + '\s*$'
            if ($s -notmatch $namePat) { throw "frontmatter name not $Name" }
            if ($s -notmatch '(?m)^description:\s*\S') { throw "frontmatter description missing" }
        }
    },
    @{
        Name = 'append_target_matches_name: body references ~/.claude/lessons/<name>.md'
        Run = {
            $s = Get-Content $Skill -Raw
            $target = "~/.claude/lessons/$Name.md"
            if ($s -notmatch [regex]::Escape($target)) { throw "append-target path does not reference $target (path drift)" }
        }
    },
    @{
        Name = 'required_sections: Capture flow / Step 2 Append / Browse mode / Seed Lessons'
        Run = {
            $s = Get-Content $Skill -Raw
            foreach ($h in @('## Capture flow','### Step 2 -- Append','## Browse mode','## Seed Lessons')) {
                if ($s -notmatch [regex]::Escape($h)) { throw "missing required section: $h" }
            }
        }
    },
    @{
        Name = 'has_seed_lesson: at least one severity-tagged seed lesson'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?m)^##\s+(NEVER|ALWAYS|CAUTION|WARN|NOTE|INFO)\s+\S') { throw "no severity-tagged seed lesson (NEVER/CAUTION/NOTE/...) found" }
        }
    }
)

$pass = 0; $fail = 0
foreach ($t in $tests) {
    try { & $t.Run; $pass++; Write-Host "PASS $($t.Name)" -ForegroundColor Green }
    catch { $fail++; Write-Host "FAIL $($t.Name): $_" -ForegroundColor Red }
}
if ($fail -eq 0) { Write-Host "EVAL PASS $Name ($pass)" -ForegroundColor Green; exit 0 }
else { Write-Host "EVAL FAIL $Name ($fail of $($pass+$fail))" -ForegroundColor Red; exit 1 }
