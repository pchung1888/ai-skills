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
        Name = 'dispatch_evidence_contract: return contract requires done_check + verification; SKILL.md wires personal-fable-mode'
        Run = {
            $tpl = Get-Content (Join-Path $SkillDir 'agent-dispatch-template.md') -Raw
            if ($tpl -notmatch '(?m)^done_check:') { throw "return contract missing done_check field" }
            if ($tpl -notmatch '(?m)^verification:') { throw "return contract missing verification field" }
            if ($tpl -notmatch 'UNVERIFIED:') { throw "verification field must document the UNVERIFIED:<reason> escape hatch" }
            $s = Get-Content $Skill -Raw
            if ($s -notmatch 'personal-fable-mode') { throw "SKILL.md does not cross-reference personal-fable-mode" }
        }
    },
    @{
        Name = 'skill_frontmatter: SKILL.md declares name=personal-goal + a description'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?m)^name:\s*personal-goal\s*$') { throw "frontmatter name not personal-goal" }
            if ($s -notmatch '(?m)^description:\s*\S') { throw "frontmatter description missing" }
            if ($s -notmatch '(?m)^model:\s*inherit\s*$') { throw "model: inherit missing -- goal driver runs at the session tier, never pinned" }
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
                    --no-requirement 'eval fixture: no owner ask for a synthetic goal' `
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
    @{
        # F-SCOPE-1: arming with no record of what was asked for is how every later
        # phase ends up checked against the previous plan instead of the owner.
        Name = 'beacon_writer_refuses_without_requirement: bare arm exits non-zero'
        Run  = {
            $tmp = [System.IO.Path]::GetTempFileName() -replace '\.tmp$', '.md'
            try {
                python (Join-Path $Lib 'beacon_writer.py') --slug t --area test --branch main `
                    --accept-cmd 'pwsh x.ps1' --accept-match 'OK' --out $tmp *> $null
                if ($LASTEXITCODE -eq 0) { throw "armed with no requirement; should have refused" }
            } finally { Remove-Item $tmp -ErrorAction SilentlyContinue }
        }
    }
    @{
        # F-SCOPE-2: an escape hatch with no floor becomes the default.
        Name = 'beacon_writer_rejects_token_reason: --no-requirement needs a real reason'
        Run  = {
            $tmp = [System.IO.Path]::GetTempFileName() -replace '\.tmp$', '.md'
            try {
                python (Join-Path $Lib 'beacon_writer.py') --slug t --area test --branch main `
                    --accept-cmd 'pwsh x.ps1' --accept-match 'OK' --no-requirement 'x' --out $tmp *> $null
                if ($LASTEXITCODE -eq 0) { throw "accepted a 1-char reason" }
                python (Join-Path $Lib 'beacon_writer.py') --slug t --area test --branch main `
                    --accept-cmd 'pwsh x.ps1' --accept-match 'OK' `
                    --no-requirement 'exploratory spike, no ask yet' --out $tmp *> $null
                if ($LASTEXITCODE -ne 0) { throw "rejected a real reason" }
                $c = Get-Content $tmp -Raw
                if ($c -notmatch '(?m)^requirement_status:\s*none --') { throw "reason not recorded in frontmatter" }
            } finally { Remove-Item $tmp -ErrorAction SilentlyContinue }
        }
    }
    @{
        # F-SCOPE-3: a real ask runs to several lines; frontmatter cannot hold that,
        # which is why it lives in a body section.
        Name = 'requirement_verbatim_multiline: multi-line ask survives the round trip'
        Run  = {
            $tmp = [System.IO.Path]::GetTempFileName() -replace '\.tmp$', '.md'
            $req = [System.IO.Path]::GetTempFileName()
            try {
                Set-Content -LiteralPath $req -Value "first line of the ask`nsecond line of the ask" -Encoding utf8
                python (Join-Path $Lib 'beacon_writer.py') --slug t --area test --branch main `
                    --accept-cmd 'pwsh x.ps1' --accept-match 'OK' --requirement-file $req --text-reviewed 'eval fixture reviewed 2026-09-18' --out $tmp *> $null
                if ($LASTEXITCODE -ne 0) { throw "beacon_writer exited $LASTEXITCODE" }
                $c = Get-Content $tmp -Raw
                if ($c -notmatch '(?m)^requirement_status:\s*provided') { throw "status not provided" }
                if ($c -notmatch '(?m)^## Requirement') { throw "no Requirement section" }
                if ($c -notmatch '> first line of the ask') { throw "line 1 missing" }
                if ($c -notmatch '> second line of the ask') { throw "line 2 missing" }
            } finally { Remove-Item $tmp, $req -ErrorAction SilentlyContinue }
        }
    }
    @{
        # F-SCOPE-4: the old parser filled Source with the phase's own number, so the
        # provenance column could never be empty and never meant anything.
        Name = 'plan_parser_source_is_proposal: parsed phases carry no fake warrant'
        Run  = {
            $out = python (Join-Path $Lib 'plan_parser.py') $Fixture 2>&1 | Out-String
            if ($out -match 'Plan\s') { throw "still emitting a self-referential Source value" }
            if ($out -notmatch 'PROPOSAL') { throw "parsed phase not labelled PROPOSAL" }
        }
    }
    @{
        # CLAUDE.md: files that get parsed stay pure ASCII.
        Name = 'plan_parser_is_ascii: no non-ASCII in a parsed source file'
        Run  = {
            $bytes = [System.IO.File]::ReadAllBytes((Join-Path $Lib 'plan_parser.py'))
            $bad = $bytes | Where-Object { $_ -gt 127 }
            if ($bad.Count -gt 0) { throw "plan_parser.py contains $($bad.Count) non-ASCII bytes" }
        }
    }
    @{
        # F-SCOPE-5: a '|' inside a free-text Source cell shifts every later column and
        # the next advance raises on the column count.
        Name = 'plan_parser_escapes_pipes: a pipe in a title cannot break the table'
        Run  = {
            $out = python -c @"
import sys; sys.path.insert(0, r'$Lib')
from plan_parser import phase_rows
print(phase_rows([(1, 'title with | a pipe')]))
"@ 2>&1 | Out-String
            $rows = @($out -split "`r?`n" | Where-Object { $_ -match '^\|' })
            if ($rows.Count -lt 1) { throw "no table row emitted: $out" }
            if ([string]$rows[0] -notmatch '\\|') { throw "pipe in title was not escaped" }
            # Column counting lives in evals/check_pipe_round_trip.py over in
            # personal-goal-next, which uses the SAME reader production uses. The
            # earlier version of this test counted with its own escape-aware regex,
            # so it graded the emitter against a smarter reader than the code had and
            # certified a fix that did not hold in production.
        }
    }
    @{
        # F-LEAK-1: the requirement is the owner's unedited words and it lands in a
        # git-committed file. docs/ is tracked in some host repos, so
        # removing it later means rewriting history, not editing a file.
        Name = 'requirement_not_committed_unseen: exit 8 without a read-back ack'
        Run  = {
            $tmp = [System.IO.Path]::GetTempFileName() -replace '\.tmp$', '.md'
            try {
                $bw = Join-Path $Lib 'beacon_writer.py'
                python $bw --slug t --area test --branch main --accept-cmd 'pwsh x.ps1' `
                    --accept-match 'OK' --requirement 'ship the thing' --out $tmp *> $null
                if ($LASTEXITCODE -ne 8) { throw "committed owner text unseen; exit $LASTEXITCODE, expected 8" }
                # A token ack is not an ack -- same floor --no-requirement already uses.
                python $bw --slug t --area test --branch main --accept-cmd 'pwsh x.ps1' `
                    --accept-match 'OK' --requirement 'ship the thing' --text-reviewed 'ok' --out $tmp *> $null
                if ($LASTEXITCODE -ne 8) { throw "accepted a 2-char review ack" }
                # Both flags at once is ambiguous, not permissive.
                python $bw --slug t --area test --branch main --accept-cmd 'pwsh x.ps1' `
                    --accept-match 'OK' --requirement 'ship the thing' `
                    --text-reviewed 'Ping confirmed 2026-09-18' --text-unreviewed 'also this one' --out $tmp *> $null
                if ($LASTEXITCODE -ne 8) { throw "accepted both review flags at once" }
                # The real ack arms, and the answer is recorded for later sessions.
                python $bw --slug t --area test --branch main --accept-cmd 'pwsh x.ps1' `
                    --accept-match 'OK' --requirement 'ship the thing' `
                    --text-reviewed 'Ping confirmed 2026-09-18' --out $tmp *> $null
                if ($LASTEXITCODE -ne 0) { throw "a real ack was refused; exit $LASTEXITCODE" }
                $c = Get-Content $tmp -Raw
                if ($c -notmatch '(?m)^text_review_status:\s*reviewed --') { throw "review status not recorded in the beacon" }
                # The bypass must be visible, not silent.
                python $bw --slug t --area test --branch main --accept-cmd 'pwsh x.ps1' `
                    --accept-match 'OK' --requirement 'ship the thing' `
                    --text-unreviewed 'autonomous run, owner asleep' --out $tmp *> $null
                if ($LASTEXITCODE -ne 0) { throw "documented bypass was refused" }
                if ((Get-Content $tmp -Raw) -notmatch '(?m)^text_review_status:\s*unreviewed --') { throw "bypass not recorded" }
            } finally { Remove-Item $tmp -ErrorAction SilentlyContinue }
        }
    }
    @{
        # F-LEAK-2: getting free text out of a file is an edit; getting it out of a
        # commit message is a history rewrite that propagates to every mirror.
        Name = 'abort_reason_not_in_commit_message: abort msg is templated'
        Run  = {
            $adv = Get-Content (Join-Path $SkillDir '../personal-goal-next/lib/advance.py') -Raw
            if ($adv -match 'ABORT -- \{args\.abort\}') {
                throw "the abort reason is still interpolated into the git commit message"
            }
            if ($adv -notmatch 'see beacon Failure Log') { throw "templated abort message missing" }
        }
    }
    @{
        # F-BEACON-1: git add on a path under an ignore rule exits 1 EVEN WHEN the file
        # is tracked and even when it stages successfully, so check=True raised on a
        # command that had worked and the commit never ran. A beacon could be silently
        # left uncommitted for a whole goal -- the crash-recovery anchor not recovering.
        Name = 'beacon_staging_survives_ignore_rules: git add -f is used for the beacon'
        Run  = {
            foreach ($f in @('advance.py', 'finalize.py')) {
                $src = Get-Content (Join-Path $SkillDir "../personal-goal-next/lib/$f") -Raw
                if ($src -match '"git",\s*"add",\s*str\(bp\)') {
                    throw "$f still stages the beacon with a plain git add; it exits 1 under an ignore rule"
                }
                if ($src -notmatch '_git_add_beacon\(bp\)') { throw "$f does not use the beacon staging helper" }
            }
            $adv = Get-Content (Join-Path $SkillDir '../personal-goal-next/lib/advance.py') -Raw
            if ($adv -notmatch '"git",\s*"add",\s*"-f",\s*str\(bp\)') { throw "the helper does not force-add" }
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
