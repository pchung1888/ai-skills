#requires -Version 7
# Eval grader for personal-htsw. See evals/eval-plan.md for the failure-mode map.
# Code-based grader (deterministic). Exit 0 = all checks pass; exit 1 = at least one fails.
# Runnable standalone OR from plugins/ping-personal/evals/run-all.ps1.
$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'   # cp1252 console guard (CLAUDE.md Windows pitfall)

$SkillDir = Resolve-Path (Join-Path $PSScriptRoot '..')          # personal-htsw/
$Checker  = Join-Path $SkillDir 'htsw-check.py'
$Skill    = Join-Path $SkillDir 'SKILL.md'
$Refs     = Join-Path $SkillDir 'references'
$Fix      = Join-Path $PSScriptRoot 'fixtures'

# Run htsw-check.py on a fixture; return its exit code (no output).
function Invoke-Checker([string]$file) {
    python $Checker --input-file $file *> $null
    return $LASTEXITCODE
}

$tests = @(
    @{
        Name = 'skill_frontmatter: SKILL.md declares name=personal-htsw + a description'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?m)^name:\s*personal-htsw\s*$') { throw "frontmatter name not personal-htsw" }
            if ($s -notmatch '(?m)^description:\s*\S') { throw "frontmatter description missing" }
        }
    },
    @{
        Name = 'seven_modes_documented: walk / pr / qa / boss / baby / code-explain / now all named in SKILL.md'
        Run = {
            $s = Get-Content $Skill -Raw
            foreach ($m in @('walk','pr','qa','boss','baby','code-explain','now')) {
                if ($s -notmatch [regex]::Escape("``$m``")) { throw "mode '$m' not documented (no backtick mention)" }
            }
        }
    },
    @{
        Name = 'reference_playbooks_present: references/{walk,pr,qa,boss,baby,code-explain,now}.md all exist'
        Run = {
            foreach ($m in @('walk','pr','qa','boss','baby','code-explain','now')) {
                $p = Join-Path $Refs "$m.md"
                if (-not (Test-Path $p)) { throw "missing reference playbook: references/$m.md" }
            }
        }
    },
    @{
        Name = 'now_playbook_present: references/now.md has verdict, flowchart, focus table, why-this-shape, TL;DR'
        Run = {
            $n = Get-Content (Join-Path $Refs 'now.md') -Raw
            foreach ($k in @('Verdict','Flowchart','| When | Your job | Time |','Why this shape','TL;DR')) {
                if ($n -notmatch [regex]::Escape($k)) { throw "now.md missing section: $k" }
            }
        }
    },
    @{
        Name = 'now_chat_only: SKILL.md says now mode writes no files'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?m)^\|\s*`now`.*writes no files') { throw "modes-table row for now does not say it writes no files" }
        }
    },
    @{
        Name = 'deep_html_documented: SKILL.md + now.md document now --deep --html <path> with per-phase tables, glossary, evidence labels, diagrams'
        Run = {
            $s = Get-Content $Skill -Raw; $n = Get-Content (Join-Path $Refs 'now.md') -Raw
            if ($s -notmatch [regex]::Escape('now --deep --html <path>')) { throw "SKILL.md does not document 'now --deep --html <path>'" }
            foreach ($k in @('per-phase table','Glossary','EXTRACTED','INFERRED','diagram')) {
                if ($n -notmatch [regex]::Escape($k)) { throw "now.md deep section missing: $k" }
            }
        }
    },
    @{
        Name = 'deep_writes_md_and_html: now.md says deep writes Markdown next to <path>, renders <path> with md-to-html, prints the link'
        Run = {
            $n = Get-Content (Join-Path $Refs 'now.md') -Raw
            foreach ($k in @('Markdown next to','md-to-html.py','--out <path>','link')) {
                if ($n -notmatch [regex]::Escape($k)) { throw "now.md deep section missing: $k" }
            }
        }
    },
    @{
        Name = 'output_path_not_a_source: source table says the --html path is output, never read, no fail-loud when missing'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?m)^\|\s*`now --deep --html <path>`.*current conversation.*never read as a source') { throw "source-table row for now --deep --html missing or incomplete" }
        }
    },
    @{
        Name = 'now_stays_chat_only: plain now writes no files; --deep --html is the only now carve-out'
        Run = {
            $s = Get-Content $Skill -Raw; $n = Get-Content (Join-Path $Refs 'now.md') -Raw
            if ($s -notmatch '(?m)^\|\s*`now`.*writes no files') { throw "modes-table row for now lost 'writes no files'" }
            if ($n -notmatch 'Without `--deep --html`, now mode writes no files') { throw "now.md does not keep plain now chat-only" }
        }
    },
    @{
        Name = 'checker_present: htsw-check.py exists'
        Run = { if (-not (Test-Path $Checker)) { throw "htsw-check.py missing at $Checker" } }
    },
    @{
        Name = 'checker_accepts_good: htsw-check.py exits 0 on fixtures/good-baby.md (E01)'
        Run = {
            $code = Invoke-Checker (Join-Path $Fix 'good-baby.md')
            if ($code -ne 0) { throw "grader rejected a conforming rendering (exit $code) -- F08 regression" }
        }
    },
    @{
        Name = 'checker_rejects_bad: htsw-check.py exits 1 on every fixtures/bad-*.md (E02,E03)'
        Run = {
            $bad = Get-ChildItem (Join-Path $Fix 'bad-*.md')
            if ($bad.Count -lt 1) { throw "no bad-*.md fixtures found" }
            foreach ($f in $bad) {
                $code = Invoke-Checker $f.FullName
                if ($code -eq 0) { throw "grader ACCEPTED a broken rendering: $($f.Name) -- F08 regression" }
            }
        }
    },
    @{
        Name = 'checker_now_mode: --purpose now accepts fixtures/now-good.md and rejects every fixtures/now-bad-*.md'
        Run = {
            python $Checker --purpose now --input-file (Join-Path $Fix 'now-good.md') *> $null
            if ($LASTEXITCODE -ne 0) { throw "checker rejected a conforming now rendering (exit $LASTEXITCODE)" }
            foreach ($f in Get-ChildItem (Join-Path $Fix 'now-bad-*.md')) {
                python $Checker --purpose now --input-file $f.FullName *> $null
                if ($LASTEXITCODE -eq 0) { throw "checker ACCEPTED a broken now rendering: $($f.Name)" }
            }
        }
    },
    @{
        Name = 'checker_accepts_code_explain_example: htsw-check.py exits 0 on references/examples/code-explain-examples.md'
        Run = {
            $ex = Join-Path $Refs 'examples/code-explain-examples.md'
            if (-not (Test-Path $ex)) { throw "missing code-explain-examples.md" }
            python $Checker --examples-file $ex *> $null
            if ($LASTEXITCODE -ne 0) { throw "checker rejected a conforming code-explain rendering (exit $LASTEXITCODE)" }
        }
    }
)

$pass = 0; $fail = 0
foreach ($t in $tests) {
    try { & $t.Run; $pass++; Write-Host "PASS $($t.Name)" -ForegroundColor Green }
    catch { $fail++; Write-Host "FAIL $($t.Name): $_" -ForegroundColor Red }
}
if ($fail -eq 0) { Write-Host "EVAL PASS personal-htsw ($pass)" -ForegroundColor Green; exit 0 }
else { Write-Host "EVAL FAIL personal-htsw ($fail of $($pass+$fail))" -ForegroundColor Red; exit 1 }
