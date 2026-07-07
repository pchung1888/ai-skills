#requires -Version 7
# Eval grader for personal-critic-gate v0.9.0 (panel v2). See evals/eval-plan.md.
# Structural + referential-integrity grader: the 5-seat panel, Stay-Paused List,
# operating modes, the ms-mario reviewer, lib scripts, and mode discovery must all be intact.
$ErrorActionPreference = 'Stop'

$SkillDir  = Resolve-Path (Join-Path $PSScriptRoot '..')              # personal-critic-gate/
$VoteParserBehavioral = Join-Path $PSScriptRoot 'test_vote_parser.py'
$TallyBehavioral      = Join-Path $PSScriptRoot 'test_tally.py'
$Skill    = Join-Path $SkillDir 'SKILL.md'
$Agents   = Resolve-Path (Join-Path $SkillDir '..\..\agents')        # plugins/ping-personal/agents/
$Lib      = Join-Path $SkillDir 'lib'

$tests = @(
    @{
        Name = 'skill_frontmatter: SKILL.md declares name=personal-critic-gate + a description'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?m)^name:\s*personal-critic-gate\s*$') { throw "frontmatter name not personal-critic-gate" }
            if ($s -notmatch '(?m)^description:\s*\S') { throw "frontmatter description missing" }
        }
    },
    @{
        Name = 'required_sections: Voting Model / Stay-Paused List / Reviewer Matrix / How to Dispatch'
        Run = {
            $s = Get-Content $Skill -Raw
            foreach ($h in @('## Voting Model','## Stay-Paused List','## Reviewer Matrix','## How to Dispatch')) {
                if ($s -notmatch [regex]::Escape($h)) { throw "missing required section: $h" }
            }
        }
    },
    @{
        Name = 'voters_5seat_and_modes_documented: ms-mario + amanda + rhea + domain + codex; PAUSE + AUTO-RESOLVE'
        Run = {
            $s = Get-Content $Skill -Raw
            foreach ($v in @('ms-mario','amanda','rhea','codex','iris')) {
                if ($s -notmatch [regex]::Escape($v)) { throw "seat reviewer '$v' not documented" }
            }
            foreach ($m in @('PAUSE','AUTO-RESOLVE')) {
                if ($s -notmatch [regex]::Escape($m)) { throw "operating mode '$m' not documented" }
            }
            # Proposer no longer votes
            if ($s -notmatch '(?i)proposer no longer votes') {
                throw "SKILL.md must document that the proposer no longer votes in the 5-seat panel"
            }
        }
    },
    @{
        Name = 'ms_mario_agent_exists: agents/ms-mario.md present on disk [F04]'
        Run = {
            $p = Join-Path $Agents 'ms-mario.md'
            if (-not (Test-Path $p)) { throw "critic-gate dispatches ms-mario but agents/ms-mario.md is missing" }
        }
    },
    @{
        Name = 'domain_seat_agents_exist: agents/vex.md + agents/maggie.md present on disk'
        Run = {
            foreach ($a in @('vex.md','maggie.md')) {
                $p = Join-Path $Agents $a
                if (-not (Test-Path $p)) { throw "domain seat requires $a but agents/$a is missing" }
            }
        }
    },
    @{
        Name = 'iris_agent_exists: agents/iris.md present on disk (Seat 5 fallback)'
        Run = {
            $p = Join-Path $Agents 'iris.md'
            if (-not (Test-Path $p)) { throw "Seat 5 iris fallback requires agents/iris.md but it is missing" }
        }
    },
    @{
        Name = 'seat5_dispatch_mechanism: Agent-tool subagent_type codex:codex-rescue; both Skill-tool and slash paths warned against'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch [regex]::Escape('subagent_type: "codex:codex-rescue"')) {
                throw "Seat 5 must specify Agent-tool dispatch via subagent_type codex:codex-rescue"
            }
            if ($s -notmatch '(?i)do NOT invoke.{0,30}via the\s+Skill tool') {
                throw "skill must warn against the Skill-tool dispatch path that hangs the session"
            }
            if ($s -notmatch '(?i)do NOT type the\s+.?/codex:rescue.?\s+slash command') {
                throw "skill must also warn against the /codex:rescue slash-command dispatch path"
            }
        }
    },
    @{
        Name = 'seat5_parse_rule: balanced-scan extraction + VOTE-value validation, not last-line / flat-regex'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?i)do NOT use "last non-empty line"') {
                throw "skill must reject the stale last-non-empty-line parsing rule"
            }
            if ($s -notmatch '(?i)balanced.{0,40}scan') {
                throw "Seat 5 parsing must specify a quote-aware balanced-brace scan, not a flat regex"
            }
            if ($s -notmatch '(?i)NOT sufficient') {
                throw "skill must call out the naive flat regex as NOT sufficient"
            }
            if ($s -notmatch '(?i)MUST be\s+one of `?PASS') {
                throw "Seat 5 parsing must validate the VOTE value against the PASS/FIX/BLOCK set"
            }
        }
    },
    @{
        Name = 'readonly_guard_lines_verbatim: Do NOT fix + Do NOT edit + Review-only preserved in Seat 5 brief'
        Run = {
            $s = Get-Content $Skill -Raw
            foreach ($line in @('Do NOT fix. Do NOT edit any files. Review-only.')) {
                if ($s -notmatch [regex]::Escape($line)) {
                    throw "read-only guard line missing from Seat 5 brief: '$line'"
                }
            }
        }
    },
    @{
        Name = 'mode_discovery_print: skill must document printing Mode line always'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?i)Mode:\s+<mode>') {
                throw "skill must document printing 'Mode: <mode> (from beacon <slug>)' line"
            }
            if ($s -notmatch '(?i)Mode: interactive .default; no beacon found.') {
                throw "skill must document printing 'Mode: interactive (default; no beacon found)'"
            }
        }
    },
    @{
        Name = 'lib_scripts_exist: lib/vote_parser.py + lib/tally.py present on disk'
        Run = {
            foreach ($f in @('vote_parser.py','tally.py')) {
                $p = Join-Path $Lib $f
                if (-not (Test-Path $p)) { throw "canonical lib script missing: lib/$f" }
            }
        }
    },
    @{
        Name = 'lib_scripts_referenced: SKILL.md references vote_parser.py and tally.py'
        Run = {
            $s = Get-Content $Skill -Raw
            foreach ($f in @('vote_parser.py','tally.py')) {
                if ($s -notmatch [regex]::Escape($f)) { throw "SKILL.md does not reference $f" }
            }
        }
    },
    @{
        Name = 'rhea_master_of_coin: agents/rhea.md has Master of Coin section'
        Run = {
            $r = Get-Content (Join-Path $Agents 'rhea.md') -Raw
            if ($r -notmatch '(?i)master of coin') {
                throw "agents/rhea.md is missing the Master of Coin section"
            }
        }
    },
    @{
        Name = 'preflight_probe: SKILL.md documents preflight codex probe before Seat 5 dispatch'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?i)preflight') {
                throw "SKILL.md must document the preflight codex probe"
            }
            if ($s -notmatch '(?i)codex unavailable') {
                throw "SKILL.md must document 'codex unavailable' announcement"
            }
        }
    },
    @{
        Name = 'seat2_amanda_vision_path: amanda brief documents vision_path conditional (read WHY when present; note absence when missing)'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?i)vision_path') {
                throw "SKILL.md must reference vision_path in the amanda (Seat 2) dispatch brief"
            }
            if ($s -notmatch '(?i)no vision doc') {
                throw "SKILL.md must instruct amanda to note 'no vision doc' in why field when vision_path absent"
            }
            if ($s -notmatch "(?i)judge intent against the WHY|judge.*WHY") {
                throw "SKILL.md must instruct amanda to judge against the WHY (vision doc) when vision_path present"
            }
        }
    },
    @{
        Name = 'domain_routing_table: SKILL.md has Seat 4 routing table with vex + maggie keywords'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?i)Domain Routing Table') {
                throw "SKILL.md must have a Seat 4 Domain Routing Table"
            }
            foreach ($kw in @('vex','maggie')) {
                if ($s -notmatch "(?i)Seat 4.*$kw|$kw.*Seat 4") {
                    # Looser check: just require both appear in proximity to routing
                    if ($s -notmatch "(?i)routing.*$kw|$kw.*routing") {
                        throw "routing table must mention '$kw' as domain reviewer"
                    }
                }
            }
        }
    }
)

$pass = 0; $fail = 0
foreach ($t in $tests) {
    try { & $t.Run; $pass++; Write-Host "PASS $($t.Name)" -ForegroundColor Green }
    catch { $fail++; Write-Host "FAIL $($t.Name): $_" -ForegroundColor Red }
}

# -- Behavioral test suite: vote_parser -----------------------------------------
$vpOut = (python $VoteParserBehavioral 2>&1 | Out-String)
$vpExit = $LASTEXITCODE
foreach ($ln in ($vpOut -split "`n")) {
    $ln = $ln.Trim()
    if ($ln -match '^PASS ') { $pass++; Write-Host "PASS vote_parser/$($ln.Substring(5))" -ForegroundColor Green }
    elseif ($ln -match '^FAIL ') { $fail++; Write-Host "FAIL vote_parser/$($ln.Substring(5))" -ForegroundColor Red }
}
if ($vpExit -ne 0 -and ($vpOut -notmatch 'FAIL ')) {
    $fail++
    Write-Host "FAIL vote_parser/test_vote_parser.py (script error)" -ForegroundColor Red
    Write-Host $vpOut
}

# -- Behavioral test suite: tally -----------------------------------------------
$tallyOut = (python $TallyBehavioral 2>&1 | Out-String)
$tallyExit = $LASTEXITCODE
foreach ($ln in ($tallyOut -split "`n")) {
    $ln = $ln.Trim()
    if ($ln -match '^PASS ') { $pass++; Write-Host "PASS tally/$($ln.Substring(5))" -ForegroundColor Green }
    elseif ($ln -match '^FAIL ') { $fail++; Write-Host "FAIL tally/$($ln.Substring(5))" -ForegroundColor Red }
}
if ($tallyExit -ne 0 -and ($tallyOut -notmatch 'FAIL ')) {
    $fail++
    Write-Host "FAIL tally/test_tally.py (script error)" -ForegroundColor Red
    Write-Host $tallyOut
}

if ($fail -eq 0) { Write-Host "EVAL PASS personal-critic-gate ($pass)" -ForegroundColor Green; exit 0 }
else { Write-Host "EVAL FAIL personal-critic-gate ($fail of $($pass+$fail))" -ForegroundColor Red; exit 1 }
