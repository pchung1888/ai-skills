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

# --- walk engine helpers (walk-build.py / walk-check.py) ---
$WalkDir = Join-Path $SkillDir 'walk'
$WalkSpec = Join-Path $Fix 'walk/phase0.walk.json'

# Make a temp folder holding strangler.svg (svg_file paths resolve against the spec folder). Caller removes it.
function New-WalkTmp {
    $d = Join-Path ([IO.Path]::GetTempPath()) ('walkeval-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory $d | Out-Null
    Copy-Item (Join-Path $Fix 'walk/strangler.svg') $d
    Copy-Item (Join-Path $Fix 'walk/phase0-hero.svg') $d
    return $d
}
# Copy phase0.walk.json into $dir as spec.json, replacing text $from with $to (must occur exactly once). Returns the path.
function Write-WalkSpec([string]$dir, [string]$from = '', [string]$to = '') {
    $raw = [IO.File]::ReadAllText($WalkSpec)
    if ($from) {
        if ([regex]::Matches($raw, [regex]::Escape($from)).Count -ne 1) { throw "patch target not found exactly once in phase0.walk.json: $from" }
        $raw = $raw.Replace($from, $to)
    }
    $p = Join-Path $dir 'spec.json'
    [IO.File]::WriteAllText($p, $raw, [Text.UTF8Encoding]::new($false))
    return $p
}
function Invoke-WalkBuild([string]$spec, [string]$out) {
    $o = (python (Join-Path $WalkDir 'walk-build.py') $spec --out $out 2>&1 | Out-String)
    return [pscustomobject]@{ Code = $LASTEXITCODE; Out = $o }
}
function Invoke-WalkCheck([string]$page, [string]$spec) {
    $o = (python (Join-Path $WalkDir 'walk-check.py') $page --spec $spec 2>&1 | Out-String)
    return [pscustomobject]@{ Code = $LASTEXITCODE; Out = $o }
}
# Build a spec, optionally edit the built HTML with $editHtml (takes and returns the page text), run walk-check,
# and require exit 1 plus a FAIL line for $rule.
function Assert-WalkRuleFails([string]$rule, [string]$from = '', [string]$to = '', [scriptblock]$editHtml = $null) {
    $d = New-WalkTmp
    try {
        $spec = Write-WalkSpec $d $from $to
        $page = Join-Path $d 'page.html'
        $b = Invoke-WalkBuild $spec $page
        if ($b.Code -ne 0) { throw "walk-build failed on the patched spec (exit $($b.Code)): $($b.Out)" }
        if ($editHtml) {
            $h = [IO.File]::ReadAllText($page)
            $h2 = & $editHtml $h
            if ($h2 -ceq $h) { throw "HTML edit changed nothing" }
            [IO.File]::WriteAllText($page, $h2, [Text.UTF8Encoding]::new($false))
        }
        $c = Invoke-WalkCheck $page $spec
        if ($c.Code -ne 1) { throw "walk-check exit $($c.Code), expected 1 for rule $rule" }
        if ($c.Out -notmatch "(?m)^FAIL\s+$([regex]::Escape($rule))\b") { throw "walk-check did not print FAIL for $rule`n$($c.Out)" }
    }
    finally { Remove-Item $d -Recurse -Force -ErrorAction SilentlyContinue }
}
# Build a patched spec and require walk-build to exit non-zero with output matching $pattern.
# Build a patched spec and return the walk-check output line for $rule (idea rules never change the exit code).
function Get-WalkRuleLine([string]$rule, [string]$from = '', [string]$to = '') {
    $d = New-WalkTmp
    try {
        $spec = Write-WalkSpec $d $from $to
        $page = Join-Path $d 'page.html'
        $b = Invoke-WalkBuild $spec $page
        if ($b.Code -ne 0) { throw "walk-build failed on the patched spec (exit $($b.Code)): $($b.Out)" }
        $c = Invoke-WalkCheck $page $spec
        $m = [regex]::Match($c.Out, "(?m)^(PASS|FAIL|MISS)\s+$([regex]::Escape($rule))\b.*$")
        if (-not $m.Success) { throw "walk-check printed no line for $rule`n$($c.Out)" }
        return $m.Value
    }
    finally { Remove-Item $d -Recurse -Force -ErrorAction SilentlyContinue }
}
function Assert-WalkBuildRejects([string]$from, [string]$to, [string]$pattern, [scriptblock]$prep = $null) {
    $d = New-WalkTmp
    try {
        if ($prep) { & $prep $d }
        $spec = Write-WalkSpec $d $from $to
        $b = Invoke-WalkBuild $spec (Join-Path $d 'page.html')
        if ($b.Code -eq 0) { throw "walk-build ACCEPTED a bad spec" }
        if ($b.Out -notmatch $pattern) { throw "walk-build failed for another reason (expected /$pattern/): $($b.Out)" }
        if ($b.Out -match 'Traceback') { throw "walk-build printed a traceback instead of one clear message: $($b.Out)" }
    }
    finally { Remove-Item $d -Recurse -Force -ErrorAction SilentlyContinue }
}

# Build a (possibly patched) phase0 spec and return the built page text. Caller gets text only; temp folder is removed.
function Get-WalkPage([string]$from = '', [string]$to = '') {
    $d = New-WalkTmp
    try {
        $spec = Write-WalkSpec $d $from $to
        $page = Join-Path $d 'page.html'
        $b = Invoke-WalkBuild $spec $page
        if ($b.Code -ne 0) { throw "walk-build failed on the patched spec (exit $($b.Code)): $($b.Out)" }
        return [IO.File]::ReadAllText($page)
    }
    finally { Remove-Item $d -Recurse -Force -ErrorAction SilentlyContinue }
}
# Build the good phase0 spec, edit the built HTML with $editHtml, run walk-check, return the line for $rule.
function Get-WalkRuleLineEdited([string]$rule, [scriptblock]$editHtml) {
    $d = New-WalkTmp
    try {
        $spec = Write-WalkSpec $d
        $page = Join-Path $d 'page.html'
        $b = Invoke-WalkBuild $spec $page
        if ($b.Code -ne 0) { throw "walk-build failed (exit $($b.Code)): $($b.Out)" }
        $h = [IO.File]::ReadAllText($page)
        $h2 = & $editHtml $h
        if ($h2 -ceq $h) { throw "HTML edit changed nothing" }
        [IO.File]::WriteAllText($page, $h2, [Text.UTF8Encoding]::new($false))
        $c = Invoke-WalkCheck $page $spec
        $m = [regex]::Match($c.Out, "(?m)^(PASS|FAIL|MISS)\s+$([regex]::Escape($rule))\b.*$")
        if (-not $m.Success) { throw "walk-check printed no line for $rule`n$($c.Out)" }
        return $m.Value
    }
    finally { Remove-Item $d -Recurse -Force -ErrorAction SilentlyContinue }
}
$WalkJs = Join-Path $WalkDir 'walk.js'
# The hero_visual line of phase0.walk.json; replacing it with '' gives a spec without a hero picture.
$HeroVisualLine = '"hero_visual": {"svg_file": "phase0-hero.svg", "caption": "Every new piece ships switched off until the go decision."},'

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
        Name = 'explaining_sentences_documented: SKILL.md has the Explaining sentences section with its eight rules and the unslop pass'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?m)^## Explaining sentences') { throw "SKILL.md has no '## Explaining sentences' section" }
            foreach ($k in @('Say who does what', 'One idea per sentence', 'Name the term, then say right away what it does', 'Say why it matters', 'Never point at something the reader was not shown', 'plain words must still say what changed', 'Keep every sentence to 20 words or fewer', 'Open with context')) {
                if ($s -notmatch [regex]::Escape($k)) { throw "Explaining sentences rule missing: $k" }
            }
            $sec = [regex]::Match($s, '(?s)## Explaining sentences.*?(?=\r?\n## )').Value
            if ($sec -notmatch 'personal-unslop') { throw "Explaining sentences section no longer sends readers through personal-unslop" }
        }
    },
    @{
        Name = 'writing_rule_everywhere: now.md (Deep HTML), personal-goal, personal-handoff and personal-md-to-html carry the writing rule'
        Run = {
            $skills = Join-Path $PSScriptRoot '../..'
            $docs = @((Join-Path $Refs 'now.md'), (Join-Path $skills 'personal-goal/SKILL.md'), (Join-Path $skills 'personal-handoff/SKILL.md'), (Join-Path $skills 'personal-md-to-html/SKILL.md'))
            foreach ($d in $docs) {
                $t = (Get-Content $d -Raw) -replace '\s+', ' '
                foreach ($k in @('htsw Explaining sentences rules (20 words or fewer per sentence, context first)', 'personal-unslop pass')) {
                    if ($t -notmatch [regex]::Escape($k)) { throw "$d lost the writing rule: $k" }
                }
            }
        }
    },
    @{
        Name = 'checker_sentence_cap: htsw-check.py rejects fixtures/bad-long-sentence.md for rule 7 and accepts fixtures/good-walk-short.md'
        Run = {
            $out = (python $Checker --input-file (Join-Path $Fix 'bad-long-sentence.md') 2>&1 | Out-String)
            if ($LASTEXITCODE -eq 0) { throw "checker ACCEPTED a rendering with 21+ word sentences" }
            if ($out -notmatch 'over 20 words') { throw "checker failed the long-sentence fixture for some other reason: $out" }
            $code = Invoke-Checker (Join-Path $Fix 'good-walk-short.md')
            if ($code -ne 0) { throw "checker rejected the short-sentence walk fixture (exit $code)" }
        }
    },
    @{
        Name = 'personas_carry_explaining_rules: every persona agent except next-recommender has the eight Explaining-sentences rules'
        Run = {
            $agents = Join-Path $PSScriptRoot '../../../agents'
            $rules = @('Say who does what', 'One idea per sentence', 'Name the term, then say right away what it does', 'Say why it matters', 'Never point at something the reader was not shown', 'plain words must still say what changed', 'Keep every sentence to 20 words or fewer', 'Open with context')
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
    },
    @{
        Name = 'walk_build_good: walk-build builds phase0.walk.json; walk-check --spec exits 0 with SCORE brief N/N'
        Run = {
            $d = New-WalkTmp
            try {
                $spec = Write-WalkSpec $d
                $page = Join-Path $d 'page.html'
                $b = Invoke-WalkBuild $spec $page
                if ($b.Code -ne 0) { throw "walk-build failed (exit $($b.Code)): $($b.Out)" }
                $c = Invoke-WalkCheck $page $spec
                if ($c.Code -ne 0) { throw "walk-check rejected the good page (exit $($c.Code)): $($c.Out)" }
                $m = [regex]::Match($c.Out, 'SCORE brief (\d+)/(\d+)')
                if (-not $m.Success) { throw "no 'SCORE brief N/N' line" }
                if ($m.Groups[1].Value -ne $m.Groups[2].Value -or [int]$m.Groups[2].Value -lt 1) { throw "must-rule score not full: $($m.Value)" }
            }
            finally { Remove-Item $d -Recurse -Force -ErrorAction SilentlyContinue }
        }
    },
    @{
        Name = 'walk_check_points_short: a point over 22 words fails points-short'
        Run = { Assert-WalkRuleFails 'points-short' 'Each record states the choice, the reason and the alternative.' 'Each record states the choice and the reason and the alternative and the owner and the date and the risk and the cost and the review and the sign off today.' }
    },
    @{
        Name = 'walk_check_no_semicolons: a semicolon in a point fails no-semicolons'
        Run = { Assert-WalkRuleFails 'no-semicolons' 'Some decisions are final today.' 'Some decisions are final today; others are not.' }
    },
    @{
        Name = 'walk_check_names_match: a menu label that differs from the heading fails names-match-4-places'
        Run = { Assert-WalkRuleFails 'names-match-4-places' -editHtml { param($h) $h.Replace('<span class="n">1</span>Decisions to record</a>', '<span class="n">1</span>Decisions to recordX</a>') } }
    },
    @{
        Name = 'walk_check_walk_links: a step with no Back link fails walk-links-every-step'
        Run = { Assert-WalkRuleFails 'walk-links-every-step' -editHtml { param($h) $h.Replace('data-back="s1"', 'data-bx="s1"') } }
    },
    @{
        Name = 'walk_check_ascii_only: a non-ASCII character in the page fails ascii-only'
        Run = { Assert-WalkRuleFails 'ascii-only' -editHtml { param($h) $h.Replace('</body>', ([string][char]0x00E9) + '</body>') } }
    },
    @{
        Name = 'walk_check_answers_no_next: a Next link in the answers section fails answers-no-next'
        Run = {
            Assert-WalkRuleFails 'answers-no-next' -editHtml {
                param($h)
                $i = $h.IndexOf('id="answers"'); if ($i -lt 0) { throw 'no answers section' }
                $j = $h.IndexOf('</section>', $i)
                $h.Insert($j, '<a class="next" href="#flow">Next</a>')
            }
        }
    },
    @{
        Name = 'walk_build_rejects_bad_id: a step id with a quote makes walk-build exit non-zero with "must match"'
        Run = { Assert-WalkBuildRejects '"id": "s1"' '"id": "s1\"x"' 'must match' }
    },
    @{
        Name = 'walk_build_rejects_svg_script: an svg_file holding <script makes walk-build exit non-zero'
        Run = {
            Assert-WalkBuildRejects '"file": "strangler.svg"' '"file": "evil.svg"' '<script' -prep {
                param($d) [IO.File]::WriteAllText((Join-Path $d 'evil.svg'), '<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>')
            }
        }
    },
    @{
        Name = 'walk_build_rejects_inline_svg_script: an inline svg block holding <script makes walk-build exit non-zero naming <script'
        Run = { Assert-WalkBuildRejects '"svg_file": {"file": "strangler.svg"' '"svg": {"svg": "<svg><script>alert(1)</script></svg>"' '<script' }
    },
    @{
        Name = 'walk_build_rejects_svg_onload: <svg/onload= (slash, no space) is refused as an event handler'
        Run = { Assert-WalkBuildRejects '"svg_file": {"file": "strangler.svg"' '"svg": {"svg": "<svg/onload=alert(1)></svg>"' 'onload=' }
    },
    @{
        Name = 'walk_build_rejects_svg_entity_js: java&#115;cript: in an attribute is decoded first, then refused as javascript:'
        Run = { Assert-WalkBuildRejects '"svg_file": {"file": "strangler.svg"' '"svg": {"svg": "<svg><text x=\"java&#115;cript:alert(1)\">x</text></svg>"' 'javascript:' }
    },
    @{
        Name = 'walk_build_rejects_svg_external_href: an entity-encoded javascript: href on <use> is refused as an external href'
        Run = { Assert-WalkBuildRejects '"svg_file": {"file": "strangler.svg"' '"svg": {"svg": "<svg><use href=\"java&#115;cript:alert(1)\"/></svg>"' '<use href=' }
    },
    @{
        Name = 'walk_build_rejects_svg_foreignobject: <foreignObject> in an svg is refused'
        Run = { Assert-WalkBuildRejects '"svg_file": {"file": "strangler.svg"' '"svg": {"svg": "<svg><foreignObject><div>x</div></foreignObject></svg>"' '<foreignObject' }
    },
    @{
        Name = 'walk_build_rejects_duplicate_step_id: two steps with id s1 make walk-build exit non-zero with "duplicates"'
        Run = { Assert-WalkBuildRejects '"id": "s2"' '"id": "s1"' 'duplicates' }
    },
    @{
        Name = 'walk_build_rejects_reserved_id: a step id "flow" makes walk-build exit non-zero with "reserved id"'
        Run = { Assert-WalkBuildRejects '"id": "s3"' '"id": "flow"' 'reserved id' }
    },
    @{
        Name = 'walk_check_unique_ids: an id used twice in the page fails unique-ids'
        Run = { Assert-WalkRuleFails 'unique-ids' -editHtml { param($h) $h.Replace('class="pdots"', 'id="top" class="pdots"') } }
    },
    @{
        Name = 'walk_build_rejects_svg_escape: an svg_file path ../x.svg makes walk-build exit non-zero (outside the spec folder)'
        Run = { Assert-WalkBuildRejects '"file": "strangler.svg"' '"file": "../x.svg"' 'outside the spec folder' }
    },
    @{
        Name = 'walk_failsafe_reveal: walk.js has bail() that removes the motion class and a rescue timer that shows stuck sections'
        Run = {
            $j = [IO.File]::ReadAllText($WalkJs)
            if ($j -notmatch 'function bail\(\)\{[^}]*root\.classList\.remove\("motion"\)') { throw "walk.js bail() no longer removes the motion class" }
            if ($j -notmatch 'function rescue\(\)\{') { throw "walk.js has no rescue() function" }
            if ($j -notmatch 'setTimeout\(rescue,\d+\)') { throw "walk.js never schedules rescue()" }
            if ($j -notmatch 'catch\(err\)\{bail\(\)\}') { throw "walk.js motion block no longer calls bail() on an error" }
            if ($j -notmatch 'function an\(t,p\)\{[^\r\n]*catch\(e\)\{bail\(\)') { throw "walk.js an() no longer turns an anime.js error into bail()" }
        }
    },
    @{
        Name = 'walk_no_default_when: a question with no "when" has no timing line and no Final today'
        Run = {
            $h = Get-WalkPage '"why": "It sets how much we commit before real numbers exist.", "when": "Final today.",' '"why": "It sets how much we commit before real numbers exist.",'
            $q1 = [regex]::Match($h, '(?s)<fieldset class="q" id="q1".*?</fieldset>').Value
            $q2 = [regex]::Match($h, '(?s)<fieldset class="q" id="q2".*?</fieldset>').Value
            if (-not $q1 -or -not $q2) { throw "question fieldsets not found" }
            if ($q1 -match 'Final today') { throw "question 1 has a Final today line although it has no when" }
            if ($q1 -match '<br>') { throw "question 1 has a timing line (<br>) although it has no when" }
            if ($q2 -notmatch 'Final today') { throw "question 2 lost its own when text" }
        }
    },
    @{
        Name = 'walk_ba_options: a ba block with kind options renders the options class and the or divider, never an arrow'
        Run = {
            $h = Get-WalkPage '{"note": {"tone": "info", "text": "If a check fails, the developer brings the decision back to Acme with what the check found."}}' '{"ba": {"kind": "options", "before_title": "Option one", "before": ["Keep it."], "after_title": "Option two", "after": ["Change it."]}}'
            $b = [regex]::Match($h, '(?s)<div class="ba opts">.*?</ul></div></div>').Value
            if (-not $b) { throw "no ba opts block rendered" }
            if ($b -notmatch 'class="or"') { throw "options block has no or divider" }
            if ($b -match 'arrow') { throw "options block still has an arrow" }
        }
    },
    @{
        Name = 'walk_stats_static: built .stat .v text equals the spec value and walk.js has no count-up code'
        Run = {
            $h = Get-WalkPage
            $spec = Get-Content $WalkSpec -Raw | ConvertFrom-Json
            $want = @($spec.steps | ForEach-Object { $_.blocks } | Where-Object { $_.stats } | ForEach-Object { $_.stats } | ForEach-Object { [string]$_.value })
            $got = @([regex]::Matches($h, '<div class="stat"><div class="v">([^<]*)</div>') | ForEach-Object { $_.Groups[1].Value })
            if ($want.Count -lt 1) { throw "spec has no stats to compare" }
            if (($want -join '|') -ne ($got -join '|')) { throw "page stat values [$($got -join ',')] differ from spec [$($want -join ',')]" }
            $j = [IO.File]::ReadAllText($WalkJs)
            if ($j -match '\.stat\b|class="v"|\.v\b|count-?up|countUp') { throw "walk.js touches stat values (count-up code)" }
        }
    },
    @{
        Name = 'walk_hero_map_labels: hero map has outcome labels (hm-lbl) and a caption naming the total step count and 1 decision'
        Run = {
            $h = Get-WalkPage $HeroVisualLine ''
            $spec = Get-Content $WalkSpec -Raw | ConvertFrom-Json
            $map = [regex]::Match($h, '(?s)<aside class="hero-map".*?</aside>').Value
            if (-not $map) { throw "no hero map" }
            $outs = @($spec.steps[-1].outcomes)
            if ($outs.Count -lt 1) { throw "last spec step has no outcomes" }
            if ([regex]::Matches($map, 'class="hm-lbl"').Count -ne $outs.Count) { throw "hero map outcome labels do not match the $($outs.Count) outcomes" }
            $cap = [regex]::Match($map, '<text class="hm-cap"[^>]*>([^<]*)</text>').Groups[1].Value
            if ($cap -notmatch ('^' + $spec.steps.Count + ' steps.*1 decision')) { throw "hero map caption '$cap' does not name $($spec.steps.Count) steps and 1 decision" }
        }
    },
    @{
        Name = 'walk_lead_takeaway_short: a 25-word lead fails lead-takeaway-short'
        Run = { Assert-WalkRuleFails 'lead-takeaway-short' 'Every decision from this meeting becomes a one-page record that sets the direction.' 'Every decision from this meeting becomes a one-page record that sets the direction for the team and for every later phase of the work that follows after it today.' }
    },
    @{
        Name = 'walk_takeaway_reads_remember_card: an analogy that echoes the lead does not make idea-takeaway-not-echo MISS when the Remember takeaway is distinct'
        Run = {
            $l = Get-WalkRuleLine 'idea-takeaway-not-echo' 'A strangler fig is a vine that grows around a tree until it replaces it. The new AppHost grows around the old one, one feature at a time.' 'The recipe is the fixed set of steps that moves one screen from old to new.'
            if ($l -match '\bs7\b') { throw "analogy text was read as the takeaway: $l" }
        }
    },
    @{
        Name = 'walk_takeaway_echo_misses: a Remember takeaway that repeats the lead makes idea-takeaway-not-echo MISS and name the step'
        Run = {
            $l = Get-WalkRuleLine 'idea-takeaway-not-echo' 'Real page use, not memory, decides what is worth converting.' 'Client logs show which pages each client really uses.'
            if ($l -notmatch '^MISS' -or $l -notmatch '\bs3\b') { throw "echoing takeaway not reported: $l" }
        }
    },
    @{
        Name = 'walk_lead_claim_regex: "The team is ready to ship on Friday." passes idea-lead-is-claim and "The log file is a list of changes." misses'
        Run = {
            $from = 'We measure today''s AppHost first, so every later claim has a real \"before\".'
            $ok = Get-WalkRuleLine 'idea-lead-is-claim' $from 'The team is ready to ship on Friday.'
            if ($ok -match '\bs2\b') { throw "a claim lead was flagged as a definition: $ok" }
            $bad = Get-WalkRuleLine 'idea-lead-is-claim' $from 'The log file is a list of changes.'
            if ($bad -notmatch '^MISS' -or $bad -notmatch '\bs2\b') { throw "a definition lead was not flagged: $bad" }
        }
    },
    @{
        Name = 'walk_no_placeholder_text: a decision that says "to be set" fails the must rule no-placeholder-text'
        Run = { Assert-WalkRuleFails 'no-placeholder-text' 'Approve phase 0, then fill in the answer sheet after step 12.' 'Approve phase 0, owner to be set.' }
    },
    @{
        Name = 'walk_no_decision_no_strip: an empty decision renders no "Decision needed" text box or note, only the Possible outcomes pills'
        Run = {
            $h = Get-WalkPage 'Approve phase 0, then fill in the answer sheet after step 12.' ''
            if ($h -match '<p class="dt">' -or $h -match '<b>Decision needed</b>' -or $h -match '>Decision needed<') { throw "an empty decision still renders decision text" }
            if ($h -notmatch 'Possible outcomes') { throw "outcome pills lost their Possible outcomes label" }
        }
    },
    @{
        Name = 'walk_hero_visual_renders: hero_visual puts the svg and caption in the hero, drops the mini map, and idea-hero-visual passes'
        Run = {
            $h = Get-WalkPage
            $hero = [regex]::Match($h, '(?s)<header class="hero".*?</header>').Value
            if ($hero -notmatch '<aside class="hero-map hero-vis"><svg[^>]*role="(img|group)"[^>]*aria-label="Phase 0 builds the road') { throw "hero has no hero-vis svg with role img and its own aria-label" }
            if ($hero -notmatch 'id="hv-road"' -or $hero -notmatch 'class="hv-in"' -or $hero -notmatch 'class="hv-draw"') { throw "hero svg lost its hv- motion classes" }
            if ($hero -notmatch '<p class="hv-cap">Every new piece ships switched off until the go decision\.</p>') { throw "hero caption missing" }
            if ($hero -match 'hm-n|hm-lbl|hm-cap') { throw "hero still holds the mini step map" }
            if ($hero -match 'aria-hidden="true"><svg') { throw "hero picture is aria-hidden" }
            $l = Get-WalkRuleLine 'idea-hero-visual'
            if ($l -notmatch '^PASS') { throw "idea-hero-visual did not pass: $l" }
        }
    },
    @{
        Name = 'walk_hero_visual_rejects_script: a hero_visual svg containing <script makes walk-build exit non-zero naming <script'
        Run = {
            Assert-WalkBuildRejects '"svg_file": "phase0-hero.svg"' '"svg_file": "evil-hero.svg"' '<script' -prep {
                param($d) [IO.File]::WriteAllText((Join-Path $d 'evil-hero.svg'), '<svg role="img" aria-label="x"><script>alert(1)</script></svg>')
            }
        }
    },
    @{
        Name = 'walk_hero_visual_rejects_no_role: a hero svg without role="img", or with an aria-label under 8 characters, is refused naming role and aria-label'
        Run = {
            Assert-WalkBuildRejects '"svg_file": "phase0-hero.svg"' '"svg_file": "bad-hero.svg"' 'role="img" and an aria-label' -prep {
                param($d) [IO.File]::WriteAllText((Join-Path $d 'bad-hero.svg'), '<svg viewBox="0 0 10 10" aria-label="a long enough label"><g/></svg>')
            }
            Assert-WalkBuildRejects '"svg_file": "phase0-hero.svg"' '"svg_file": "bad-hero.svg"' 'role="img" and an aria-label' -prep {
                param($d) [IO.File]::WriteAllText((Join-Path $d 'bad-hero.svg'), '<svg viewBox="0 0 10 10" role="img" aria-label="short"><g/></svg>')
            }
        }
    },
    @{
        Name = 'walk_hero_visual_rejects_onload: a hero svg with an onload= handler is refused'
        Run = {
            Assert-WalkBuildRejects '"svg_file": "phase0-hero.svg"' '"svg_file": "bad-hero.svg"' 'onload' -prep {
                param($d) [IO.File]::WriteAllText((Join-Path $d 'bad-hero.svg'), '<svg viewBox="0 0 10 10" role="img" aria-label="a long enough label" onload="alert(1)"><g/></svg>')
            }
        }
    },
    @{
        Name = 'walk_hero_visual_rejects_external_href: a hero svg with <image href="http://..."> is refused'
        Run = {
            Assert-WalkBuildRejects '"svg_file": "phase0-hero.svg"' '"svg_file": "bad-hero.svg"' 'href' -prep {
                param($d) [IO.File]::WriteAllText((Join-Path $d 'bad-hero.svg'), '<svg viewBox="0 0 10 10" role="img" aria-label="a long enough label"><image href="http://example.com/x.png" width="5" height="5"/></svg>')
            }
        }
    },
    @{
        Name = 'walk_hero_visual_rejects_no_viewbox: a hero svg without a viewBox is refused naming viewBox'
        Run = {
            Assert-WalkBuildRejects '"svg_file": "phase0-hero.svg"' '"svg_file": "bad-hero.svg"' 'viewBox' -prep {
                param($d) [IO.File]::WriteAllText((Join-Path $d 'bad-hero.svg'), '<svg role="img" aria-label="a long enough label"><g/></svg>')
            }
        }
    },
    @{
        Name = 'walk_hero_links_render: a hero_links id gets class hv-link, data-go and a "Go to step N" aria-label, and the hint shows'
        Run = {
            $h = Get-WalkPage
            if ($h -notmatch '<g id="hv-switch" class="hv-link hv-in" tabindex="0" role="link" aria-label="Go to step 8: Router" data-go="#s8">') { throw "hv-switch lost its link attributes" }
            if ($h -notmatch 'Click or tap a part of the picture to jump to its step\.') { throw "hero_links hint missing" }
            if ((Get-Content (Join-Path $WalkDir 'walk.js') -Raw) -notmatch 'closest\("\.hv-link"\)') { throw "walk.js does not handle .hv-link" }
            $p = Get-WalkPage '"hero_links": {"hv-switch": "s8", "hv-markers": "s2"},' ''
            if ($p -match 'class="hv-link|Click or tap a part of the picture') { throw "a page without hero_links still has link markup" }
        }
    },
    @{
        Name = 'walk_rejects_multi_svg_and_multi_key_block: two <svg> elements, a two-key block and an empty block are refused'
        Run = {
            Assert-WalkBuildRejects '"svg_file": "phase0-hero.svg"' '"svg_file": "bad-hero.svg"' 'must hold exactly one <svg>' -prep {
                param($d) [IO.File]::WriteAllText((Join-Path $d 'bad-hero.svg'), '<svg role="img" aria-label="a long enough label" viewBox="0 0 1 1"><svg/></svg>')
            }
            Assert-WalkBuildRejects '{"stats": [{"value": "18"' '{"bullets": ["x"], "h3": "x", "stats": [{"value": "18"' 'each block must be an object with one key'
            Assert-WalkBuildRejects '{"stats": [{"value": "18"' '{}, {"stats": [{"value": "18"' 'each block must be an object with one key'
        }
    },
    @{
        Name = 'walk_hero_links_a11y_and_cue: root svg is role group with links and role img without; resting drop-shadow; same-hash scroll'
        Run = {
            $h = Get-WalkPage
            if ($h -notmatch '<svg[^>]*role="group"') { throw "hero root svg is not role=group when hero_links is set" }
            $p = Get-WalkPage '"hero_links": {"hv-switch": "s8", "hv-markers": "s2"},' ''
            if ($p -notmatch '<aside class="hero-map hero-vis"><svg[^>]*role="img"') { throw "a page without hero_links lost role=img on the hero svg" }
            $l = Get-WalkRuleLineEdited 'idea-hero-visual' { param($x) $x.Replace('role="group"', 'role="img"') }
            if ($l -notmatch '^MISS.*role="group"') { throw "idea-hero-visual did not name role group for a linked hero with role img: $l" }
            if ((Get-Content (Join-Path $WalkDir 'walk.css') -Raw) -notmatch '\.hv-link\{[^}]*drop-shadow') { throw "walk.css .hv-link has no resting drop-shadow" }
            if ((Get-Content (Join-Path $WalkDir 'walk.js') -Raw) -notmatch 'location\.hash===') { throw "walk.js hvGo has no same-hash branch" }
        }
    },
    @{
        Name = 'walk_hero_links_rejects_root_and_existing_attr: the root svg id and an element that already has role are refused'
        Run = {
            Assert-WalkBuildRejects '"hv-switch": "s8"' '"hv-root": "s8"' 'cannot be the root svg' -prep {
                param($d) $t = [IO.File]::ReadAllText((Join-Path $d 'phase0-hero.svg')); [IO.File]::WriteAllText((Join-Path $d 'phase0-hero.svg'), $t.Replace('<svg viewBox', '<svg id="hv-root" viewBox'))
            }
            Assert-WalkBuildRejects '"hv-switch": "s8"' '"hv-pre": "s8"' 'already has role' -prep {
                param($d) $t = [IO.File]::ReadAllText((Join-Path $d 'phase0-hero.svg')); [IO.File]::WriteAllText((Join-Path $d 'phase0-hero.svg'), $t.Replace('<g id="hv-switch"', '<g id="hv-pre" role="button"><g id="hv-switch"').Replace('</svg>', '</g></svg>'))
            }
        }
    },
    @{
        Name = 'walk_hero_links_rejects_bad: an unknown svg id or an unknown step id is refused with a hero_links message'
        Run = {
            Assert-WalkBuildRejects '"hv-switch": "s8"' '"hv-nope": "s8"' 'walk-build: hero_links element id .hv-nope. must appear exactly once'
            Assert-WalkBuildRejects '"hv-switch": "s8"' '"hv-switch": "s99"' 'walk-build: hero_links hv-switch points at step id .s99.'
        }
    },
    @{
        Name = 'walk_phone_cta_before_dstrip: at the 900px breakpoint the Start CTA has a lower order than the decision strip, and the dstrip carries the answer-sheet note'
        Run = {
            $css = Get-Content (Join-Path $WalkDir 'walk.css') -Raw
            $mq = [regex]::Match($css, '@media \(max-width:900px\)\{.*')
            $c = [regex]::Match($mq.Value, '\.hero-main>\.cta\{order:(\d+)')
            $d = [regex]::Match($mq.Value, '\.hero-main>\.dstrip\{order:(\d+)')
            if (-not $c.Success -or -not $d.Success -or [int]$c.Groups[1].Value -ge [int]$d.Groups[1].Value) { throw "phone CTA is not ordered before the decision strip" }
            if ((Get-WalkPage) -notmatch '<p class="dnote">You answer at the end, on the answer sheet\.</p>') { throw "decision strip lacks the answer-sheet note" }
        }
    },
    @{
        Name = 'walk_hero_visual_clear_errors: a missing svg_file key, a missing file and a non-ASCII file each give one "walk-build: hero_visual" message and no traceback'
        Run = {
            Assert-WalkBuildRejects '"svg_file": "phase0-hero.svg", ' '' 'walk-build: hero_visual needs an svg_file'
            Assert-WalkBuildRejects '"svg_file": "phase0-hero.svg"' '"svg_file": "nope-hero.svg"' 'walk-build: hero_visual svg_file nope-hero.svg does not exist'
            Assert-WalkBuildRejects '"svg_file": "phase0-hero.svg"' '"svg_file": "uni-hero.svg"' 'walk-build: hero_visual svg_file uni-hero.svg must be ASCII' -prep {
                param($d) [IO.File]::WriteAllBytes((Join-Path $d 'uni-hero.svg'), [Text.Encoding]::UTF8.GetBytes('<svg viewBox="0 0 10 10" role="img" aria-label="a long enough label"><text>caf' + [char]0xE9 + '</text></svg>'))
            }
        }
    },
    @{
        Name = 'walk_hero_text_size: hero svg text under 22 units at a 560 wide viewBox is a MISS on hero-text-size; the shipped hero passes; an svg without role is a MISS on idea-hero-visual'
        Run = {
            $l = Get-WalkRuleLine 'hero-text-size'
            if ($l -notmatch '^PASS') { throw "hero-text-size did not pass on the shipped hero: $l" }
            $l = Get-WalkRuleLineEdited 'hero-text-size' { param($h) $h.Replace('font-size:22px', 'font-size:16px') }
            if ($l -notmatch '^MISS') { throw "hero-text-size did not MISS on small text: $l" }
            $l = Get-WalkRuleLineEdited 'idea-hero-visual' { param($h) $h -replace '(<svg viewBox="0 0 560 \d+") role="(img|group)"', '$1' }
            if ($l -notmatch '^MISS') { throw "idea-hero-visual did not MISS on an svg without role: $l" }
        }
    },
    @{
        Name = 'walk_hero_visual_absent_keeps_map: without hero_visual the mini step map stays and idea-hero-visual is MISS'
        Run = {
            $h = Get-WalkPage $HeroVisualLine ''
            if ($h -match 'class="hero-map hero-vis"') { throw "a page without hero_visual still has a hero-vis picture" }
            if ($h -notmatch '<aside class="hero-map" aria-hidden="true">' -or $h -notmatch 'class="hm-lbl"') { throw "the mini step map is gone" }
            $l = Get-WalkRuleLine 'idea-hero-visual' $HeroVisualLine ''
            if ($l -notmatch '^MISS') { throw "idea-hero-visual did not MISS: $l" }
        }
    },
    @{
        Name = 'walk_alongside_dashed: alongside draws dashed box, tag and legend in both charts; 5 words refused; unstated parallel is a MISS'
        Run = {
            $h = Get-WalkPage
            if ([regex]::Matches($h, 'class="st cat-a al"').Count -ne 1 -or $h -notmatch 'class="st pst cat-a al"') { throw "step 4 has no al class in both charts" }
            if ($h -notmatch 'class="s altag"[^>]*>while others go on' -or $h -notmatch 'runs alongside</span>') { throw "tag or legend missing" }
            if ((Get-WalkPage '"alongside": "while others go on",' '') -match 'Dashed boxes') { throw "legend shown without alongside" }
            Assert-WalkBuildRejects '"alongside": "while others go on"' '"alongside": "runs while the others go on"' 'alongside'
            $l = Get-WalkRuleLine 'alongside-stated' '"lead": "Every decision from this meeting' '"lead": "Meanwhile every decision from this meeting'
            if ($l -notmatch '^MISS') { throw "alongside-stated did not MISS: $l" }
        }
    },
    @{
        Name = 'walk_alongside_decision_refused: alongside on the decision step and over 24 chars are refused by walk-build'
        Run = {
            Assert-WalkBuildRejects '"id": "s12", "name": "Criteria and decision", "cat": "a",' '"id": "s12", "name": "Criteria and decision", "cat": "a", "alongside": "while others go on",' 'cannot be set on the decision step'
            Assert-WalkBuildRejects '"alongside": "while others go on"' '"alongside": "while all the others go"' 'at most 24 characters'
        }
    },
    @{
        Name = 'walk_alongside_bypass_edge: a solid bypass edge runs from box 3 to box 5 around the alongside box 4, and the stub out of box 4 ends in an open circle'
        Run = {
            $h = Get-WalkPage
            if ($h -notmatch 'class="flow-edge al-bypass" data-from="2" data-to="5"') { throw "no bypass edge from the step before to the step after the alongside box" }
            if ($h -notmatch 'class="al-dot"') { throw "no open-circle end on the alongside stub" }
            if ($h -match 'al-bypass[^>]*stroke-dasharray') { throw "bypass path is dashed" }
            if ((Get-Content (Join-Path $WalkDir 'walk.css') -Raw) -match '\.al-bypass\{[^}]*dasharray') { throw "walk.css dashes the bypass" }
            if ($h -match 'class="flow-edge al-edge"[^>]*marker-end') { throw "stub has an arrowhead" }
            if ([regex]::Matches($h, 'class="parr al"').Count -ne 1) { throw "expected exactly one phone parr al" }
            if ($h -notmatch 'class="afternote">starts after step 3<') { throw "phone list has no starts-after-step-3 note" }
            if ($h -notmatch '(?s)<span class="pn">5</span>(?:(?!</li>).)*class="afternote">starts after step 3<') { throw "starts-after note not in phone box 5" }
            if ($h -match '(?s)class="altag">[^<]*</small>\s*<small class="afternote"') { throw "after-note sits in the alongside box" }
            if ((Get-Content (Join-Path $WalkDir 'walk.css') -Raw) -notmatch '\.flow-edge\.al-edge\{[^}]*stroke:var\(--a\)') { throw "stub not accent-stroked" }
            if ([regex]::Matches($h, 'starts after step').Count -ne 1) { throw "expected exactly one starts-after note" }
            if ((Get-Content $WalkJs -Raw) -notmatch [regex]::Escape('$$(".flow-edge:not(.al-edge)",chart)')) { throw "walk.js passes the al-edge stub to createDrawable, which hides its dash" }
        }
    },
    @{
        Name = 'walk_alongside_position_refused: alongside at a column head or tail, before the decision, or after another alongside is refused'
        Run = {
            foreach ($t in 's1','s6','s11') {
                $m = [regex]::Match((Get-Content $WalkSpec -Raw), '"id": "' + $t + '", "name": "[^"]*"')
                Assert-WalkBuildRejects $m.Value ($m.Value + ', "alongside": "while others go on"') 'needs a step before and after'
            }
            $m = [regex]::Match((Get-Content $WalkSpec -Raw), '"id": "s5", "name": "[^"]*"')
            Assert-WalkBuildRejects $m.Value ($m.Value + ', "alongside": "also runs"') 'cannot follow another alongside'
        }
    },
    @{
        Name = 'walk_alongside_edge_caption: the arrow out of the alongside box is dashed (al-edge), the arrows caption comes before the chart, the legend has a dashed swatch, the rail item is dashed'
        Run = {
            $h = Get-WalkPage
            if ($h -notmatch 'class="flow-edge al-edge"') { throw "no al-edge arrow in the chart" }
            if ([regex]::Matches($h, 'class="flow-edge al-edge"').Count -ne 1) { throw "expected exactly one al-edge arrow" }
            $c = $h.IndexOf('A dashed step ends in an open circle. The next step does not wait.'); $f = $h.IndexOf('class="fig flowfig"')
            if ($c -lt 0 -or $f -lt 0 -or $c -gt $f) { throw "arrows caption missing or not before the chart (caption $c, chart $f)" }
            if ($h -notmatch '<i class="dash"></i>runs alongside') { throw "legend has no dashed swatch" }
            if ($h -notmatch 'class="cat-a al" href="#s4"') { throw "rail item for the alongside step has no al class" }
            $n = Get-WalkPage '"alongside": "while others go on",' ''
            if ($n -match 'al-edge"|class="dash"|does not wait') { throw "alongside marks shown without an alongside step" }
        }
    },
    @{
        Name = 'walk_alongside_stated_regex: "while others go on" without the field is a MISS; "alongside" only inside an svg block passes'
        Run = {
            $l = Get-WalkRuleLine 'alongside-stated' '"lead": "Every decision from this meeting' '"lead": "While others go on, every decision from this meeting'
            if ($l -notmatch '^MISS') { throw "alongside-stated did not MISS on 'while others go on': $l" }
            $svg = '{"svg": {"svg": "<svg viewBox=\"0 0 10 10\" role=\"img\" aria-label=\"x\"><text x=\"1\" y=\"5\">alongside</text></svg>"}}, {"table": {"head": ["Area", "What we count", "Source"], "rows": ['
            $l = Get-WalkRuleLine 'alongside-stated' '{"table": {"head": ["Area", "What we count", "Source"], "rows": [' $svg
            if ($l -notmatch '^PASS') { throw "alongside-stated flagged a word inside svg: $l" }
        }
    },
    @{
        Name = 'walk_hv_draw_keeps_dash: walk.js saves a hero path own stroke-dasharray/dashoffset and restores them on complete and in bail(), never sets ""'
        Run = {
            $j = Get-Content $WalkJs -Raw
            if ($j -notmatch 'dashKeep\.set\(p,') { throw "walk.js does not save the authored dash before drawing" }
            if ($j -notmatch 'onComplete:function\(\)\{dashBack\(p\)\}') { throw "hv-draw onComplete does not restore the authored dash" }
            if ($j -notmatch '\$\$\("\.hv-draw"\)\.forEach\(function\(p\)\{dashBack\(p\)\}\)') { throw "bail() does not restore the authored dash" }
        }
    },
    @{
        Name = 'walk_hidden_rules_in_hid: every .motion <sel>{...opacity:0} rule in walk.css is covered by the HID selector list in walk.js'
        Run = {
            $css = Get-Content (Join-Path $WalkDir 'walk.css') -Raw
            $j = Get-Content $WalkJs -Raw
            if ($j -notmatch 'var HID="([^"]+)"') { throw "HID list not found in walk.js" }
            $hid = @($Matches[1] -split ',\s*')
            $n = 0
            foreach ($m in [regex]::Matches($css, '(?m)^(\.motion [^{]+)\{[^}]*opacity:0[;}]')) {
                foreach ($sel in ($m.Groups[1].Value -split ',')) {
                    $sel = $sel.Trim() -replace '^\.motion\s+', ''
                    $last = ($sel -split '\s+')[-1]
                    $n++
                    if ($hid -notcontains $sel -and $hid -notcontains $last) { throw "walk.css hides '$sel' at opacity 0 but HID in walk.js does not list it, so the fault rescue skips it" }
                }
            }
            if ($n -lt 5) { throw "found only $n .motion opacity:0 selectors; the parse is broken" }
        }
    },
    @{
        Name = 'walk_seen_toggle_markup: the built page has one seen-tog button per step with aria-pressed and aria-label, outside the step link'
        Run = {
            $h = Get-WalkPage
            $steps = [regex]::Matches($h, 'class="st"').Count
            $m = [regex]::Matches($h, '<button type="button" class="seen-tog" data-step="[^"]+" aria-pressed="(true|false)" aria-label="Mark step \d+ as (not )?read"></button>')
            if ($m.Count -lt 2) { throw "found only $($m.Count) well-formed seen-tog buttons" }
            $nav = [regex]::Match($h, '<nav class="mf".*?</nav>').Value
            if ([regex]::Matches($nav, 'class="seen-tog"').Count -ne $m.Count) { throw "a seen-tog button is outside the menu or malformed" }
            if ($nav -match '<a [^>]*>(?:(?!</a>).)*seen-tog') { throw "a seen-tog button sits inside an <a> link" }
            if ($nav -notmatch 'id="reset-prog"') { throw "no Reset progress button in the menu" }
        }
    },
    @{
        Name = 'walk_seen_unmark_reset: walk.js unmark saves; reset removes only the seen key; no confirm( or alert( call'
        Run = {
            $j = [IO.File]::ReadAllText($WalkJs)
            if ($j -notmatch 'function setSeen\(id,on\)\{[^\r\n]*delete seen\[id\][^\r\n]*save\("seen",seen\)') { throw "walk.js has no unmark path that saves the seen key" }
            if ($j -notmatch 'localStorage\.removeItem\(KEY\+":seen"\)') { throw "walk.js reset does not remove the seen key" }
            if ($j -match 'localStorage\.clear|removeItem\(KEY\+":(?!seen")') { throw "walk.js reset clears more than the seen key" }
            if ($j -match '\b(confirm|alert)\(') { throw "walk.js calls confirm( or alert(; dialogs are banned" }
        }
    },
    @{
        Name = 'walk_seen_dwell_constant: walk.js auto-marks a step after DWELL_MS = 4000 and uses the constant'
        Run = {
            $j = [IO.File]::ReadAllText($WalkJs)
            if ($j -notmatch 'var DWELL_MS=4000;') { throw "DWELL_MS is not 4000" }
            if ($j -notmatch 'markSeen\(id,true\)\},DWELL_MS\)') { throw "the dwell timer does not use DWELL_MS" }
        }
    },
    @{
        Name = 'walk_docs_wired: SKILL.md and walk-page.md name walk-build.py and walk-check.py; SKILL.md and now.md point at walk-page.md'
        Run = {
            $s = Get-Content $Skill -Raw; $n = Get-Content (Join-Path $Refs 'now.md') -Raw; $w = Get-Content (Join-Path $Refs 'walk-page.md') -Raw
            foreach ($doc in @(@('SKILL.md', $s), @('walk-page.md', $w))) {
                foreach ($k in @('walk-build.py', 'walk-check.py')) {
                    if ($doc[1] -notmatch [regex]::Escape($k)) { throw "$($doc[0]) does not mention $k" }
                }
            }
            if ($s -notmatch [regex]::Escape('references/walk-page.md')) { throw "SKILL.md does not point at references/walk-page.md" }
            if ($n -notmatch [regex]::Escape('references/walk-page.md')) { throw "now.md does not point at references/walk-page.md" }
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
