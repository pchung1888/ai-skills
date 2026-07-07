#requires -Version 7
# Eval grader for personal-understanding. See evals/eval-plan.md for the failure-mode map.
# Deterministic red/green grader. Exit 0 = all checks pass; exit 1 = at least one fails.
# Runnable standalone OR from plugins/ping-personal/evals/run-all.ps1 (auto-discovered by glob).
# ASCII only (no em-dashes/smart-quotes -- Windows PowerShell 5.1 cp1252 pitfall).
# This skill is instruction-only (no scripts): we grade STRUCTURE + REFERENTIAL INTEGRITY.
$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'   # cp1252 console guard

$SkillDir = Resolve-Path (Join-Path $PSScriptRoot '..')   # personal-understanding/
$Skill    = Join-Path $SkillDir 'SKILL.md'
$Refs     = Join-Path $SkillDir 'references'
$Fix      = Join-Path $PSScriptRoot 'fixtures'

# Valid understand-anything sub-skill vocabulary (referential-integrity target).
# Checked against a known set rather than the filesystem so the eval does not depend
# on the plugin being installed in the eval environment (documented blind spot in eval-plan).
$ValidSubskills = @(
    'understand', 'understand-dashboard', 'understand-chat', 'understand-explain',
    'understand-diff', 'understand-domain', 'understand-onboard', 'understand-knowledge'
)

# Returns a list of violation strings for the TEXT-ONLY rules (so it works on fixtures too).
# Empty list = conforming. These are exactly the rules the skill's contract must satisfy.
function Get-SkillViolations([string]$text) {
    $v = @()

    # R1 frontmatter integrity
    if ($text -notmatch '(?m)^name:\s*personal-understanding\s*$') { $v += 'R1:name' }
    if ($text -notmatch '(?m)^model:\s*(haiku|sonnet|opus|fable|inherit|claude-[\w.\-\[\]]+)\s*$') { $v += 'R1:model' }
    if ($text -notmatch '(?m)^description:\s*\S') { $v += 'R1:description' }
    if ($text -notmatch 'understand-anything') { $v += 'R1:no-plugin-ref' }

    # R2 the three modes + the no-arg status default are documented
    foreach ($m in @('install', 'onboard', 'use')) {
        if ($text -notmatch ('`' + $m + '`')) { $v += "R2:mode:$m" }
    }
    if ($text -notmatch '(?i)status') { $v += 'R2:mode:status' }

    # R3 all six use sub-actions are documented (backtick-prefixed)
    foreach ($sa in @('dashboard', 'ask', 'explain', 'diff', 'domain', 'guide')) {
        if ($text -notmatch ('`' + $sa)) { $v += "R3:subaction:$sa" }
    }

    # R4 referential integrity: every understand-anything:<x> named must be a real sub-skill
    foreach ($mm in [regex]::Matches($text, 'understand-anything:([a-z\-]+)')) {
        $name = $mm.Groups[1].Value
        if ($ValidSubskills -notcontains $name) { $v += "R4:bad-subskill:$name" }
    }

    # R5 the core delegations must be present (a router that never delegates is broken)
    foreach ($req in @('understand-anything:understand', 'understand-anything:understand-dashboard', 'understand-anything:understand-chat')) {
        if ($text -notmatch [regex]::Escape($req)) { $v += "R5:missing-delegation:$req" }
    }

    # R6 AD-2 boundary: must state it CANNOT run the /plugin commands itself (honesty)
    if ($text -notmatch '(?is)CANNOT[\s\S]{0,80}/?plugin') { $v += 'R6:ad2-boundary' }

    return $v
}

function Test-IsAscii([string]$text) { return ($text -notmatch '[^\x00-\x7F]') }

$tests = @(
    @{
        Name = 'skill_present: SKILL.md exists'
        Run = { if (-not (Test-Path $Skill)) { throw "SKILL.md missing at $Skill" } }
    },
    @{
        Name = 'structure: real SKILL.md satisfies every contract rule (R1-R6)'
        Run = {
            $s = Get-Content $Skill -Raw
            $v = Get-SkillViolations $s
            if ($v.Count -gt 0) { throw "violations: $($v -join ', ')" }
        }
    },
    @{
        Name = 'ascii: real SKILL.md is pure ASCII (PowerShell 5.1 mojibake guard)'
        Run = {
            $s = Get-Content $Skill -Raw
            if (-not (Test-IsAscii $s)) { throw "SKILL.md contains non-ASCII characters" }
        }
    },
    @{
        Name = 'ref_files: every references/<file>.md named in SKILL.md exists on disk'
        Run = {
            $s = Get-Content $Skill -Raw
            $named = [regex]::Matches($s, 'references/([a-z0-9\-]+\.md)') | ForEach-Object { $_.Groups[1].Value } | Select-Object -Unique
            if ($named.Count -lt 1) { throw "SKILL.md names no reference files (expected install.md + install-detection.md)" }
            foreach ($f in $named) {
                if (-not (Test-Path (Join-Path $Refs $f))) { throw "referenced file missing: references/$f" }
            }
        }
    },
    @{
        Name = 'calibration_good: fixtures/good-skill.md passes all rules (grader is not over-strict)'
        Run = {
            $g = Get-Content (Join-Path $Fix 'good-skill.md') -Raw
            $v = Get-SkillViolations $g
            if ($v.Count -gt 0) { throw "good fixture wrongly rejected: $($v -join ', ')" }
        }
    },
    @{
        Name = 'calibration_bad: every fixtures/bad-*.md is rejected (grader is not over-lenient)'
        Run = {
            $bads = Get-ChildItem (Join-Path $Fix 'bad-*.md')
            if ($bads.Count -lt 1) { throw "no bad-* fixtures found -- grader is uncalibrated" }
            foreach ($b in $bads) {
                $t = Get-Content $b.FullName -Raw
                $v = Get-SkillViolations $t
                if ($v.Count -eq 0) { throw "bad fixture passed (should fail): $($b.Name)" }
            }
        }
    },
    @{
        Name = 'ascii_discriminates: the ASCII check flags a non-ASCII string but accepts a clean one'
        Run = {
            $emdash = "a" + [char]0x2014 + "b"   # constructed em-dash; no non-ASCII byte committed to disk
            if (Test-IsAscii $emdash) { throw "ASCII check failed to flag an em-dash" }
            if (-not (Test-IsAscii "plain ascii")) { throw "ASCII check wrongly flagged clean text" }
        }
    }
)

$pass = 0; $fail = 0
foreach ($t in $tests) {
    try { & $t.Run; $pass++; Write-Host "PASS $($t.Name)" -ForegroundColor Green }
    catch { $fail++; Write-Host "FAIL $($t.Name): $_" -ForegroundColor Red }
}
if ($fail -eq 0) { Write-Host "EVAL PASS personal-understanding ($pass)" -ForegroundColor Green; exit 0 }
else { Write-Host "EVAL FAIL personal-understanding ($fail of $($pass+$fail))" -ForegroundColor Red; exit 1 }
