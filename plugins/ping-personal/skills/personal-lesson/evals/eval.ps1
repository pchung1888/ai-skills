#requires -Version 7
# Eval grader for personal-lesson master router (instruction-only). See evals/eval-plan.md.
# Structural + referential-integrity grader: the router must document its routing contract
# AND every domain skill it routes to must exist on disk.
$ErrorActionPreference = 'Stop'

$SkillDir  = Resolve-Path (Join-Path $PSScriptRoot '..')          # personal-lesson/
$SkillsDir = Split-Path $SkillDir                                 # .../skills/
$Skill     = Join-Path $SkillDir 'SKILL.md'
$Domains   = @('personal-lesson-ui','personal-lesson-parser','personal-lesson-data','personal-lesson-tooling')
$Classify  = Join-Path $SkillDir 'lib/classify.py'
$EmptyKw   = Join-Path $SkillDir 'evals/fixtures/empty-keywords.md'   # hermetic: no CWD override
$env:PYTHONIOENCODING = 'utf-8'   # cp1252 console guard (CLAUDE.md Windows pitfall)

$tests = @(
    @{
        Name = 'skill_frontmatter: SKILL.md declares name=personal-lesson + a description'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?m)^name:\s*personal-lesson\s*$') { throw "frontmatter name not personal-lesson" }
            if ($s -notmatch '(?m)^description:\s*\S') { throw "frontmatter description missing" }
        }
    },
    @{
        Name = 'routes_to_existing_domains: all 4 domain skills named AND present on disk [F02,F03]'
        Run = {
            $s = Get-Content $Skill -Raw
            foreach ($d in $Domains) {
                if ($s -notmatch [regex]::Escape($d)) { throw "domain skill '$d' not referenced in the router" }
                $p = Join-Path $SkillsDir "$d/SKILL.md"
                if (-not (Test-Path $p)) { throw "router references '$d' but $d/SKILL.md is missing on disk" }
            }
        }
    },
    @{
        Name = 'required_sections: Capture flow / Step 1 Classify / Step 2 Dispatch / Browse mode'
        Run = {
            $s = Get-Content $Skill -Raw
            foreach ($h in @('## Capture flow','### Step 1 -- Classify into a domain','### Step 2 -- Dispatch to domain skill','## Browse mode')) {
                if ($s -notmatch [regex]::Escape($h)) { throw "missing required section: $h" }
            }
        }
    },
    @{
        Name = 'classifier_present: lib/classify.py exists'
        Run = {
            if (-not (Test-Path $Classify)) { throw "missing classifier script: lib/classify.py" }
        }
    },
    @{
        Name = 'classifier_routing: known lesson text routes to expected domain [Step 1]'
        Run = {
            $cases = @(
                @{ Text = 'React component hydration bug in page.tsx';                 Expect = 'personal-lesson-ui' }
                @{ Text = 'PDF parse to extract each line item from a bank statement';  Expect = 'personal-lesson-parser' }
                @{ Text = 'vault read-only file path encoding with Chinese character';  Expect = 'personal-lesson-data' }
                @{ Text = 'git worktree pre-commit hook in PowerShell';                 Expect = 'personal-lesson-tooling' }
                @{ Text = 'the weather is nice today';                                  Expect = 'personal-lesson-tooling' }  # zero-hit fallback
                @{ Text = 'schema dedupe';                                             Expect = 'personal-lesson-data' }      # tie data vs parser -> data
                @{ Text = 'guide to digital transformation';                           Expect = 'personal-lesson-ui' }       # characterization of KNOWN substring over-match (ui in 'guide', git in 'digital' -> tie -> ui). See SKILL.md Gotchas.
            )
            foreach ($c in $cases) {
                $got = (python $Classify --text $c.Text --keywords-file $EmptyKw 2>$null | Out-String).Trim()
                if ($got -ne $c.Expect) { throw "routing '$($c.Text)' -> '$got', expected '$($c.Expect)' (if blank: run 'python $Classify --text ...' to see stderr)" }
            }
        }
    }
)

$pass = 0; $fail = 0
foreach ($t in $tests) {
    try { & $t.Run; $pass++; Write-Host "PASS $($t.Name)" -ForegroundColor Green }
    catch { $fail++; Write-Host "FAIL $($t.Name): $_" -ForegroundColor Red }
}
if ($fail -eq 0) { Write-Host "EVAL PASS personal-lesson ($pass)" -ForegroundColor Green; exit 0 }
else { Write-Host "EVAL FAIL personal-lesson ($fail of $($pass+$fail))" -ForegroundColor Red; exit 1 }
