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
    },
    @{
        # F-SCOPE-6: the repair-loop shape. A phase produced by a plan or a findings pass
        # carries no owner warrant, and marking it done is what turned an inventory
        # into a shipped six-phase plan one defensible step at a time.
        Name = 'unwarranted_phase_refused: PASS on a PROPOSAL phase exits 6, no commit'
        Run = {
            $t = Join-Path ([System.IO.Path]::GetTempPath()) ("scope-" + [guid]::NewGuid())
            New-Item -ItemType Directory -Path $t | Out-Null
            Push-Location $t
            try {
                git init -q .; git config user.email t@t; git config user.name t
                $b = Join-Path $t 'b.md'
                python (Join-Path $SkillDir '../personal-goal/lib/beacon_writer.py') `
                    --slug scope --area test --branch main --accept-cmd 'pwsh x.ps1' `
                    --accept-match 'OK' --requirement 'ship the export button' --text-reviewed 'eval fixture reviewed 2026-09-18' --out $b *> $null
                # beacon_writer with no --plan-path renders one placeholder row; give it
                # an explicit PROPOSAL row so the guard has something to judge.
                (Get-Content $b -Raw) -replace '\| 1 \| -- \|', '| 1 | PROPOSAL |' |
                    Set-Content $b -Encoding utf8
                git add -A; git commit -qm init
                $head0 = (git rev-parse HEAD).Trim()
                python $Advance --beacon $b --phase 1 --outcome PASS --tokens 100 `
                    --duration 5 --commit abc1234 --subagent bunny --verify 'ran it; OK' *> $null
                if ($LASTEXITCODE -ne 6) { throw "PROPOSAL phase advanced; exit $LASTEXITCODE, expected 6" }
                if ((git rev-parse HEAD).Trim() -ne $head0) { throw "a refused advance created a commit" }
                # A warranted phase must still advance -- the guard must not be a wall.
                (Get-Content $b -Raw) -replace '\| 1 \| PROPOSAL \|', '| 1 | ASK:the export button |' |
                    Set-Content $b -Encoding utf8
                python $Advance --beacon $b --phase 1 --outcome PASS --tokens 100 `
                    --duration 5 --commit abc1234 --subagent bunny --verify 'ran it; OK' *> $null
                if ($LASTEXITCODE -ne 0) { throw "warranted phase refused; exit $LASTEXITCODE" }
            } finally { Pop-Location; Remove-Item $t -Recurse -Force -ErrorAction SilentlyContinue }
        }
    },
    @{
        # F-SCOPE-7: before this, Decisions/Detours could only ever be empty headings --
        # the same defect the Source column already had.
        Name = 'decision_and_detour_writers: rows land in their own tables; guards fire'
        Run = {
            $b = [System.IO.Path]::GetTempFileName() -replace '\.tmp$', '.md'
            try {
                python (Join-Path $SkillDir '../personal-goal/lib/beacon_writer.py') `
                    --slug d --area test --branch main --accept-cmd 'pwsh x.ps1' `
                    --accept-match 'OK' --requirement 'ship the thing' --text-reviewed 'eval fixture reviewed 2026-09-18' --out $b *> $null
                # A detour with no origin cannot be classified as detour-or-drift.
                python $Advance --beacon $b --detour-open 'test FAILS' --detour-checked 'x' *> $null
                if ($LASTEXITCODE -eq 0) { throw "detour opened without --detour-origin" }
                # Skipping the already-checked question is how new machinery gets built
                # beside a system that already does the job.
                python $Advance --beacon $b --detour-open 'test FAILS' --detour-origin 'pre-existing' *> $null
                if ($LASTEXITCODE -eq 0) { throw "detour opened without --detour-checked" }
                python $Advance --beacon $b --detour-open 'test FAILS' --detour-origin 'pre-existing' `
                    --detour-blocks 'phase 1' --detour-checked 'existing helper reviewed' *> $null
                if ($LASTEXITCODE -ne 0) { throw "valid detour refused" }
                python $Advance --beacon $b --decision 'do it this way' --decision-why 'because' *> $null
                if ($LASTEXITCODE -ne 0) { throw "decision write refused" }
                $c = Get-Content $b -Raw
                # Each row must be inside its own section, not appended to whichever
                # table happened to precede it.
                $dec = [regex]::Match($c, '(?ms)^## Decisions.*?(?=^## )').Value
                $det = [regex]::Match($c, '(?ms)^## Detours.*?(?=^## )').Value
                $chk = [regex]::Match($c, '(?ms)^## Last Known Good.*?(?=^## )').Value
                if ($dec -notmatch 'DEC-1') { throw "DEC-1 not in the Decisions section" }
                if ($det -notmatch 'DET-1') { throw "DET-1 not in the Detours section" }
                if ($chk -match 'DEC-|DET-') { throw "rows leaked into the checkpoint table" }
            } finally { Remove-Item $b -ErrorAction SilentlyContinue }
        }
    },
    @{
        # F-PIPE-1/2: mutation-proven gap. The writers escaped pipes and no reader
        # unescaped them, so one '|' in a detour Proof -- routine in shell output,
        # which is exactly what PROOF is documented to hold -- put Status one column
        # right of where close_detour_row wrote. The detour stayed open forever and
        # finalize returned exit 7 permanently. Removing the escaping left all 38
        # suites green, so this case exists to make that impossible again.
        Name = 'pipe_round_trip: pipes survive write/read/close in all three tables'
        Run = {
            python (Join-Path $PSScriptRoot 'check_pipe_round_trip.py') *> $null
            if ($LASTEXITCODE -ne 0) {
                throw "pipe round trip corrupted -- run evals/check_pipe_round_trip.py to see which"
            }
        }
    },
    @{
        # F-SCOPE-8: the return path. Closing a goal with a detour still open is how a
        # two-hour fix quietly becomes the project.
        Name = 'finalize_refuses_open_detour: acceptance blocked until the detour closes'
        Run = {
            $t = Join-Path ([System.IO.Path]::GetTempPath()) ("det-" + [guid]::NewGuid())
            New-Item -ItemType Directory -Path $t | Out-Null
            try {
                $b = Join-Path $t 'b.md'; $todo = Join-Path $t 'TODO.md'
                Set-Content $todo "## In Progress`n- **[GOAL 2026-09-18 d]** x" -Encoding utf8
                python (Join-Path $SkillDir '../personal-goal/lib/beacon_writer.py') `
                    --slug d --area test --branch main --accept-cmd 'pwsh -c "echo OK"' `
                    --accept-match 'OK' --requirement 'ship the thing' --text-reviewed 'eval fixture reviewed 2026-09-18' --out $b *> $null
                python $Advance --beacon $b --detour-open 'test FAILS' --detour-origin 'pre-existing' `
                    --detour-blocks 'phase 1' --detour-checked 'existing helper reviewed' *> $null
                python (Join-Path $Lib 'finalize.py') --beacon $b --todo $todo --slug d *> $null
                if ($LASTEXITCODE -ne 7) { throw "finalize allowed an open detour; exit $LASTEXITCODE, expected 7" }
                python $Advance --beacon $b --detour-close 'DET-1' *> $null
                python (Join-Path $Lib 'finalize.py') --beacon $b --todo $todo --slug d *> $null
                if ($LASTEXITCODE -ne 0) { throw "finalize refused after the detour closed; exit $LASTEXITCODE" }
            } finally { Remove-Item $t -Recurse -Force -ErrorAction SilentlyContinue }
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
