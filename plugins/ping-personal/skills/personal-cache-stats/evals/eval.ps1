#requires -Version 7
# Eval grader for personal-cache-stats. See evals/eval-plan.md for the failure-mode map.
# Runs cache-stats.ps1 against a locked fixture transcript with a known answer
# (Turns=2, READ=800, Hit rate=80% WARM) and asserts the deterministic output.
$ErrorActionPreference = 'Stop'

$SkillDir = Resolve-Path (Join-Path $PSScriptRoot '..')          # personal-cache-stats/
$Skill    = Join-Path $SkillDir 'SKILL.md'
$Script   = Join-Path $SkillDir 'cache-stats.ps1'
$Fixture  = Join-Path $PSScriptRoot 'fixtures/sample-transcript.jsonl'

$tests = @(
    @{
        Name = 'skill_frontmatter: SKILL.md declares name=personal-cache-stats + a description'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?m)^name:\s*personal-cache-stats\s*$') { throw "frontmatter name not personal-cache-stats" }
            if ($s -notmatch '(?m)^description:\s*\S') { throw "frontmatter description missing" }
        }
    },
    @{
        Name = 'script_present: cache-stats.ps1 exists'
        Run = { if (-not (Test-Path $Script)) { throw "cache-stats.ps1 missing at $Script" } }
    },
    @{
        Name = 'parses_known_fixture: -SessionFile yields Turns=2, READ=800, Hit rate 80% WARM (E01)'
        Run = {
            $out = (pwsh -NoProfile -File $Script -SessionFile $Fixture 2>&1 | Out-String)
            if ($LASTEXITCODE -ne 0) { throw "cache-stats.ps1 exited $LASTEXITCODE on the fixture" }
            if ($out -notmatch 'Turns\s*:\s*2\b')            { throw "expected Turns=2 (noise lines not skipped?). Output:`n$out" }
            if ($out -notmatch 'Cache READ\s*\(hit\)\s*:\s*800') { throw "expected Cache READ=800. Output:`n$out" }
            if ($out -notmatch 'Hit rate\s*:\s*80')          { throw "expected Hit rate 80 (math drift). Output:`n$out" }
            if ($out -notmatch 'WARM')                       { throw "expected WARM verdict band. Output:`n$out" }
        }
    },
    @{
        Name = 'skips_noise: no-usage + malformed-json lines skipped (Turns=2, no crash) [F02,F03]'
        Run = {
            # The fixture has 4 lines: 1 no-usage, 2 valid, 1 malformed. A correct run
            # reports exactly 2 turns and exits 0. Turns!=2 or a crash fails this.
            $out = (pwsh -NoProfile -File $Script -SessionFile $Fixture 2>&1 | Out-String)
            if ($LASTEXITCODE -ne 0) { throw "crashed on noisy transcript (exit $LASTEXITCODE)" }
            if ($out -notmatch 'of 2 total in file') { throw "did not skip the no-usage/malformed lines. Output:`n$out" }
        }
    }
)

$pass = 0; $fail = 0
foreach ($t in $tests) {
    try { & $t.Run; $pass++; Write-Host "PASS $($t.Name)" -ForegroundColor Green }
    catch { $fail++; Write-Host "FAIL $($t.Name): $_" -ForegroundColor Red }
}
if ($fail -eq 0) { Write-Host "EVAL PASS personal-cache-stats ($pass)" -ForegroundColor Green; exit 0 }
else { Write-Host "EVAL FAIL personal-cache-stats ($fail of $($pass+$fail))" -ForegroundColor Red; exit 1 }
