#requires -Version 7
# Eval grader for personal-drift-check. See evals/eval-plan.md for the failure-mode map.
#
# Two classes of test:
#   1. Fixture tests -- a locked 14-line transcript with a hand-computed answer.
#      Exercises the exclusions (meta tools, Agent, subagent turns, malformed JSON)
#      that a naive "count every tool_use" parser would get wrong.
#   2. The CALIBRATION INVARIANT -- the metric definition must keep reproducing the
#      published baseline in docs/harness-drift/. This is the test that matters: the
#      whole value of the meter is that its numbers are comparable to that analysis.
#      Skipped (not failed) when the reference transcripts are not on this machine.
$ErrorActionPreference = 'Stop'

$SkillDir = Resolve-Path (Join-Path $PSScriptRoot '..')          # personal-drift-check/
$Skill    = Join-Path $SkillDir 'SKILL.md'
$Script   = Join-Path $SkillDir 'drift-check.ps1'
$Fixture  = Join-Path $PSScriptRoot 'fixtures/sample-transcript.jsonl'

# Fixture ground truth, computed by hand from the 14 lines:
#   work tools (9) = Read,Read,Grep,Glob | Bash x3 | Edit,Write
#   evidence 4/9 = 44.4%   probe 5/9 = 55.6% (one Bash is a read-only `grep`)
#   shell 3/9 = 33.3%      action 2/9 = 22.2%      Agent 1 (excluded from denominator)
#   attributed 5/9 = 55.6%
# Excluded on purpose: a user-type line, ToolSearch (meta), a sidechain Read, malformed JSON.

function Get-FixtureJson {
    $out = (pwsh -NoProfile -File $Script -SessionFile $Fixture -Json 2>&1 | Out-String)
    if ($LASTEXITCODE -ne 0) { throw "drift-check.ps1 exited $LASTEXITCODE on the fixture. Output:`n$out" }
    return ($out | ConvertFrom-Json)
}

$tests = @(
    @{
        Name = 'skill_frontmatter: SKILL.md declares name=personal-drift-check + a description'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?m)^name:\s*personal-drift-check\s*$') { throw "frontmatter name not personal-drift-check" }
            if ($s -notmatch '(?m)^description:\s*\S') { throw "frontmatter description missing" }
        }
    },
    @{
        Name = 'script_present: drift-check.ps1 exists'
        Run = { if (-not (Test-Path $Script)) { throw "drift-check.ps1 missing at $Script" } }
    },
    @{
        Name = 'denominator_excludes_meta_agent_sidechain: totalCalls=9 on the fixture [F01,F02,F03]'
        Run = {
            $j = Get-FixtureJson
            if ($j.totalCalls -ne 9) {
                throw "expected totalCalls=9 (meta/Agent/sidechain/malformed excluded), got $($j.totalCalls)"
            }
        }
    },
    @{
        Name = 'evidence_share_math: evidencePct=44.4 on the fixture [E01]'
        Run = {
            $j = Get-FixtureJson
            if ([math]::Abs($j.evidencePct - 44.4) -gt 0.1) { throw "expected evidencePct 44.4, got $($j.evidencePct)" }
        }
    },
    @{
        Name = 'agent_counted_but_not_in_denominator: agentCalls=1 while totalCalls=9 [F04]'
        Run = {
            # Regression guard: delegating must never look like a drop in evidence share.
            $j = Get-FixtureJson
            if ($j.agentCalls -ne 1) { throw "expected agentCalls=1, got $($j.agentCalls)" }
            if ($j.totalCalls -ne 9) { throw "Agent leaked into the denominator (totalCalls=$($j.totalCalls))" }
        }
    },
    @{
        Name = 'readonly_shell_counts_as_probe_not_evidence: probePct=55.6, evidencePct=44.4 [F05]'
        Run = {
            # The `grep` Bash call must lift probe share but NOT the calibrated
            # evidence share -- otherwise calibration against the baseline breaks.
            $j = Get-FixtureJson
            if ([math]::Abs($j.probePct - 55.6) -gt 0.1) { throw "expected probePct 55.6, got $($j.probePct)" }
            if ([math]::Abs($j.evidencePct - 44.4) -gt 0.1) { throw "read-only shell leaked into evidence share" }
        }
    },
    @{
        Name = 'mutating_shell_is_not_a_probe: git-commit and npm-install excluded from probe [F06]'
        Run = {
            $j = Get-FixtureJson
            # 4 evidence + exactly 1 of 3 Bash calls = 5. If the mutating two counted, probe would be 7/9.
            if ($j.probePct -gt 60) { throw "mutating shell commands counted as probes (probePct=$($j.probePct))" }
        }
    },
    @{
        Name = 'verdict_band: 44.4% evidence yields HEALTHY [E02]'
        Run = {
            $j = Get-FixtureJson
            if ($j.verdict -ne 'HEALTHY') { throw "expected HEALTHY at 44.4% evidence, got '$($j.verdict)'" }
        }
    },
    @{
        Name = 'survives_malformed_json: exits 0 on a transcript with a broken line [F07]'
        Run = {
            $out = (pwsh -NoProfile -File $Script -SessionFile $Fixture 2>&1 | Out-String)
            if ($LASTEXITCODE -ne 0) { throw "crashed on malformed line (exit $LASTEXITCODE). Output:`n$out" }
        }
    },
    @{
        Name = 'CALIBRATION: reproduces the published baseline 144/375=38.4% and 78/733=10.6% [E03]'
        Run = {
            # Point DRIFT_CHECK_REF_DIR at the ~/.claude/projects/<project> folder holding the reference transcripts.
            $d = if ($env:DRIFT_CHECK_REF_DIR) { $env:DRIFT_CHECK_REF_DIR } else { Join-Path $env:TEMP 'drift-check-no-ref-dir' }
            $base = @('4542c564','fb6a4425','55dcc5c0','07570696') | ForEach-Object { Join-Path $d "$_*.jsonl" }
            $rec  = @('a7222290','4b8cea60','e855ab40')            | ForEach-Object { Join-Path $d "$_*.jsonl" }
            $haveBase = @($base | ForEach-Object { Get-ChildItem $_ -ErrorAction SilentlyContinue }).Count
            $haveRec  = @($rec  | ForEach-Object { Get-ChildItem $_ -ErrorAction SilentlyContinue }).Count
            if ($haveBase -lt 4 -or $haveRec -lt 3) {
                # Reference transcripts are machine-specific. Absence is not a defect
                # in the script, so this is reported and skipped rather than failed.
                Write-Host "  SKIP calibration: reference transcripts not on this machine ($haveBase/4 baseline, $haveRec/3 recent)" -ForegroundColor Yellow
                return
            }
            $b = & $Script -Cohort $base -Json | ConvertFrom-Json
            $r = & $Script -Cohort $rec  -Json | ConvertFrom-Json
            if ($b.totalCalls -ne 375)  { throw "BASELINE denominator drifted: expected 375, got $($b.totalCalls)" }
            if ($r.totalCalls -ne 733)  { throw "RECENT denominator drifted: expected 733, got $($r.totalCalls)" }
            if ([math]::Abs($b.evidencePct - 38.4) -gt 0.05) { throw "BASELINE evidence share drifted: expected 38.4, got $($b.evidencePct)" }
            if ([math]::Abs($r.evidencePct - 10.6) -gt 0.05) { throw "RECENT evidence share drifted: expected 10.6, got $($r.evidencePct)" }
        }
    }
)

$pass = 0; $fail = 0
foreach ($t in $tests) {
    try { & $t.Run; $pass++; Write-Host "PASS $($t.Name)" -ForegroundColor Green }
    catch { $fail++; Write-Host "FAIL $($t.Name): $_" -ForegroundColor Red }
}
if ($fail -eq 0) { Write-Host "EVAL PASS personal-drift-check ($pass)" -ForegroundColor Green; exit 0 }
else { Write-Host "EVAL FAIL personal-drift-check ($fail of $($pass+$fail))" -ForegroundColor Red; exit 1 }
