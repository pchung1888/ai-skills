#requires -Version 7
# Eval grader for personal-verify-builder. See evals/eval-plan.md for the failure-mode map.
# Deterministic red/green grader. Exit 0 = all checks pass; exit 1 = at least one fails.
$ErrorActionPreference = 'Stop'

$SkillDir = Resolve-Path (Join-Path $PSScriptRoot '..')
$Skill    = Join-Path $SkillDir 'SKILL.md'
$Template = Join-Path $SkillDir 'references\verify-template.md'
$Layers   = Join-Path $SkillDir 'references\check-layers.md'
$Fixture  = Join-Path $PSScriptRoot 'fixtures\tiny-ledger'
$Notices  = Join-Path $SkillDir '..\..\THIRD-PARTY-NOTICES.md'

# The planted bug tier 2 uses. Kept here so fixture_oracle and run-fixture.ps1 agree.
$BugFrom = "WHERE status = 'open'"
$BugTo   = 'WHERE 1 = 1'

function Assert-Has([string]$file, [string[]]$keys) {
    $text = Get-Content $file -Raw
    foreach ($k in $keys) { if ($text -cnotmatch [regex]::Escape($k)) { throw "$(Split-Path $file -Leaf) lost: $k" } }
}

$tests = @(
    @{
        Name = 'skill_frontmatter: name, description, ASCII in every skill file'
        Run = {
            $fm = [regex]::Match((Get-Content $Skill -Raw), '\A---\r?\n(?<fm>.*?)\r?\n---\r?\n', 'Singleline')
            if (-not $fm.Success) { throw 'SKILL.md has no leading --- frontmatter block' }
            $s = $fm.Groups['fm'].Value
            if ($s -cnotmatch '(?m)^name:\s*personal-verify-builder\s*$') { throw 'frontmatter name wrong' }
            if ($s -cnotmatch '(?m)^description:\s*Use when\b') { throw 'description must start with "Use when"' }
            if ($s -match '(?m)^disable-model-invocation:') { throw 'builder must stay model-invocable' }
            foreach ($f in Get-ChildItem $SkillDir -Recurse -File | Where-Object { $_.Extension -ne '.db' }) {
                $bad = @([System.IO.File]::ReadAllBytes($f.FullName) | Where-Object { $_ -gt 127 }).Count
                if ($bad) { throw "$bad non-ASCII bytes in $($f.Name)" }
            }
        }
    },
    @{
        Name = 'four_modes: create, maintain, rate, improve'
        Run = { Assert-Has $Skill @('| `create` |', '| `maintain` |', '| `rate <1-5> <note>` |', '| `improve` |', '## create', '## maintain', '## rate and improve') }
    },
    @{
        Name = 'output_contract: exactly verify, repo root, model-invocable'
        Run = {
            Assert-Has $Skill @('named exactly `verify`', '.claude/skills/verify/SKILL.md', 'no `disable-model-invocation`', '/run-skill-generator')
            $t = Get-Content $Template -Raw
            if ($t -notmatch '(?m)^name: verify\s*$') { throw 'template frontmatter is not "name: verify"' }
            if ($t -match '(?m)^disable-model-invocation:') { throw 'template sets disable-model-invocation' }
        }
    },
    @{
        Name = 'able_to_fail: planted bug, red, revert, green'
        Run = {
            Assert-Has $Skill @('Every check must fail on a planted bug', 'run it red, revert from a backup', 'run it green', 'Do not commit a planted bug', 'it is too weak',
                "that check's own assertion", 'with a wrong expected value')
            Assert-Has $Template @('## Proof it can fail', '| Proof it can fail |', 'import error')
        }
    },
    @{
        Name = 'safe_revert: fresh hashed backup before planting, never checkout unsaved work, good binary restored'
        Run = {
            Assert-Has $Skill @('verify-plant-backup/<repo name>/<its repo-relative path>', 'No saved copy, no plant', 'Delete any old copy at that path', 'git hash-object', 'git status --porcelain -- <file>', 'a file you did not save first',
                "Restore a compiled target's good binary", 'revert from a backup', 'using `create`', 'never revert a planted bug with git')
            Assert-Has $Layers @('restore the good DLL backup and re-register it')
        }
    },
    @{
        Name = 'findings_stay_findings: never weaken, never edit product code'
        Run = {
            Assert-Has $Skill @('Findings stay findings', 'Never weaken a check', 'never change product code unless the user asks', 'Compute expected values from the inputs')
            Assert-Has $Template @('Never weaken the check')
        }
    },
    @{
        Name = 'shared_read_only: QA, DEV, client servers get doctor only'
        Run = {
            Assert-Has $Skill @('Shared servers stay read-only', 'only on the local box or a copy', 'stop only those')
            Assert-Has $Layers @('QA, DEV and client servers get')
            Assert-Has $Template @('## Safety', 'QA, DEV and client servers get Doctor and read-only checks only', 'If Doctor cannot show the', 'broken prerequisite')
        }
    },
    @{
        Name = 'touched_only: touched features before commit, all on request'
        Run = {
            Assert-Has $Skill @('Touched features only before a commit', '`/verify all`')
            Assert-Has $Template @('git diff --name-only HEAD', 'git ls-files --others --exclude-standard', '`/verify <feature>`', '`/verify all`')
        }
    },
    @{
        Name = 'template_sections: every section of the generated skill'
        Run = {
            Assert-Has $Template @('## Pick what to run', '## Launch', '## Doctor', '## Run all checks', '## Features',
                '## Reading a failure', '## Evidence', '## Coverage and sync', '## Not covered', '## Test oracle',
                '## Formal candidate', '.claude/verify-evidence/', '| Synced at |', 'one line, run from the repo root')
            Assert-Has $Skill @('already exists, stop', 'One single-line command')
        }
    },
    @{
        Name = 'maintain_outcomes: in sync, updated, bug, blocked'
        Run = { Assert-Has $Skill @('**in sync**', '**updated**', '**bug**', '**blocked**', 'never from the result', '"Synced at" commit') }
    },
    @{
        Name = 'retro_loop: rate log outside repos, improve waits for the user'
        Run = { Assert-Has $Skill @('~/.claude/verify-builder-retros.md', 'change nothing until the user picks', 'at least three rows') }
    },
    @{
        Name = 'fixture_oracle: fixture totals right, planted bug changes them'
        Run = {
            $q = Get-Content (Join-Path $Fixture 'queries.py') -Raw
            if ($q -notmatch [regex]::Escape($BugFrom)) { throw "queries.py lost the bug site: $BugFrom" }
            $py = @'
import importlib.util, os, sqlite3, sys
sys.dont_write_bytecode = True  # a __pycache__ in the fixture would fail the ASCII grader
d = sys.argv[1]
sys.path.insert(0, d)
seed = importlib.util.spec_from_file_location('seed', os.path.join(d, 'seed.py'))
m = importlib.util.module_from_spec(seed); seed.loader.exec_module(m)
con = sqlite3.connect(':memory:')
con.execute('CREATE TABLE trades (id INTEGER PRIMARY KEY, symbol TEXT, qty INTEGER, price REAL, status TEXT)')
con.executemany('INSERT INTO trades (symbol, qty, price, status) VALUES (?, ?, ?, ?)', m.TRADES)
import queries
good = queries.positions(con)
bad = con.execute(queries.POSITIONS_SQL.replace(sys.argv[2], sys.argv[3])).fetchall()
assert good == [('AAPL', 60, 11341.0), ('MSFT', 50, 20527.5), ('TSLA', 10, 2503.33)], good
assert bad != good, 'planted bug does not change the output'
print('ok')
'@
            $out = ($py | python -I - $Fixture $BugFrom $BugTo 2>&1 | Out-String).Trim()
            if ($LASTEXITCODE -ne 0 -or $out -ne 'ok') { throw "fixture oracle failed: $out" }
            $rf = Get-Content (Join-Path $PSScriptRoot 'run-fixture.ps1') -Raw
            if (-not $rf.Contains($BugTo)) { throw 'run-fixture.ps1 does not plant the same SQL bug' }
            $AppBug = 'sum(r[2] for r in rows)'
            if (-not (Get-Content (Join-Path $Fixture 'app.py') -Raw).Contains($AppBug)) { throw "app.py lost the page-total bug site: $AppBug" }
            if (-not $rf.Contains($AppBug)) { throw 'run-fixture.ps1 does not plant the page-total bug' }
            foreach ($k in 'GROUP BY symbol -- neutral edit', "'^-?\d+$'", 'Stop-OwnedListeners', 'git rev-list --count',
                'skill-copy', 'taskkill /T /F', '$PreexistingPids') {
                if (-not $rf.Contains($k)) { throw "run-fixture.ps1 lost: $k" }
            }
        }
    },
    @{
        Name = 'notice: pstack MIT notice present'
        Run = { Assert-Has $Notices @('personal-verify-builder', 'Copyright (c) 2026 Lauren Tan') }
    }
)

$pass = 0; $fail = 0
foreach ($t in $tests) {
    try { & $t.Run; $pass++; Write-Host "PASS $($t.Name)" -ForegroundColor Green }
    catch { $fail++; Write-Host "FAIL $($t.Name): $_" -ForegroundColor Red }
}
if ($fail -eq 0) { Write-Host "EVAL PASS personal-verify-builder ($pass)" -ForegroundColor Green; exit 0 }
else { Write-Host "EVAL FAIL personal-verify-builder ($fail of $($pass+$fail))" -ForegroundColor Red; exit 1 }
