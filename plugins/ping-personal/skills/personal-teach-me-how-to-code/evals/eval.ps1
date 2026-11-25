#requires -Version 7
# Eval grader for personal-teach-me-how-to-code. See evals/eval-plan.md for the failure-mode map.
# Deterministic red/green grader. Exit 0 = all checks pass; exit 1 = at least one fails.
$ErrorActionPreference = 'Stop'

$SkillDir = Resolve-Path (Join-Path $PSScriptRoot '..')
$Skill    = Join-Path $SkillDir 'SKILL.md'
$Skills   = Resolve-Path (Join-Path $SkillDir '..')
$Refs     = @('reading-order.md', 'step-example.md', 'page-mode.md', 'findings-notes.md', 'data-boundary.md', 'ops-scripts.md')
$Shape    = Join-Path $Skills 'personal-copilot-talk/evals/eval.ps1'

function Read-Text([string]$Path) { (Get-Content $Path -Raw) -replace "`r`n", "`n" }
function Assert-Ascii([string]$Path) {
    $bad = @([System.IO.File]::ReadAllBytes($Path) | Where-Object { $_ -gt 127 }).Count
    if ($bad) { throw "$bad non-ASCII bytes in $Path" }
}

$tests = @(
    @{
        Name = 'skill_frontmatter: name, Use-when description, ASCII, no wizard trigger'
        Run = {
            $s = Read-Text $Skill
            if ($s -notmatch '(?m)^name:\s*personal-teach-me-how-to-code\s*$') { throw "frontmatter name wrong" }
            if ($s -notmatch '(?m)^description:\s*Use when') { throw "description must start with 'Use when'" }
            $desc = ([regex]::Match($s, '(?m)^description:(.*)$')).Groups[1].Value
            if ($desc -match '(?i)walk me through') { throw "description uses 'walk me through', which personal-wizard owns" }
            Assert-Ascii $Skill
        }
    },
    @{
        Name = 'references: every reference file is linked from SKILL.md, exists and is ASCII'
        Run = {
            $s = Read-Text $Skill
            foreach ($f in $Refs) {
                if ($s -notmatch [regex]::Escape("](references/$f)")) { throw "SKILL.md does not link references/$f" }
                Assert-Ascii (Join-Path $SkillDir "references/$f")
            }
        }
    },
    @{
        Name = 'reuse: the skills and scripts SKILL.md points at exist'
        Run = {
            foreach ($p in @('personal-htsw/walk/walk-build.py', 'personal-htsw/walk/walk-check.py',
                    'personal-htsw/references/walk-page.md', 'personal-copilot-talk/SKILL.md',
                    'personal-teach-me-how-to-code/scripts/check_plan.py')) {
                if (-not (Test-Path (Join-Path $Skills $p))) { throw "missing $p" }
            }
            $s = Read-Text $Skill
            foreach ($k in @('scripts/check_plan.py', 'walk/walk-build.py', 'walk/walk-check.py', 'personal-copilot-talk')) {
                if ($s -notmatch [regex]::Escape($k)) { throw "SKILL.md no longer names $k" }
            }
        }
    },
    @{
        Name = 'skill_contract: the rules from the real lesson are still in SKILL.md'
        Run = {
            $s = Read-Text $Skill
            foreach ($k in @('Read-only. Never edit it', 'build order', 'more than 60 lines', 'PLAN FAIL',
                    'In ASP terms', 'React pattern here', '.NET idea here', 'ASCII flow diagram',
                    'Two or three checkable questions', 'EXTRACTED, INFERRED or UNKNOWN',
                    'Page mode (default)', 'walk-check.py` exits 0', 'One step per reply',
                    'Do not move on until the user', 'Do not duplicate it', 'dated decisions',
                    'list_connected_browsers', '`localhost` tabs', 'the user caught a skipped 8b',
                    'one step per kind of call', 'whole wiring chain', 'mapping table',
                    'Never cut the key line', 'Show the wiring chain once', 'parity or mapping file',
                    'operator view', 'Step | File | Lines | Job', 'Rollback gets its own step',
                    'Symptom | Likely cause | Check | Fix', 'Teach what the operator sets up')) {
                if ($s -notmatch [regex]::Escape($k)) { throw "SKILL.md lost: $k" }
            }
        }
    },
    @{
        Name = 'plan_check: check_plan.py unit tests pass (skipped section fails the plan)'
        Run = {
            Push-Location $SkillDir
            try {
                $out = (python -m unittest evals/test_check_plan.py 2>&1 | Out-String)
                if ($LASTEXITCODE -ne 0) { throw "unit tests failed:`n$out" }
            } finally { Pop-Location }
        }
    },
    @{
        Name = 'step_shape: good-*.md pass and bad-*.md fail the copilot-talk reply grader'
        Run = {
            foreach ($f in Get-ChildItem (Join-Path $PSScriptRoot 'fixtures') -Filter '*.md') {
                $null = pwsh -NoProfile -File $Shape -ReplyFile $f.FullName 2>&1
                $ok = $LASTEXITCODE -eq 0
                if ($f.Name -like 'good-*' -and -not $ok) { throw "$($f.Name) failed the reply shape" }
                if ($f.Name -like 'bad-*' -and $ok) { throw "$($f.Name) passed but should fail" }
            }
        }
    }
)

$pass = 0; $fail = 0
foreach ($t in $tests) {
    try { & $t.Run; $pass++; Write-Host "PASS $($t.Name)" -ForegroundColor Green }
    catch { $fail++; Write-Host "FAIL $($t.Name): $_" -ForegroundColor Red }
}
if ($fail -eq 0) { Write-Host "EVAL PASS personal-teach-me-how-to-code ($pass)" -ForegroundColor Green; exit 0 }
else { Write-Host "EVAL FAIL personal-teach-me-how-to-code ($fail of $($pass+$fail))" -ForegroundColor Red; exit 1 }
