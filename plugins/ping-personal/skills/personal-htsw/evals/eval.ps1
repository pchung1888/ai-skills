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
        Name = 'text_layout_rules: flows run top to bottom with no box drawing; a paragraph holds 3 sentences at most (DEC-1)'
        Run = {
            $s = Get-Content $Skill -Raw; $w = Get-Content (Join-Path $Refs 'walk.md') -Raw; $n = Get-Content (Join-Path $Refs 'now.md') -Raw
            if ($s -notmatch 'one box per line, arrows down') { throw "SKILL.md Diagram syntax lost the top-to-bottom rule" }
            if ($s -notmatch 'A paragraph holds 3 sentences at most') { throw "SKILL.md restraint rules lost the 3-sentence block rule" }
            if ($n -notmatch 'Never two boxes on one line') { throw "now.md flowchart rule lost 'Never two boxes on one line'" }
            foreach ($doc in @(@('SKILL.md', $s, '## Diagram syntax'), @('walk.md', $w, 'Example (ASCII flow):'))) {
                $i = $doc[1].IndexOf($doc[2]); if ($i -lt 0) { throw "$($doc[0]): '$($doc[2])' not found" }
                $ex = [regex]::Match($doc[1].Substring($i), '(?s)```\r?\n(.*?)```').Groups[1].Value
                if ($ex -match '[─-╿▶-▼]') { throw "$($doc[0]) flow example uses Unicode box drawing" }
                if ($ex -notmatch '(?m)^\s*v\s*$') { throw "$($doc[0]) flow example is not top to bottom (no 'v' line)" }
            }
        }
    },
    @{
        Name = 'deep_uses_plan_blocks: now.md Deep HTML asks for interactive: true and the flow / code-pins / note / ask blocks'
        Run = {
            $n = Get-Content (Join-Path $Refs 'now.md') -Raw
            foreach ($k in @('interactive: true','`flow` block','`code-pins` block','`note` block','`ask` block','never a text flowchart',
                             '**You asked:**', '```note warn', '- [x] The recommended option', 'the pane does not send md-to-html''s own docs')) {
                if ($n -notmatch [regex]::Escape($k)) { throw "now.md Deep HTML section missing: $k" }
            }
            $h = Get-Content (Join-Path $SkillDir '../../hooks/hud-explain.ts') -Raw
            if ($h -notmatch "key: 'deep'[^\n]*interactive: true[^\n]*flow block") { throw "hud-explain.ts Deep button prompt does not ask for interactive: true and a flow block" }
        }
    },
    @{
        Name = 'checker_now_cantonese: --purpose now accepts Chinese text with ASCII punctuation (fixtures/now-good-cantonese.md)'
        Run = {
            python $Checker --purpose now --input-file (Join-Path $Fix 'now-good-cantonese.md') *> $null
            if ($LASTEXITCODE -ne 0) { throw "checker rejected a Cantonese now rendering (exit $LASTEXITCODE)" }
        }
    },
    @{
        Name = 'explaining_sentences_documented: SKILL.md has the Explaining sentences section with its six rules'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?m)^## Explaining sentences') { throw "SKILL.md has no '## Explaining sentences' section" }
            foreach ($k in @('Say who does what', 'One idea per sentence', 'Name the term, then say right away what it does', 'Say why it matters', 'Never point at something the reader was not shown', 'plain words must still say what changed')) {
                if ($s -notmatch [regex]::Escape($k)) { throw "Explaining sentences rule missing: $k" }
            }
        }
    },
    @{
        Name = 'personas_carry_explaining_rules: every persona agent except next-recommender has the six Explaining-sentences rules'
        Run = {
            $agents = Join-Path $PSScriptRoot '../../../agents'
            $rules = @('Say who does what', 'One idea per sentence', 'Name the term, then say right away what it does', 'Say why it matters', 'Never point at something the reader was not shown', 'plain words must still say what changed')
            $files = Get-ChildItem (Join-Path $agents '*.md') | Where-Object { $_.BaseName -ne 'next-recommender' }
            if ($files.Count -lt 8) { throw "expected 8 persona agents, found $($files.Count)" }
            foreach ($f in $files) {
                $t = Get-Content $f.FullName -Raw -Encoding utf8
                if ($t -notmatch [regex]::Escape('**Explaining sentences** (personal-htsw SKILL.md)')) { throw "$($f.Name) has no Explaining sentences line" }
                foreach ($k in $rules) { if ($t -notmatch [regex]::Escape($k)) { throw "$($f.Name) is missing rule: $k" } }
            }
        }
    },
    @{
        Name = 'cantonese_switch_documented: SKILL.md documents --cantonese; now.md allows Chinese text with it'
        Run = {
            $s = Get-Content $Skill -Raw; $n = Get-Content (Join-Path $Refs 'now.md') -Raw
            if ($s -notmatch '(?m)^## Language switch -- --cantonese') { throw "SKILL.md has no '## Language switch -- --cantonese' section" }
            foreach ($k in @('/personal-htsw walk --cantonese', 'technical terms stay in English', 'Punctuation stays ASCII')) {
                if ($s -notmatch [regex]::Escape($k)) { throw "Language switch section missing: $k" }
            }
            if ($n -notmatch [regex]::Escape('Chinese text is allowed with')) { throw "now.md still says ASCII only with no Chinese carve-out" }
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
