#requires -Version 7
# eval.ps1 -- personal-loop skill eval. See evals/eval-plan.md.
# House-style deterministic grader: every check throws, the harness catches and
# counts, so ONE failing check no longer hides the rest (the pre-2026-07 tiered
# version exited at the first failing tier and had no calibration guard).
# Must print "EVAL PASS personal-loop" and exit 0 on success.
# Auto-discovered by run-all.ps1 via skills/*/evals/eval.ps1 glob.
# ASCII only (no em-dashes/smart-quotes -- Windows PowerShell 5.1 cp1252 pitfall).
$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'   # cp1252 console guard (CLAUDE.md Windows pitfall)

$SkillRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
$EvalDir   = $PSScriptRoot
$SkillsDir = Resolve-Path (Join-Path $SkillRoot '..')   # skills/
$SkillMd   = Join-Path $SkillRoot 'SKILL.md'

# Shared by the real graders AND the calibration mutations, so they never desync.
$RequiredHeaders = @(
    '## Roles block', '## Invocation', '## Pre-flight', '## Role Resolution',
    '## Tick lifecycle', '## Fence', '## Survival', '## REPORT format',
    '## Evidence-gathering', '## Orchestration'
)
$RequiredInvariants = @(
    'model: inherit',      # outer loop runs at the driving session's tier -- never pinned down
    'The Gate Law',        # the first-class invariant block
    'co-extensive',        # invariant 1 wording
    'all-goals-done',      # campaign-mode authoritative gate
    'Autonomy dial',       # tick-granularity tradeoff
    'severity-aware',      # resolved critic FIX contradiction
    'personal-fable-mode', # driving session runs the five-gate discipline
    'Trusted-input boundary',
    'human-evidence',      # invariant 4: loop never self-judges an unobservable
    'outer-loop-tracker'   # schema, source-of-truth, idempotent heartbeat (S6)
)
function Find-MissingPhrase([string]$text, [string[]]$phrases) {
    # Returns the missing phrases (empty array = all present).
    return @($phrases | Where-Object { $text -notmatch [regex]::Escape($_) })
}

$tests = @(
    @{
        Name = 'tier_a_lib_unit_tests: evals/test_lib.py exits 0'
        Run = {
            $out = & python (Join-Path $EvalDir 'test_lib.py') 2>&1 | Out-String
            if ($LASTEXITCODE -ne 0) { throw "lib unit tests failed (exit $LASTEXITCODE): $($out.Trim())" }
        }
    },
    @{
        Name = 'tier_b_headers: all 10 required SKILL.md section headers present'
        Run = {
            $missing = Find-MissingPhrase (Get-Content $SkillMd -Raw) $RequiredHeaders
            if ($missing.Count -gt 0) { throw "missing headers: $($missing -join ', ')" }
        }
    },
    @{
        Name = 'tier_c_invariants: load-bearing rule phrasings present (Gate Law, dial, fable-mode, ...)'
        Run = {
            $missing = Find-MissingPhrase (Get-Content $SkillMd -Raw) $RequiredInvariants
            if ($missing.Count -gt 0) { throw "missing invariant phrasing: $($missing -join ', ')" }
        }
    },
    @{
        Name = 'tier_d_lib_refs: every <module>.py referenced in SKILL.md or references/*.md resolves'
        Run = {
            $docFiles = @($SkillMd) + @(Get-ChildItem (Join-Path $SkillRoot 'references\*.md') -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
            $allText  = ($docFiles | ForEach-Object { Get-Content $_ -Raw }) -join "`n"
            $refs = [regex]::Matches($allText, '([A-Za-z0-9_]+)\.py') |
                ForEach-Object { $_.Groups[1].Value } | Sort-Object -Unique
            $dangling = @()
            foreach ($mod in $refs) {
                $hits = @(Get-ChildItem (Join-Path $SkillsDir "*\lib\$mod.py") -ErrorAction SilentlyContinue) +
                        @(Get-ChildItem (Join-Path $SkillsDir "*\evals\$mod.py") -ErrorAction SilentlyContinue)
                if (-not $hits) { $dangling += "$mod.py" }
            }
            if ($dangling.Count -gt 0) { throw "dangling lib references: $($dangling -join ', ')" }
        }
    },
    @{
        Name = 'calibration: a copy missing The Gate Law FAILS the invariant grader'
        Run = {
            $bad = (Get-Content $SkillMd -Raw) -replace 'The Gate Law', 'The Gate Rule'
            if ((Find-MissingPhrase $bad $RequiredInvariants).Count -eq 0) {
                throw "invariant grader passed a copy without The Gate Law -- dead metric"
            }
        }
    },
    @{
        Name = 'calibration: a copy missing the Fence header FAILS the header grader'
        Run = {
            $bad = (Get-Content $SkillMd -Raw) -replace '## Fence', '## Guardrail'
            if ((Find-MissingPhrase $bad $RequiredHeaders).Count -eq 0) {
                throw "header grader passed a copy without ## Fence -- dead metric"
            }
        }
    }
)

$pass = 0; $fail = 0
foreach ($t in $tests) {
    try { & $t.Run; $pass++; Write-Host "PASS $($t.Name)" -ForegroundColor Green }
    catch { $fail++; Write-Host "FAIL $($t.Name): $_" -ForegroundColor Red }
}
if ($fail -eq 0) { Write-Host "EVAL PASS personal-loop ($pass)" -ForegroundColor Green; exit 0 }
else { Write-Host "EVAL FAIL personal-loop ($fail of $($pass+$fail))" -ForegroundColor Red; exit 1 }
