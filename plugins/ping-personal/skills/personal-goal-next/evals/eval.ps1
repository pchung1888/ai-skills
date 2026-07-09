#requires -Version 7
# Eval grader for personal-goal-next. See evals/eval-plan.md for the failure-mode map.
# Tests the rule-4 refuse-guards (which return BEFORE git -- no commit) and unit-tests
# the beacon-mutation core via check_phase_table.py. Exit 0 = pass, 1 = fail.
$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'   # cp1252 console guard (CLAUDE.md Windows pitfall)

$SkillDir = Resolve-Path (Join-Path $PSScriptRoot '..')          # personal-goal-next/
$Skill    = Join-Path $SkillDir 'SKILL.md'
$Lib      = Join-Path $SkillDir 'lib'
$Advance  = Join-Path $Lib 'advance.py'
$PhaseChk = Join-Path $PSScriptRoot 'check_phase_table.py'

# Run advance.py with the given args against a nonexistent beacon; return exit code.
# A nonexistent --beacon means even a logic regression fails at read_text BEFORE git.
function Invoke-Advance([string[]]$advArgs) {
    python $Advance @advArgs *> $null
    return $LASTEXITCODE
}

$Behavioral = Join-Path $PSScriptRoot 'test_behavioral.py'

$tests = @(
    @{
        Name = 'skill_frontmatter: SKILL.md declares name=personal-goal-next + a description'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?m)^name:\s*personal-goal-next\s*$') { throw "frontmatter name not personal-goal-next" }
            if ($s -notmatch '(?m)^description:\s*\S') { throw "frontmatter description missing" }
        }
    },
    @{
        Name = 'lib_scripts_present: lib/advance.py and lib/phase_table.py exist'
        Run = {
            foreach ($f in @('advance.py','phase_table.py')) {
                if (-not (Test-Path (Join-Path $Lib $f))) { throw "missing load-bearing script: lib/$f" }
            }
        }
    },
    @{
        Name = 'advance_refuses_incomplete: PASS-no-commit + missing outcome/tokens refused, no commit [F01,F02,F06]'
        Run = {
            $head0 = (git rev-parse HEAD).Trim()
            $dummy = '/nonexistent/dummy.md'
            $passNoCommit = Invoke-Advance @('--beacon',$dummy,'--phase','1','--outcome','PASS','--tokens','100','--duration','5','--subagent','driver')
            if ($passNoCommit -eq 0) { throw "outcome=PASS with NO --commit was ALLOWED -- F02" }
            $noOutcome = Invoke-Advance @('--beacon',$dummy,'--phase','1','--tokens','100','--duration','5','--subagent','driver')
            if ($noOutcome -eq 0) { throw "advance with NO --outcome was ALLOWED -- F01" }
            $noTokens = Invoke-Advance @('--beacon',$dummy,'--phase','1','--outcome','FAIL','--duration','5','--subagent','driver')
            if ($noTokens -eq 0) { throw "advance with NO --tokens was ALLOWED -- F01" }
            # F08 unverified done: PASS without --verify must be REFUSED at the guard (exit 2),
            # not crash later at read_text (exit 1) -- the -ne 2 assert distinguishes the two.
            $passNoVerify = Invoke-Advance @('--beacon',$dummy,'--phase','1','--outcome','PASS','--tokens','100','--duration','5','--subagent','driver','--commit','abc1234')
            if ($passNoVerify -ne 2) { throw "outcome=PASS with NO --verify must refuse with exit 2 (got $passNoVerify) -- F08" }
            # The documented escape hatch must stay open: an explicit UNVERIFIED reason
            # passes the guard (any later exit here is the nonexistent-beacon crash, not 2).
            $passUnverified = Invoke-Advance @('--beacon',$dummy,'--phase','1','--outcome','PASS','--tokens','100','--duration','5','--subagent','driver','--commit','abc1234','--verify','UNVERIFIED: driver approved')
            if ($passUnverified -eq 2) { throw "explicit 'UNVERIFIED: <reason>' was refused -- escape hatch broken -- F08" }
            $head1 = (git rev-parse HEAD).Trim()
            if ($head0 -ne $head1) { throw "a refused advance created a git commit -- F06" }
        }
    },
    @{
        Name = 'phase_table_guards: check_phase_table.py exits 0 (flip + dup-reject + undeclared-reject) [F03,F04,F05]'
        Run = {
            python $PhaseChk *> $null
            if ($LASTEXITCODE -ne 0) { throw "phase_table guard regression -- run check_phase_table.py to see which" }
        }
    }
)

$pass = 0; $fail = 0
foreach ($t in $tests) {
    try { & $t.Run; $pass++; Write-Host "PASS $($t.Name)" -ForegroundColor Green }
    catch { $fail++; Write-Host "FAIL $($t.Name): $_" -ForegroundColor Red }
}

# -- Behavioral test suite --------------------------------------------------
$bOut = (python $Behavioral 2>&1 | Out-String)
$bExit = $LASTEXITCODE
foreach ($ln in ($bOut -split "`n")) {
    $ln = $ln.Trim()
    if ($ln -match '^PASS ') { $pass++; Write-Host "PASS behavioral/$($ln.Substring(5))" -ForegroundColor Green }
    elseif ($ln -match '^FAIL ') { $fail++; Write-Host "FAIL behavioral/$($ln.Substring(5))" -ForegroundColor Red }
}
if ($bExit -ne 0 -and ($bOut -notmatch 'FAIL ')) {
    # Script crashed entirely -- count it as one failure
    $fail++
    Write-Host "FAIL behavioral/test_behavioral.py (script error)" -ForegroundColor Red
    Write-Host $bOut
}

if ($fail -eq 0) { Write-Host "EVAL PASS personal-goal-next ($pass)" -ForegroundColor Green; exit 0 }
else { Write-Host "EVAL FAIL personal-goal-next ($fail of $($pass+$fail))" -ForegroundColor Red; exit 1 }
