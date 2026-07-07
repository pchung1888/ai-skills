#requires -Version 7
# Eval grader for personal-goal. See evals/eval-plan.md for the failure-mode map.
# Exercises the real lib scripts: accept_gate.py (acceptance gate) + plan_parser.py
# (phasing) against known inputs. Exit 0 = pass, 1 = fail.
$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'   # cp1252 console guard (CLAUDE.md Windows pitfall)

$SkillDir = Resolve-Path (Join-Path $PSScriptRoot '..')          # personal-goal/
$Skill    = Join-Path $SkillDir 'SKILL.md'
$Lib      = Join-Path $SkillDir 'lib'
$Fixture  = Join-Path $PSScriptRoot 'fixtures/plan-2-phases.md'

# Run a lib script; return its exit code (no output).
function Invoke-Gate([string[]]$gateArgs) {
    python (Join-Path $Lib 'accept_gate.py') @gateArgs *> $null
    return $LASTEXITCODE
}

$tests = @(
    @{
        Name = 'skill_frontmatter: SKILL.md declares name=personal-goal + a description'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?m)^name:\s*personal-goal\s*$') { throw "frontmatter name not personal-goal" }
            if ($s -notmatch '(?m)^description:\s*\S') { throw "frontmatter description missing" }
        }
    },
    @{
        Name = 'lib_scripts_present: lib/accept_gate.py and lib/plan_parser.py exist'
        Run = {
            foreach ($f in @('accept_gate.py','plan_parser.py')) {
                if (-not (Test-Path (Join-Path $Lib $f))) { throw "missing load-bearing script: lib/$f" }
            }
        }
    },
    @{
        Name = 'accept_gate_enforces: valid gate ALLOWS; unverifiable + short-reason REJECTED [F01-F03]'
        Run = {
            $good = Invoke-Gate @('--validate','--accept-cmd','pwsh x.ps1','--accept-match','OK')
            if ($good -ne 0) { throw "valid accept-cmd + match was REJECTED (exit $good) -- F02" }
            $noMatch = Invoke-Gate @('--validate','--accept-cmd','pwsh x.ps1')
            if ($noMatch -eq 0) { throw "accept-cmd with NO match/regex was ACCEPTED -- F01 (unverifiable goal slipped through)" }
            $shortReason = Invoke-Gate @('--validate','--unverifiable','x')
            if ($shortReason -eq 0) { throw "1-char --unverifiable reason was ACCEPTED -- F03 (rubber-stamp escape hatch)" }
        }
    },
    @{
        Name = 'beacon_writer_vision_path: --vision-path flag renders vision_path frontmatter'
        Run = {
            $tmp = [System.IO.Path]::GetTempFileName() -replace '\.tmp$', '.md'
            try {
                $bw = Join-Path $Lib 'beacon_writer.py'
                python $bw --slug test-vision --area test --branch main `
                    --accept-cmd 'pwsh x.ps1' --accept-match 'OK' `
                    --vision-path 'docs/goals/test-vision.md' `
                    --out $tmp *> $null
                if ($LASTEXITCODE -ne 0) { throw "beacon_writer exited $LASTEXITCODE" }
                $content = Get-Content $tmp -Raw
                if ($content -notmatch '(?m)^vision_path:\s*docs/goals/test-vision\.md') {
                    throw "vision_path not rendered in frontmatter"
                }
            } finally { Remove-Item $tmp -ErrorAction SilentlyContinue }
        }
    },
    @{
        Name = 'skill_forced_amnesia_retry: SKILL.md documents forced-amnesia retry rule'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?i)forced.amnesia') {
                throw "SKILL.md must document the forced-amnesia retry rule section"
            }
            if ($s -notmatch '(?i)NEVER use SendMessage') {
                throw "SKILL.md must explicitly prohibit SendMessage continuation on retry"
            }
            if ($s -notmatch '(?i)exit.*4|code 4') {
                throw "SKILL.md must document exit code 4 (RETRY CAP / NO PROGRESS) as STOP-no-retry"
            }
            if ($s -notmatch '(?i)RETRY CONTEXT') {
                throw "SKILL.md must reference the RETRY CONTEXT section from agent-dispatch-template"
            }
        }
    },
    @{
        Name = 'agent_dispatch_retry_context: agent-dispatch-template.md has RETRY CONTEXT section'
        Run = {
            $tpl = Get-Content (Join-Path $SkillDir 'agent-dispatch-template.md') -Raw
            if ($tpl -notmatch '(?i)##\s+RETRY CONTEXT') {
                throw "agent-dispatch-template.md must have a ## RETRY CONTEXT section"
            }
            if ($tpl -notmatch '(?i)omit on first attempt') {
                throw "RETRY CONTEXT section must instruct to omit on first attempt"
            }
        }
    },
    @{
        Name = 'plan_parser_parses_fixture: both phases emitted in order [F04]'
        Run = {
            $out = (python (Join-Path $Lib 'plan_parser.py') $Fixture 2>&1) -join "`n"
            if ($LASTEXITCODE -ne 0) { throw "plan_parser failed: $out" }
            if ($out -notmatch 'Author three reference notes') { throw "phase 1 missing from parse" }
            if ($out -notmatch 'Deploy the notes')             { throw "phase 2 missing from parse" }
            $p1 = $out.IndexOf('Author three reference notes')
            $p2 = $out.IndexOf('Deploy the notes')
            if ($p1 -lt 0 -or $p2 -lt 0 -or $p1 -gt $p2) { throw "phases out of order" }
        }
    }
)

$pass = 0; $fail = 0
foreach ($t in $tests) {
    try { & $t.Run; $pass++; Write-Host "PASS $($t.Name)" -ForegroundColor Green }
    catch { $fail++; Write-Host "FAIL $($t.Name): $_" -ForegroundColor Red }
}
if ($fail -eq 0) { Write-Host "EVAL PASS personal-goal ($pass)" -ForegroundColor Green; exit 0 }
else { Write-Host "EVAL FAIL personal-goal ($fail of $($pass+$fail))" -ForegroundColor Red; exit 1 }
