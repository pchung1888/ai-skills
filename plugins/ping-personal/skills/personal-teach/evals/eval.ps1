#requires -Version 7
# Eval grader for personal-teach. See evals/eval-plan.md for the failure-mode map.
# Deterministic red/green grader. Exit 0 = all checks pass; exit 1 = at least one fails.
$ErrorActionPreference = 'Stop'

$SkillDir = Resolve-Path (Join-Path $PSScriptRoot '..')
$Skill    = Join-Path $SkillDir 'SKILL.md'
$Formats  = @('MISSION-FORMAT.md', 'RESOURCES-FORMAT.md', 'GLOSSARY-FORMAT.md', 'LEARNING-RECORD-FORMAT.md')

$tests = @(
    @{
        Name = 'skill_frontmatter: name, description and manual-only flag present'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?m)^name:\s*personal-teach\s*$') { throw "frontmatter name not personal-teach" }
            if ($s -notmatch '(?m)^description:\s*\S') { throw "frontmatter description missing" }
            if ($s -notmatch '(?m)^disable-model-invocation:\s*true\s*$') { throw "teach must stay manual-only (it creates a stateful workspace)" }
        }
    },
    @{
        Name = 'format_files: all four format files exist, are linked and are ASCII'
        Run = {
            $s = Get-Content $Skill -Raw
            foreach ($f in $Formats) {
                if ($s -notmatch [regex]::Escape("]($f)")) { throw "SKILL.md does not link $f" }
                $p = Join-Path $SkillDir $f
                if (-not (Test-Path $p)) { throw "$f missing" }
                $bad = @([System.IO.File]::ReadAllBytes($p) | Where-Object { $_ -gt 127 }).Count
                if ($bad) { throw "$bad non-ASCII bytes in $f" }
            }
        }
    },
    @{
        Name = 'never_in_a_code_repo: the workspace guard keeps lessons out of code repos'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch [regex]::Escape('Never use a code repo as the workspace')) { throw "code-repo workspace guard missing" }
        }
    },
    @{
        Name = 'lessons_render_with_md_to_html: lessons are Markdown rendered by personal-md-to-html, and that script exists'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch [regex]::Escape('skills/personal-md-to-html/md-to-html.py')) { throw "lessons no longer render with personal-md-to-html" }
            $script = Join-Path $SkillDir '../personal-md-to-html/md-to-html.py'
            if (-not (Test-Path $script)) { throw "md-to-html.py not found where the skill points" }
        }
    },
    @{
        Name = 'learning_science: mission first, retrieval practice, check-yourself section, sourced claims'
        Run = {
            $s = Get-Content $Skill -Raw
            foreach ($k in @('first ask the user why', 'Retrieval practice', 'Check yourself', 'Cites a source for every claim', 'Never trust your own memory as the source')) {
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
if ($fail -eq 0) { Write-Host "EVAL PASS personal-teach ($pass)" -ForegroundColor Green; exit 0 }
else { Write-Host "EVAL FAIL personal-teach ($fail of $($pass+$fail))" -ForegroundColor Red; exit 1 }
