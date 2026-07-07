#requires -Version 7
$ErrorActionPreference = 'Stop'
# FIX-1: tests/ is 5 levels below repo root:
# tests -> personal-workflow -> skills -> ping-personal -> plugins -> <repo root>
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot '..\..\..\..\..')
Set-Location $RepoRoot
$env:PYTHONIOENCODING = 'utf-8'   # guard the cp1252 console crash (CLAUDE.md Windows pitfall)
$Lib = 'plugins/ping-personal/skills/personal-workflow/lib'
$Fix = 'plugins/ping-personal/skills/personal-workflow/tests/fixtures'

$tests = @(
    @{
        Name = 'discover: emits project rows; block-scalar indicator stripped + folded to one line'
        Run = {
            $json = python "$Lib/discover.py" --skills-dir "$Fix/skills-sample" --agents-dir "$Fix/agents-sample" 2>&1
            if ($LASTEXITCODE -ne 0) { throw "discover.py failed: $json" }
            $map = $json | ConvertFrom-Json
            if ($map.source -ne 'filesystem') { throw "source should be filesystem" }
            $alpha = $map.rows | Where-Object { $_.name -eq 'alpha-skill' }
            if (-not $alpha) { throw "alpha-skill missing" }
            if ($alpha.confidence -ne 'high') { throw "alpha should be high confidence (desc present on disk)" }
            if ($alpha.description -notmatch 'stored procedures') { throw "alpha desc not read from file" }
            if ($alpha.description -match '^[>|]') { throw "block-scalar indicator leaked into description" }
            if ($alpha.description -match "`n") { throw "description not folded to a single line" }
            $beta = $map.rows | Where-Object { $_.name -eq 'beta-agent' }
            if ($beta.kind -ne 'agent' -or $beta.invoke -ne 'Agent') { throw "beta-agent not classified as agent" }
        }
    },
    @{
        Name = 'discover: empty on-disk description triggers body-fallback + low confidence'
        Run = {
            $json = python "$Lib/discover.py" --skills-dir "$Fix/skills-sample" --agents-dir "$Fix/agents-sample" 2>&1
            if ($LASTEXITCODE -ne 0) { throw "discover.py failed: $json" }
            $map = $json | ConvertFrom-Json
            $blank = $map.rows | Where-Object { $_.name -eq 'blank-skill' }
            if (-not $blank) { throw "blank-skill row missing" }
            if ($blank.confidence -ne 'low') { throw "blank-skill should be low confidence" }
            if ($blank.description -notmatch 'regression') { throw "body-fallback did not read the heading/paragraph" }
        }
    },
    @{
        Name = 'fence: destructive SQL + git pause-always (exit 2)'
        Run = {
            $cases = @(
                'DROP TABLE Users',
                'DELETE FROM Orders',                  # no WHERE
                'UPDATE Account SET active = 0',       # no WHERE
                'git push --force origin main',
                'git push origin main',                # any push pauses (over-pause, never under)
                'git reset --hard HEAD~3',
                'git branch -D feature/x',
                'iisreset /restart'
            )
            foreach ($c in $cases) {
                python "$Lib/fence.py" --action "$c" *> $null
                if ($LASTEXITCODE -ne 2) { throw "expected PAUSE-ALWAYS (2) for: $c (got $LASTEXITCODE)" }
            }
        }
    },
    @{
        Name = 'fence: sensitive paths pause-always (exit 2)'
        Run = {
            foreach ($c in @('modify .claude/settings.local.json', 'touch .gitignore',
                             'write .env.production', 'rewrite package-lock.json', 'edit dist/bundle.js')) {
                python "$Lib/fence.py" --action "$c" *> $null
                if ($LASTEXITCODE -ne 2) { throw "expected 2 for path: $c (got $LASTEXITCODE)" }
            }
        }
    },
    @{
        Name = 'fence: Restart-WebAppPool is pause-ack-once (exit 3); safe action allows (exit 0)'
        Run = {
            python "$Lib/fence.py" --action 'Restart-WebAppPool -Name App2' *> $null
            if ($LASTEXITCODE -ne 3) { throw "expected PAUSE-ACK-ONCE (3), got $LASTEXITCODE" }
            python "$Lib/fence.py" --action 'git commit -m "feat: x"' *> $null
            if ($LASTEXITCODE -ne 0) { throw "expected ALLOW (0) for safe commit, got $LASTEXITCODE" }
            python "$Lib/fence.py" --action 'DELETE FROM Orders WHERE Id = 5' *> $null
            if ($LASTEXITCODE -ne 0) { throw "DELETE with WHERE should ALLOW (0), got $LASTEXITCODE" }
        }
    },
    @{
        Name = 'SKILL.md has roles block + the 5 loop steps + two-source discovery + re-pointed delegates'
        Run = {
            $s = Get-Content 'plugins/ping-personal/skills/personal-workflow/SKILL.md' -Raw
            foreach ($needle in @('BEACON', 'BRAINSTORM', 'RESEARCHER', 'IMPLEMENTER', 'CRITIC',
                                  'ROUTE', 'MODE', 'FENCE', 'VERIFY', 'RECORD',
                                  'discover.py', 'fence.py', 'model folds in',
                                  'personal-goal', 'personal-critic-gate', 'iris', 'bunny')) {
                if ($s -notmatch [regex]::Escape($needle)) { throw "SKILL.md missing: $needle" }
            }
            # FIX-3 guard: no version-pinned plugin cache path baked in
            if ($s -match '0\.4\.0') { throw "SKILL.md hardcodes a version-pinned cache path (FIX-3 violation)" }
        }
    },
    @{
        Name = 'beacon reuse: personal-goal plan_parser reads the dry-run fixture (FIX-2 path)'
        Run = {
            $pp = 'plugins/ping-personal/skills/personal-goal/lib/plan_parser.py'
            # -join: native output is an ARRAY of lines; fold to one string so -match is boolean, not a filter
            $rows = (python $pp "$Fix/plan-2-phases.md" 2>&1) -join "`n"
            if ($LASTEXITCODE -ne 0) { throw "plan_parser failed: $rows" }
            if ($rows -notmatch 'Author three reference notes') { throw "phase 1 not parsed" }
            if ($rows -notmatch 'Deploy the notes') { throw "phase 2 not parsed" }
        }
    },
    @{
        Name = 'fence: recursive-delete + git clean long-form pause-always (gate finding H1)'
        Run = {
            foreach ($c in @('rm -rf ./src', 'Remove-Item -Recurse -Force .\plugins',
                             'git clean -fd', 'git clean --force')) {
                python "$Lib/fence.py" --action "$c" *> $null
                if ($LASTEXITCODE -ne 2) { throw "expected PAUSE-ALWAYS (2) for: $c (got $LASTEXITCODE)" }
            }
        }
    },
    @{
        Name = 'fence: multiline / schema-qualified SQL cannot smuggle WHERE past the no-WHERE guard'
        Run = {
            # WHERE only in a LATER newline-separated statement must NOT excuse the bare DELETE
            python "$Lib/fence.py" --action "DELETE FROM Orders`nGO`nSELECT * FROM X WHERE id=1" *> $null
            if ($LASTEXITCODE -ne 2) { throw "multiline DELETE smuggled a later WHERE (got $LASTEXITCODE)" }
            # schema-qualified + bracketed UPDATE targets without WHERE must PAUSE
            python "$Lib/fence.py" --action 'UPDATE dbo.Account SET active = 0' *> $null
            if ($LASTEXITCODE -ne 2) { throw "schema-qualified UPDATE bypassed (got $LASTEXITCODE)" }
            python "$Lib/fence.py" --action 'UPDATE [Account] SET active = 0' *> $null
            if ($LASTEXITCODE -ne 2) { throw "bracketed UPDATE bypassed (got $LASTEXITCODE)" }
            # same-line WHERE still correctly ALLOWS (no over-pause regression)
            python "$Lib/fence.py" --action 'UPDATE dbo.Account SET active = 0 WHERE id = 5' *> $null
            if ($LASTEXITCODE -ne 0) { throw "UPDATE with same-line WHERE should ALLOW (got $LASTEXITCODE)" }
        }
    },
    @{
        Name = 'routing.md referenced ping-personal agents exist on disk (gate finding M2)'
        Run = {
            $r = Get-Content 'plugins/ping-personal/skills/personal-workflow/references/routing.md' -Raw
            foreach ($a in @('iris','bunny','ms-mario','vex','dora','maggie')) {
                if ($r -match [regex]::Escape($a)) {
                    if (-not (Test-Path "plugins/ping-personal/agents/$a.md")) {
                        throw "routing.md cites '$a' but plugins/ping-personal/agents/$a.md is missing"
                    }
                }
            }
        }
    }
)

# final-block shape matches personal-goal convention ($pass/$fail counters + explicit exit codes)
$pass = 0; $fail = 0
foreach ($t in $tests) {
    try { & $t.Run; $pass++; Write-Host "PASS $($t.Name)" -ForegroundColor Green }
    catch { $fail++; Write-Host "FAIL $($t.Name): $_" -ForegroundColor Red }
}
if ($fail -eq 0) { Write-Host "SMOKE PASS ($pass)" -ForegroundColor Green; exit 0 }
else { Write-Host "SMOKE FAIL ($fail of $($pass+$fail))" -ForegroundColor Red; exit 1 }
