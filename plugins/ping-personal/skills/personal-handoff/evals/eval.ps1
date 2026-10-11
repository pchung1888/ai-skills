#requires -Version 7
# Eval grader for personal-handoff (instruction-only). See evals/eval-plan.md.
# Structural grader: the capture steps, output path, progress-vs-handoff contract, and
# the templates scaffold must all be intact.
$ErrorActionPreference = 'Stop'

$SkillDir = Resolve-Path (Join-Path $PSScriptRoot '..')          # personal-handoff/
$Skill    = Join-Path $SkillDir 'SKILL.md'

$tests = @(
    @{
        Name = 'skill_frontmatter: SKILL.md declares name=personal-handoff + a description'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?m)^name:\s*personal-handoff\s*$') { throw "frontmatter name not personal-handoff" }
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
    },
    @{
        # A handoff that carries only conclusions hands the next session maximum
        # confidence and minimum context. These three sections are what carry the ask,
        # the doubts, and the way back.
        Name = 'antidrift_sections: template requires the ask, the doubts, and open detours'
        Run  = {
            $t = Get-Content (Join-Path $SkillDir 'templates/progress-template.md') -Raw
            if ($t -notmatch '(?m)^## The ask \(verbatim\)') { throw "template has no verbatim ask section" }
            if ($t -notmatch '(?m)^## What I am unsure about') { throw "template has no uncertainty section" }
            if ($t -notmatch '(?m)^## Open detours') { throw "template has no open-detours section" }
            $s = Get-Content $Skill -Raw
            if ($s -notmatch 'What I am unsure about') { throw "SKILL.md does not require the uncertainty section" }
            if ($s -notmatch 'Never paraphrase') { throw "SKILL.md does not forbid paraphrasing the ask" }
            if ($s -notmatch '(?i)link, do not restate') { throw "SKILL.md does not carry the link-not-restate rule" }
        }
    },
    @{
        Name = 'unattended_flag_documented: SKILL.md documents --unattended and the -audit-tracker.md path args'
        Run  = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?m)^## Unattended mode') { throw "no '## Unattended mode' section" }
            if ($s -notmatch [regex]::Escape('--unattended')) { throw "--unattended not documented" }
            if ($s -notmatch [regex]::Escape('-audit-tracker.md')) { throw "bound tracker path pattern -audit-tracker.md not documented" }
        }
    },
    @{
        Name = 'unattended_asks_no_questions: unattended mode asks the user nothing'
        Run  = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?i)unattended[^\n]*asks? no questions|asks? no questions[^\n]*unattended|ask no questions') { throw "no 'ask no questions' rule for unattended mode" }
        }
    },
    @{
        Name = 'unattended_writes_unknown: unreadable items are written as Unknown'
        Run  = {
            $s = Get-Content $Skill -Raw
            $i = $s.IndexOf('## Unattended mode')
            if ($i -lt 0) { throw "no Unattended mode section" }
            if ($s.Substring($i) -notmatch '(?i)writes? `Unknown`') { throw "unattended section does not say to write Unknown" }
        }
    },
    @{
        Name = 'unattended_skips_readback: unattended mode skips the verbatim read-back'
        Run  = {
            $s = Get-Content $Skill -Raw
            $i = $s.IndexOf('## Unattended mode')
            if ($i -lt 0) { throw "no Unattended mode section" }
            if ($s.Substring($i) -notmatch '(?i)skip[^\n]*read-back') { throw "unattended section does not skip the read-back" }
        }
    },
    @{
        Name = 'unattended_never_commits: unattended mode never commits or asks about committing'
        Run  = {
            $s = Get-Content $Skill -Raw
            $i = $s.IndexOf('## Unattended mode')
            if ($i -lt 0) { throw "no Unattended mode section" }
            if ($s.Substring($i) -notmatch '(?i)never commit') { throw "unattended section does not say never commit" }
        }
    },
    @{
        Name = 'goal_beacon_per_bound_path: SKILL.md and template carry a Goal beacon: <path> line, one per bound path, deduped'
        Run  = {
            $s = Get-Content $Skill -Raw
            $t = Get-Content (Join-Path $SkillDir 'templates/progress-template.md') -Raw
            if ($t -notmatch '(?m)^Goal beacon: ') { throw "template has no 'Goal beacon: <path>' line" }
            if ($s -notmatch [regex]::Escape('Goal beacon: <path>')) { throw "SKILL.md does not document 'Goal beacon: <path>'" }
            if ($s -notmatch '(?i)one `Goal beacon: <path>` line per bound path') { throw "no one-line-per-bound-path rule" }
            if ($s -notmatch '(?i)dedup') { throw "no dedupe rule" }
        }
    }
)

$pass = 0; $fail = 0
foreach ($t in $tests) {
    try { & $t.Run; $pass++; Write-Host "PASS $($t.Name)" -ForegroundColor Green }
    catch { $fail++; Write-Host "FAIL $($t.Name): $_" -ForegroundColor Red }
}
if ($fail -eq 0) { Write-Host "EVAL PASS personal-handoff ($pass)" -ForegroundColor Green; exit 0 }
else { Write-Host "EVAL FAIL personal-handoff ($fail of $($pass+$fail))" -ForegroundColor Red; exit 1 }
