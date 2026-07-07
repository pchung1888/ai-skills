#requires -Version 7
# Behavioral test: babysit.py report-only sweep.
# Hermetic: creates a temp dir with 2 fixture beacons + a fixture TODO.md,
# runs babysit.py (with and without --run-acceptance), asserts table rows.
# Exit 0 = all pass.
$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'

$SkillDir = Resolve-Path (Join-Path $PSScriptRoot '..')
$Script   = Join-Path $SkillDir 'lib/babysit.py'

# ---------------------------------------------------------------------------
# Fixture setup
# ---------------------------------------------------------------------------
$tmp = Join-Path ([System.IO.Path]::GetTempPath()) "babysit-eval-$([System.Guid]::NewGuid().ToString('N').Substring(0,8))"
New-Item -ItemType Directory -Path $tmp | Out-Null
$docsDir = Join-Path $tmp 'docs'
New-Item -ItemType Directory -Path $docsDir | Out-Null

# Beacon 1: fresh, trivially-passing accept_cmd (python -c "print('DONE')")
$beacon1 = Join-Path $docsDir 'fresh-goal-audit-tracker.md'
@"
---
goal_slug: fresh-goal
goal_owner: Test
started: 2026-06-11 00:00:00
branch: main
accept_cmd: python -c "print('DONE')"
accept_shell:
accept_match: DONE
accept_regex:
accept_status: verifiable
---

# Audit Tracker -- fresh-goal
"@ | Set-Content -Path $beacon1 -Encoding utf8

# Beacon 2: stale (set mtime to 30 days ago), unverifiable accept_status
$beacon2 = Join-Path $docsDir 'old-goal-audit-tracker.md'
@"
---
goal_slug: old-goal
goal_owner: Test
started: 2025-01-01 00:00:00
branch: nonexistent-branch-xyz
accept_cmd:
accept_shell:
accept_match:
accept_regex:
accept_status: unverifiable
---

# Audit Tracker -- old-goal
"@ | Set-Content -Path $beacon2 -Encoding utf8

# Force mtime to 30 days ago on beacon2
$oldTime = (Get-Date).AddDays(-30)
(Get-Item $beacon2).LastWriteTime = $oldTime

# Fixture TODO.md
$todoFile = Join-Path $tmp 'TODO.md'
@"
# TODO

## To Be Tested
- **[GOAL 2026-06-11 fresh-goal]** Some description. Beacon: docs/fresh-goal-audit-tracker.md.
- **[GOAL 2025-01-01 old-goal]** Some description. Beacon: docs/old-goal-audit-tracker.md.
"@ | Set-Content -Path $todoFile -Encoding utf8

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
function Run-Babysit {
    param([switch]$RunAcceptance)
    if ($RunAcceptance) {
        $out = python $Script --todo $todoFile --docs-root $docsDir --run-acceptance 2>&1
    } else {
        $out = python $Script --todo $todoFile --docs-root $docsDir 2>&1
    }
    return $out -join "`n"
}

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
$pass = 0; $fail = 0

function Assert-Contains {
    param([string]$Label, [string]$Output, [string]$Expected)
    if ($Output -notlike "*$Expected*") {
        $script:fail++
        Write-Host "FAIL $Label : expected '$Expected' in output" -ForegroundColor Red
        Write-Host "  Output: $Output" -ForegroundColor DarkRed
    } else {
        $script:pass++
        Write-Host "PASS $Label" -ForegroundColor Green
    }
}

# Test 1: without --run-acceptance, both slugs appear and gate = 'not run'
$out1 = Run-Babysit
Assert-Contains 'babysit_no_run_fresh_slug'    $out1 'fresh-goal'
Assert-Contains 'babysit_no_run_old_slug'      $out1 'old-goal'
Assert-Contains 'babysit_no_run_gate_not_run'  $out1 'not run'

# Test 2: fresh beacon shows 'fresh' staleness
Assert-Contains 'babysit_fresh_beacon_not_stale' $out1 'fresh'

# Test 3: old beacon shows 'STALE'
Assert-Contains 'babysit_old_beacon_stale' $out1 'STALE'

# Test 4: old beacon branch = nonexistent -> 'branch-missing'
Assert-Contains 'babysit_old_branch_missing' $out1 'branch-missing'

# Test 5: with --run-acceptance, fresh-goal shows PASS (accept_cmd: python -c "print('DONE')")
$out2 = Run-Babysit -RunAcceptance
Assert-Contains 'babysit_run_accept_fresh_pass' $out2 'PASS'

# Test 6: with --run-acceptance, old-goal shows UNVERIFIABLE (accept_status: unverifiable)
Assert-Contains 'babysit_run_accept_old_unverifiable' $out2 'UNVERIFIABLE'

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------
Remove-Item -Recurse -Force $tmp

# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------
if ($fail -eq 0) {
    Write-Host "BABYSIT TESTS PASS ($pass)" -ForegroundColor Green
    exit 0
} else {
    Write-Host "BABYSIT TESTS FAIL ($fail of $($pass+$fail))" -ForegroundColor Red
    exit 1
}
