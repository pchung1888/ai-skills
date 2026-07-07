#requires -Version 7
# eval.ps1 -- personal-loop skill eval.
# Must print "EVAL PASS personal-loop" and exit 0 on success.
# Auto-discovered by run-all.ps1 via skills/*/evals/eval.ps1 glob.
$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'   # cp1252 console guard (CLAUDE.md Windows pitfall)

$SkillRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
$EvalDir   = $PSScriptRoot
$SkillsDir = Resolve-Path (Join-Path $SkillRoot '..')   # skills/

# ---------------------------------------------------------------------------
# Tier A: lib unit tests
# ---------------------------------------------------------------------------
Write-Host 'personal-loop: running Tier A (lib unit tests)...'
$tierAOut = & python (Join-Path $EvalDir 'test_lib.py') 2>&1 | Out-String
Write-Host $tierAOut.TrimEnd()
if ($LASTEXITCODE -ne 0) {
    Write-Host 'personal-loop: Tier A FAILED (lib unit tests)' -ForegroundColor Red
    exit 1
}
Write-Host 'personal-loop: Tier A PASS' -ForegroundColor Green

# ---------------------------------------------------------------------------
# Tier B: SKILL.md structural check (8 required headers)
# ---------------------------------------------------------------------------
Write-Host 'personal-loop: running Tier B (SKILL.md structural check)...'
$skillMd = Join-Path $SkillRoot 'SKILL.md'
if (-not (Test-Path $skillMd)) {
    Write-Host "personal-loop: SKILL.md not found at $skillMd" -ForegroundColor Red
    exit 1
}
$content = Get-Content $skillMd -Raw

$required = @(
    '## Roles block',
    '## Invocation',
    '## Pre-flight',
    '## Role Resolution',
    '## Tick lifecycle',
    '## Fence',
    '## Survival',
    '## REPORT format',
    '## Evidence-gathering',
    '## Orchestration'
)
$missing = @()
foreach ($h in $required) {
    if ($content -notmatch [regex]::Escape($h)) { $missing += $h }
}
if ($missing.Count -gt 0) {
    Write-Host ("personal-loop: SKILL.md missing headers: {0}" -f ($missing -join ', ')) -ForegroundColor Red
    exit 1
}
Write-Host 'personal-loop: Tier B PASS (all 10 headers present)' -ForegroundColor Green

# ---------------------------------------------------------------------------
# Tier C: SKILL.md content invariants (header-presence is not enough -- guard
# against the load-bearing rules silently regressing or being contradicted)
# ---------------------------------------------------------------------------
Write-Host 'personal-loop: running Tier C (content invariants)...'
$invariants = @(
    'The Gate Law',        # the first-class invariant block
    'co-extensive',        # invariant 1 wording
    'all-goals-done',      # campaign-mode authoritative gate
    'Autonomy dial',       # tick-granularity tradeoff
    'severity-aware',      # resolved critic FIX contradiction
    'Trusted-input boundary',
    'human-evidence',      # invariant 4: loop never self-judges an unobservable
    'outer-loop-tracker'   # schema, source-of-truth, idempotent heartbeat (S6)
)
$absent = @()
foreach ($p in $invariants) {
    if ($content -notmatch [regex]::Escape($p)) { $absent += $p }
}
if ($absent.Count -gt 0) {
    Write-Host ("personal-loop: SKILL.md missing invariant phrasing: {0}" -f ($absent -join ', ')) -ForegroundColor Red
    exit 1
}
Write-Host 'personal-loop: Tier C PASS (content invariants present)' -ForegroundColor Green

# ---------------------------------------------------------------------------
# Tier D: every <module>.py referenced in SKILL.md OR references/*.md actually
# exists under some skills/*/lib or skills/*/evals (catches the dangling-
# reference class, e.g. an un-prefixed discover.py, in prose OR references, and
# whether or not the ref carries a lib/ prefix or is a bare backtick name).
# ---------------------------------------------------------------------------
Write-Host 'personal-loop: running Tier D (referenced lib files exist)...'
$docFiles = @($skillMd) + @(Get-ChildItem (Join-Path $SkillRoot 'references\*.md') -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
$allText  = ($docFiles | ForEach-Object { Get-Content $_ -Raw }) -join "`n"
$refs = [regex]::Matches($allText, '([A-Za-z0-9_]+)\.py') |
    ForEach-Object { $_.Groups[1].Value } | Sort-Object -Unique
$dangling = @()
foreach ($mod in $refs) {
    $hits = @(Get-ChildItem (Join-Path $SkillsDir "*\lib\$mod.py") -ErrorAction SilentlyContinue) +
            @(Get-ChildItem (Join-Path $SkillsDir "*\evals\$mod.py") -ErrorAction SilentlyContinue)
    if (-not $hits) { $dangling += "$mod.py" }
}
if ($dangling.Count -gt 0) {
    Write-Host ("personal-loop: SKILL.md references missing lib files: {0}" -f ($dangling -join ', ')) -ForegroundColor Red
    exit 1
}
Write-Host ("personal-loop: Tier D PASS ({0} referenced lib modules resolve)" -f $refs.Count) -ForegroundColor Green

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
Write-Host 'EVAL PASS personal-loop (4 tiers)' -ForegroundColor Green
exit 0
