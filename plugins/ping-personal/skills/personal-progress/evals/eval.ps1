#requires -Version 7
# Eval grader for personal-progress (instruction-only). See evals/eval-plan.md.
# Structural grader: the capture steps, output path, progress-vs-handoff contract, and
# the templates scaffold must all be intact.
$ErrorActionPreference = 'Stop'

$SkillDir = Resolve-Path (Join-Path $PSScriptRoot '..')          # personal-progress/
$Skill    = Join-Path $SkillDir 'SKILL.md'

$tests = @(
    @{
        Name = 'skill_frontmatter: SKILL.md declares name=personal-progress + a description'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?m)^name:\s*personal-progress\s*$') { throw "frontmatter name not personal-progress" }
            if ($s -notmatch '(?m)^description:\s*\S') { throw "frontmatter description missing" }
        }
    },
    @{
        Name = 'output_path_documented: body references docs/progress/'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch [regex]::Escape('docs/progress/')) { throw "output path docs/progress/ not documented" }
        }
    },
    @{
        Name = 'progress_vs_handoff_documented: both artifacts + the WHAT-happened/WHAT-next split'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?i)progress') { throw "'progress' not documented" }
            if ($s -notmatch '(?i)handoff')  { throw "'handoff' not documented" }
            if ($s -notmatch '(?i)Progress\s*=\s*WHAT' -and $s -notmatch '(?i)Handoff\s*=\s*WHAT') {
                throw "the progress-vs-handoff (WHAT happened vs WHAT next) distinction is missing"
            }
        }
    },
    @{
        Name = 'required_sections: Step 0 / Step 2 Write Progress / Step 2.5 Sibling Handoff / Safety Rules'
        Run = {
            $s = Get-Content $Skill -Raw
            foreach ($h in @('## Step 0','## Step 2: Write the Progress File','## Step 2.5: Sibling Handoff File','## Safety Rules')) {
                if ($s -notmatch [regex]::Escape($h)) { throw "missing required section: $h" }
            }
        }
    },
    @{
        Name = 'templates_present: the templates/ directory exists'
        Run = {
            if (-not (Test-Path (Join-Path $SkillDir 'templates'))) { throw "templates/ directory missing" }
        }
    },
    @{
        Name = 'provenance_footer: progress-template ends with a Provenance block (source tier / freshness / Honesty Protocol)'
        Run = {
            $tpl = Join-Path $SkillDir 'templates/progress-template.md'
            if (-not (Test-Path $tpl)) { throw "progress-template.md missing" }
            $t = Get-Content $tpl -Raw
            if ($t -notmatch [regex]::Escape('## Provenance')) { throw "Provenance footer heading missing from template" }
            if ($t -notmatch '(?i)source tier')  { throw "Provenance footer missing source-tier line" }
            if ($t -notmatch '(?i)freshness')    { throw "Provenance footer missing freshness line" }
            if ($t -notmatch [regex]::Escape('Honesty Protocol')) { throw "Provenance footer missing Honesty Protocol trust note" }
        }
    }
)

$pass = 0; $fail = 0
foreach ($t in $tests) {
    try { & $t.Run; $pass++; Write-Host "PASS $($t.Name)" -ForegroundColor Green }
    catch { $fail++; Write-Host "FAIL $($t.Name): $_" -ForegroundColor Red }
}
if ($fail -eq 0) { Write-Host "EVAL PASS personal-progress ($pass)" -ForegroundColor Green; exit 0 }
else { Write-Host "EVAL FAIL personal-progress ($fail of $($pass+$fail))" -ForegroundColor Red; exit 1 }
