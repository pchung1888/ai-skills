#requires -Version 7
# Eval grader for personal-wayfinder. See evals/eval-plan.md for the failure-mode map.
# Deterministic red/green grader. Exit 0 = all checks pass; exit 1 = at least one fails.
$ErrorActionPreference = 'Stop'

$SkillDir  = Resolve-Path (Join-Path $PSScriptRoot '..')
$Skill     = Join-Path $SkillDir 'SKILL.md'
$SkillsDir = Join-Path $SkillDir '..'

$tests = @(
    @{
        Name = 'skill_frontmatter: name, description, manual-only, ASCII'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?m)^name:\s*personal-wayfinder\s*$') { throw "frontmatter name not personal-wayfinder" }
            if ($s -notmatch '(?m)^description:\s*\S') { throw "frontmatter description missing" }
            if ($s -notmatch '(?m)^disable-model-invocation:\s*true\s*$') { throw "wayfinder must stay manual-only (it writes to trackers)" }
            $bad = @([System.IO.File]::ReadAllBytes($Skill) | Where-Object { $_ -gt 127 }).Count
            if ($bad) { throw "$bad non-ASCII bytes in SKILL.md" }
        }
    },
    @{
        Name = 'tracker_choice: Jira for company remotes, GitHub for github.com, local Markdown otherwise, recorded in Notes'
        Run = {
            $s = Get-Content $Skill -Raw
            foreach ($k in @('## Pick the tracker', 'github.com', '**GitHub**', '**Jira**', '**local Markdown**', "write the tracker's name in the map's **Notes**")) {
                if ($s -notmatch [regex]::Escape($k)) { throw "tracker rule lost: $k" }
            }
        }
    },
    @{
        Name = 'jira_safety: confirm before writing, ask for the project key, professional register, tool preflight'
        Run = {
            $s = Get-Content $Skill -Raw
            foreach ($k in @('Confirm before the first write in a session', 'Ask for the project key', 'Never assume one', 'Professional register', 'Preflight the tools')) {
                if ($s -notmatch [regex]::Escape($k)) { throw "Jira safety rule lost: $k" }
            }
        }
    },
    @{
        Name = 'github_and_local_ops: gh commands with honest fallbacks, and the local Markdown layout'
        Run = {
            $s = Get-Content $Skill -Raw
            foreach ($k in @('gh issue create', 'sub_issues', 'Part of #', 'Blocked by: #', 'Never report a link that the tool result did not confirm', 'docs/wayfinder/<map-slug>/MAP.md')) {
                if ($s -notmatch [regex]::Escape($k)) { throw "tracker operation lost: $k" }
            }
        }
    },
    @{
        Name = 'calls_our_skills: every skill it calls is ping-personal, exists, and accepts a Skill-tool call; no Matt-only names'
        Run = {
            $s = Get-Content $Skill -Raw
            foreach ($n in @('personal-online-research', 'personal-prototype', 'personal-grill-me', 'personal-wizard')) {
                if ($s -notmatch [regex]::Escape("ping-personal:$n")) { throw "wayfinder no longer calls ping-personal:$n" }
                $p = Join-Path $SkillsDir "$n/SKILL.md"
                if (-not (Test-Path $p)) { throw "$n/SKILL.md missing" }
                if ((Get-Content $p -Raw) -match '(?m)^disable-model-invocation:\s*true') { throw "$n is manual-only, so wayfinder's Skill call would be refused" }
            }
            foreach ($bad in @('setup-matt-pocock-skills', 'Skill tool with "research"', 'Skill tool with "prototype"', '"grilling" and "domain-modeling"')) {
                if ($s -match [regex]::Escape($bad)) { throw "a Matt-only call survived: $bad" }
            }
        }
    },
    @{
        Name = 'core_discipline: one ticket per session, claim before work, plan not do, fog vs ticket'
        Run = {
            $s = Get-Content $Skill -Raw
            foreach ($k in @('never resolve more than one ticket per session', 'before any work', "## Plan, don't do", '**Fog or ticket?**', '## Out of scope')) {
                if ($s -notmatch [regex]::Escape($k)) { throw "SKILL.md lost: $k" }
            }
        }
    }
)

$pass = 0; $fail = 0
foreach ($t in $tests) {
    try { & $t.Run; $pass++; Write-Host "PASS $($t.Name)" -ForegroundColor Green }
    catch { $fail++; Write-Host "FAIL $($t.Name): $_" -ForegroundColor Red }
}
if ($fail -eq 0) { Write-Host "EVAL PASS personal-wayfinder ($pass)" -ForegroundColor Green; exit 0 }
else { Write-Host "EVAL FAIL personal-wayfinder ($fail of $($pass+$fail))" -ForegroundColor Red; exit 1 }
