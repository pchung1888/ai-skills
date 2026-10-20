#requires -Version 7
# Eval grader for personal-big-project. See evals/eval-plan.md for the failure-mode map.
# Deterministic red/green grader. Exit 0 = all checks pass; exit 1 = at least one fails.
# Runnable standalone OR from plugins/ping-personal/evals/run-all.ps1 (auto-discovered by glob).
# Needs python and node on PATH. ASCII only (Windows PowerShell 5.1 cp1252 pitfall).
$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'   # cp1252 console guard

$SkillDir = Resolve-Path (Join-Path $PSScriptRoot '..')   # personal-big-project/
$Skill    = Join-Path $SkillDir 'SKILL.md'
# The check_run fixture needs a real git repo with a local bare remote, which cannot live in the
# plugin repo, so materialize.py builds a fresh copy in a temp folder for each eval run.
$FixSrc   = Join-Path $PSScriptRoot 'fixtures'
$Fix      = Join-Path ([IO.Path]::GetTempPath()) ("bp-fix-" + [guid]::NewGuid())
python (Join-Path $FixSrc 'materialize.py') $Fix | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'materialize.py failed' }
$Scripts  = Join-Path $SkillDir 'scripts'
$Agents   = Join-Path $SkillDir '../../agents'

# Rules that must stay in SKILL.md. Shared by the real check and its calibration mutation.
$Invariants = @(
    'model: inherit',                        # coordinator runs at the user's session tier, never pinned down
    'disable-model-invocation: true',        # starts unattended work: only the user may start it
    'It must be Opus',                       # coordinator model gate
    'Ask only while the user is present',        # questions at the door, never after
    'Pass comes only from the done command', # no trust in agent claims
    'never re-taken from new code',          # baseline immutability
    'Side effects have hard caps',
    'explicit asks are inputs',              # owner asks are not renegotiated
    '## Fix, defer or stop',                 # fix what can be fixed, hand back the rest
    'is never deferred: that is a regression',
    'AGENT-DEFERRED',
    '## When the run is done',
    'no new item has passed across 2 stage attempts',  # no-progress stop
    'only repeat "done"',                    # self-termination
    'check_run.py',                          # final gate runs the run-state checker
    'context at 70% returns HANDOFF',        # context is a handoff, never a stop
    'run_state.py next',                     # next action comes from tested code, not memory
    'log/decisions.md',                      # every coordinator decision is logged
    '## Which agent for which job',          # coordinator picks any fitting agent
    'ping-personal:dora',                    # git work has an owner with a shell
    'verifier agent that did not do the',    # pass is never the worker's own claim
    'GOAL-BRIEF.md',                         # alignment interview ends in an approved brief
    'Corrections before approval',           # alignment metric read by retro_metrics.py
    'skill-friction.md',                     # every workaround of the skill is logged
    'retro_metrics.py',                      # retro starts from measured numbers
    'big-project-retros',                    # retros collect outside every repo for improve mode
    'baseCommit',                            # one fixed point for regressions, review and checks
    '`estimateK`',                           # every task sized to one fresh context
    '`stageCheck`',                          # full done command once per stage, not per task
    'finalReview: true',                     # two-axis final review, never merged
    'Transcript sample for the retro',       # retro reads raw transcripts, not only self-reports
    'references/glossary.md',                # one vocabulary for owner and agents
    'interview them in rounds'                # dependency-graph rounds with recommended answers
)
function Get-Missing([string]$text) {
    @($Invariants | Where-Object { -not $text.Contains($_) })
}
function Invoke-CheckRun([string]$state, [string]$transcript) {
    $out = (python (Join-Path $Scripts 'check_run.py') --state-dir $state --transcript $transcript 2>&1) -join "`n"
    @{ Code = $LASTEXITCODE; Out = $out }
}

$tests = @(
    @{
        Name = 'skill_rules: SKILL.md keeps every invariant (name, model, gates, done rules)'
        Run = {
            $s = (Get-Content $Skill -Raw) -replace "`r`n", "`n"
            if ($s -notmatch '(?m)^name:\s*personal-big-project\s*$') { throw 'frontmatter name not personal-big-project' }
            $m = Get-Missing $s
            if ($m) { throw "SKILL.md lost: $($m -join ' | ')" }
            # Calibration: removing one invariant must be detected.
            $mutant = $s.Replace('## When the run is done', '## Wrapping up')
            if (-not (Get-Missing $mutant)) { throw 'calibration: a removed invariant went unnoticed' }
        }
    },
    @{
        Name = 'referential_integrity: every file and agent the skill names exists'
        Run = {
            $text = (Get-ChildItem $SkillDir -Recurse -File -Include *.md, *.js, *.py, *.ps1 |
                Where-Object { $_.FullName -notmatch '\\(evals|fixtures)\\' } | Get-Content -Raw) -join "`n"
            $paths = [regex]::Matches($text, '(?<![\w/])(references|scripts)/[\w.-]+\.(md|js|py|ps1)') |
                ForEach-Object Value | Sort-Object -Unique
            $gone = @($paths | Where-Object { -not (Test-Path (Join-Path $SkillDir $_)) })
            $agents = [regex]::Matches($text, 'ping-personal:([a-z-]+)') | ForEach-Object { $_.Groups[1].Value } | Sort-Object -Unique
            $gone += @($agents | Where-Object { -not (Test-Path (Join-Path $Agents "$_.md")) } | ForEach-Object { "agent $_" })
            if ($gone) { throw "named but missing: $($gone -join ', ')" }
            if ($paths.Count -lt 5) { throw "only $($paths.Count) file references found; the extractor is broken" }
        }
    },
    @{
        Name = 'build_table: rebuilds the real run''s table from trimmed journals'
        Run = {
            $out = (python (Join-Path $PSScriptRoot 'test_build_table.py') 2>&1) -join "`n"
            if ($LASTEXITCODE -ne 0 -or $out -notmatch 'BUILD TABLE TEST PASS') { throw $out }
        }
    },
    @{
        Name = 'generate: tick and stage scripts filled, escaped, valid JS, bad specs refused'
        Run = {
            $out = (python (Join-Path $PSScriptRoot 'test_generate.py') 2>&1) -join "`n"
            if ($LASTEXITCODE -ne 0 -or $out -notmatch 'GENERATE TEST PASS') { throw $out }
        }
    },
    @{
        Name = 'python self-tests: run_state transitions, check_run fail-closed, retro_metrics parsing'
        Run = {
            foreach ($t in @(@('test_run_state.py', 'RUN STATE TEST PASS'), @('test_check_run.py', 'CHECK RUN TEST PASS'), @('test_retro_metrics.py', 'RETRO METRICS TEST PASS'))) {
                $out = (python (Join-Path $PSScriptRoot $t[0]) 2>&1) -join "`n"
                if ($LASTEXITCODE -ne 0 -or $out -notmatch [regex]::Escape($t[1])) { throw "$($t[0]):`n$out" }
            }
        }
    },
    @{
        Name = 'check_run calibration: good run passes AND each broken rule fails by name'
        Run = {
            $good = Join-Path $Fix 'good-run/repo/autopilot'
            $tr = Join-Path $Fix 'transcript.jsonl'
            $r = Invoke-CheckRun $good $tr
            if ($r.Code -ne 0) { throw "good run did not pass:`n$($r.Out)" }
            # Each break: a file edit inside a temp copy, and the check that must catch it.
            $breaks = @(
                @{ Check = 'log-times';    File = 'log/run-log.md';      Append = "| 2026-10-17 evening | T2 | estimated time | - |`n" },
                @{ Check = 'report-plain'; File = 'reports/2026-10-16-2130.md'; Append = "Task T2 passed, commit 4b8d3b26.`n" },
                @{ Check = 'table-rows';   File = 'tasks.csv';           Append = "T3,Build,new task never shown,,`n" },
                @{ Check = 'side-effects'; File = 'log/side-effects.md'; Append = "| Sat 10-17 01:00 | mail | 38 | rerun |`n" },
                @{ Check = 'baselines';    File = '../baseline/expected.txt'; Append = "re-taken from new code`n" },
                @{ Check = 'verdict';      File = 'OWNER-REPORT.md';     Replace = @('1 deferred, 1 by agents', '1 deferred') },
                @{ Check = 'owner-report'; File = 'OWNER-REPORT.md';     Replace = @('## Merge danger', '## Danger') },
                @{ Check = 'no-questions'; File = '../../../transcript.jsonl'; Append = '{"type":"assistant","timestamp":"2026-10-17T03:00:00.000Z","message":{"content":[{"type":"tool_use","name":"AskUserQuestion"}]}}' + "`n" }
            )
            foreach ($b in $breaks) {
                $tmp = Join-Path ([IO.Path]::GetTempPath()) ("bp-eval-" + [guid]::NewGuid())
                Copy-Item $Fix $tmp -Recurse
                try {
                    $f = Join-Path $tmp "good-run/repo/autopilot/$($b.File)"
                    if ($b.Replace) { (Get-Content $f -Raw).Replace($b.Replace[0], $b.Replace[1]) | Set-Content $f -NoNewline }
                    else { Add-Content $f $b.Append -NoNewline }
                    $r = Invoke-CheckRun (Join-Path $tmp 'good-run/repo/autopilot') (Join-Path $tmp 'transcript.jsonl')
                    if ($r.Code -eq 0 -or $r.Out -notmatch "FAIL $($b.Check):") { throw "break of $($b.Check) was not caught:`n$($r.Out)" }
                } finally { Remove-Item $tmp -Recurse -Force }
            }
        }
    },
    @{
        Name = 'retro_metrics: real-run journals give the known numbers; a late question is counted'
        Run = {
            $state = Join-Path $Fix 'good-run/repo/autopilot'
            $args3 = @('--state-dir', $state, '--journals', (Join-Path $Fix 'journals'))
            $out = (python (Join-Path $Scripts 'retro_metrics.py') @args3 --transcript (Join-Path $Fix 'transcript.jsonl') 2>&1) -join "`n"
            if ($LASTEXITCODE -ne 0) { throw $out }
            # Known values: the 37-hour run (5 stages, 57 agents, 8,888,029 tokens) plus the good-run fixture.
            $want = @('| Stages (workflows) | 5 |', '| Workflow agents | 57 |', '| Workflow tokens | 8,888,029 |',
                '15.5 h', '| Ticks (quota-log rows) / pauses | 3 / 1 |', '| 5h window peak | 91% |',
                '| Skill friction rows (workarounds) | 1 |', '| Goal-brief corrections at the door | 2 |',
                '| Owner messages while unattended | 1 |', '| Questions asked while unattended | 0 |')
            $miss = @($want | Where-Object { -not $out.Contains($_) })
            if ($miss) { throw "retro metrics missing: $($miss -join ' ; ')`n$out" }
            # Calibration: one AskUserQuestion after unattendedSince must move the count to 1.
            $tmp = Join-Path ([IO.Path]::GetTempPath()) ("bp-retro-" + [guid]::NewGuid() + '.jsonl')
            Copy-Item (Join-Path $Fix 'transcript.jsonl') $tmp
            Add-Content $tmp '{"type":"assistant","timestamp":"2026-10-17T03:00:00.000Z","message":{"content":[{"type":"tool_use","name":"AskUserQuestion"}]}}'
            try {
                $out = (python (Join-Path $Scripts 'retro_metrics.py') @args3 --transcript $tmp 2>&1) -join "`n"
                if (-not $out.Contains('| Questions asked while unattended | 1 |')) { throw "late question not counted:`n$out" }
            } finally { Remove-Item $tmp -Force }
        }
    },
    @{
        Name = 'preflight calibration: good inputs all PASS, bad inputs fail every scripted check'
        Run = {
            $tmp = Join-Path ([IO.Path]::GetTempPath()) ("bp-pf-" + [guid]::NewGuid())
            New-Item -ItemType Directory "$tmp/state/log", "$tmp/usage" -Force | Out-Null
            'STATUS.md', 'log/run-log.md', 'log/quota-log.md', 'log/side-effects.md', 'log/skill-friction.md' |
                ForEach-Object { New-Item -ItemType File "$tmp/state/$_" | Out-Null }
            $now = [datetimeoffset]::UtcNow.ToString('o')
            @{ writtenAt = $now; model = 'Opus 5.5'; claude = @(@{ window = '7d'; percentUsed = 40 }) } | ConvertTo-Json -Depth 4 | Set-Content "$tmp/usage/good.json"
            @{ writtenAt = $now; model = 'Sonnet 5.5'; claude = @(@{ window = '7d'; percentUsed = 90 }) } | ConvertTo-Json -Depth 4 | Set-Content "$tmp/usage/bad.json"
            $sys = $env:SystemDrive
            try {
                $pf = Join-Path $Scripts 'preflight.ps1'
                $common = @('-RepoPath', $tmp, '-DoneCommand', "Write-Output 'ALL CHECKS: FAIL'", '-LiveUsageDir', "$tmp/usage", '-QuotaPs1', "$tmp/none.ps1")
                $out = (pwsh -NoProfile -File $pf @common -StateDir state -PassLine 'ALL CHECKS: PASS' -Disks $sys -MinGB 0.001 -SessionId good 2>&1) -join "`n"
                if ($LASTEXITCODE -ne 0 -or $out -notmatch 'PREFLIGHT SCRIPTED CHECKS PASS') { throw "good preflight failed:`n$out" }
                $out = (pwsh -NoProfile -File $pf @common -StateDir missing -PassLine 'ALL CHECKS: FAIL' -Disks $sys -MinGB 999999 -SessionId bad 2>&1) -join "`n"
                foreach ($c in 'coordinator-model', 'quota-sensor', 'disk-', 'state-folder', 'done-red') {
                    if ($out -notmatch "FAIL $c") { throw "bad preflight did not fail $c`n$out" }
                }
                if ($LASTEXITCODE -eq 0) { throw 'bad preflight exited 0' }
                # A broken done command (its last line is neither the pass nor the fail line) is not RED proof.
                $broken = @('-RepoPath', $tmp, '-DoneCommand', "Write-Output 'boom: command not found'", '-LiveUsageDir', "$tmp/usage", '-QuotaPs1', "$tmp/none.ps1")
                $out = (pwsh -NoProfile -File $pf @broken -StateDir state -PassLine 'ALL CHECKS: PASS' -Disks $sys -MinGB 0.001 -SessionId good 2>&1) -join "`n"
                if ($out -notmatch 'FAIL done-red') { throw "a broken done command passed done-red:`n$out" }
            } finally { Remove-Item $tmp -Recurse -Force }
        }
    },
    @{
        Name = 'ascii: every skill file is pure ASCII'
        Run = {
            $bad = Get-ChildItem $SkillDir -Recurse -File | Where-Object { $_.FullName -notmatch '__pycache__' } |
                Where-Object { [IO.File]::ReadAllBytes($_.FullName) | Where-Object { $_ -gt 127 } | Select-Object -First 1 }
            if ($bad) { throw "non-ASCII bytes in: $($bad.Name -join ', ')" }
        }
    },
    @{
        Name = 'reviewed_sha_rule: SKILL.md carries the literal Reviewed: <sha>'
        Run = {
            if (-not (Get-Content $Skill -Raw).Contains('Reviewed: <sha>')) { throw 'SKILL.md lost the literal Reviewed: <sha>' }
        }
    }
    ,@{
        Name = 'expect_head_rule: SKILL.md carries the literal tally.py --final --sha <sha> --expect-head'
        Run = {
            if (-not (Get-Content $Skill -Raw).Contains('tally.py --final --sha <sha> --expect-head')) { throw 'SKILL.md lost the --expect-head call' }
        }
    }
    ,@{
        Name = 'fixtures_lf: eval fixtures contain no CR bytes (.gitattributes eol=lf)'
        Run = {
            $bad = Get-ChildItem (Join-Path $PSScriptRoot 'fixtures') -Recurse -File |
                Where-Object { $_.FullName -notmatch '__pycache__' } |
                Where-Object { [IO.File]::ReadAllBytes($_.FullName) -contains 13 }
            if ($bad) { throw "CR bytes in fixtures: $($bad.Name -join ', ')" }
        }
    }
)

$pass = 0; $fail = 0
foreach ($t in $tests) {
    try { & $t.Run; $pass++; Write-Host "PASS $($t.Name)" -ForegroundColor Green }
    catch { $fail++; Write-Host "FAIL $($t.Name): $_" -ForegroundColor Red }
}
Remove-Item $Fix -Recurse -Force -ErrorAction SilentlyContinue
if ($fail -eq 0) { Write-Host "EVAL PASS personal-big-project ($pass)" -ForegroundColor Green; exit 0 }
else { Write-Host "EVAL FAIL personal-big-project ($fail of $($pass+$fail))" -ForegroundColor Red; exit 1 }
