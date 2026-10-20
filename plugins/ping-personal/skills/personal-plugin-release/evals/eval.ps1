#requires -Version 7
# Eval grader for personal-plugin-release. See evals/eval-plan.md for the failure-mode map.
# Deterministic red/green grader. Exit 0 = all checks pass; exit 1 = at least one fails.
# ASCII only (no em-dashes/smart-quotes -- Windows PowerShell 5.1 cp1252 pitfall).
$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'

$SkillDir = Resolve-Path (Join-Path $PSScriptRoot '..')
$Skill    = Join-Path $SkillDir 'SKILL.md'

# The load-bearing knowledge this skill exists to carry. If any of these
# regexes stops matching, the skill has lost the fact that caused the
# original friction (7 sessions of "is it actually installed?") or the
# dual-runtime coupling added for Codex.
$couplingChecks = @(
    @{ Pat = [regex]::Escape('plugins/ping-personal/.claude-plugin/plugin.json'); Why = 'repo plugin.json path' },
    @{ Pat = [regex]::Escape('.claude-plugin/marketplace.json');                  Why = 'repo marketplace.json path' },
    @{ Pat = [regex]::Escape('plugins/ping-personal/.codex-plugin/plugin.json');  Why = 'Codex plugin.json path' },
    @{ Pat = [regex]::Escape('.codex-plugin/marketplace.json');                   Why = 'Codex marketplace.json path' },
    @{ Pat = [regex]::Escape('installed_plugins.json');                          Why = 'user-scope installed_plugins.json' },
    @{ Pat = [regex]::Escape('codex plugin add ping-personal@ping-personal');     Why = 'Codex install command' },
    @{ Pat = [regex]::Escape('check_dual_runtime.py');                            Why = 'dual-runtime drift check' },
    @{ Pat = [regex]::Escape('ping-personal@ping-personal');                     Why = 'correct install key (owner@name)' },
    @{ Pat = 'NOT\s+`?ping-personal@personal-plugin';                            Why = 'wrong-key warning' },
    @{ Pat = [regex]::Escape('refs/remotes/origin/HEAD');                          Why = 'checkout the default branch, not a hard-coded master' },
    @{ Pat = [regex]::Escape('config.toml.bak-before-');                           Why = 'Codex config backup before the install' },
    @{ Pat = 'model_reasoning_effort';                                             Why = 'protected Codex config lines checked after each command' },
    @{ Pat = [regex]::Escape('failed to parse plugin hooks config');               Why = 'Codex hooks parse check in the verify gate' }
)

$tests = @(
    @{
        Name = 'skill_frontmatter: SKILL.md declares the right name + a description'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?m)^name:\s*personal-plugin-release\s*$') { throw "frontmatter name not personal-plugin-release" }
            if ($s -notmatch '(?m)^description:\s*\S') { throw "frontmatter description missing" }
        }
    },
    @{
        Name = 'manifest_coupling: Claude and Codex manifests + install-key contract documented'
        Run = {
            $s = Get-Content $Skill -Raw
            foreach ($c in $couplingChecks) {
                if ($s -notmatch $c.Pat) { throw "coupling knowledge lost: $($c.Why)" }
            }
        }
    },
    @{
        Name = 'verify_loaded_gate: mandatory gate + eval-suite ship gate + never-push-main all present'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?i)VERIFY-LOADED') { throw "verify-loaded gate missing" }
            if ($s -notmatch [regex]::Escape('run-all.ps1')) { throw "eval-suite ship gate missing" }
            if ($s -notmatch [regex]::Escape('DUAL RUNTIME CHECK PASS')) { throw "dual-runtime ship gate missing" }
            if ($s -notmatch '(?i)never push main') { throw "never-push-main boundary missing" }
            if ($s -notmatch '(?i)reload-plugins') { throw "reload step missing" }
        }
    },
    @{
        Name = 'calibration: a mutated copy missing installed_plugins.json FAILS the coupling grader'
        Run = {
            $s = Get-Content $Skill -Raw
            $bad = $s -replace 'installed_plugins\.json', 'REDACTED.json'
            $survives = $true
            foreach ($c in $couplingChecks) {
                if ($bad -notmatch $c.Pat) { $survives = $false }
            }
            if ($survives) { throw "coupling grader passed a copy with installed_plugins.json removed -- dead metric" }
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
        Name = 'rationalizations: section exists and every row has a non-empty Source cell'
        Run = {
            $chk = {
                param($txt)
                $m = [regex]::Match($txt, '(?ms)^## Rationalizations\s*
(.*?)(?=^## |\z)')
                if (-not $m.Success) { return 'section missing' }
                $rows = @($m.Groups[1].Value -split "`n" | Where-Object { $_ -match '^\|' -and $_ -notmatch '^\|[-| ]+\|\s*$' } | Select-Object -Skip 1)
                if ($rows.Count -lt 1) { return 'no rows' }
                foreach ($r in $rows) {
                    $c = @($r.Trim().Trim('|') -split '\|')
                    if ($c.Count -lt 4 -or -not $c[-1].Trim()) { return "empty Source: $r" }
                }
                return $null
            }
            $s = Get-Content $Skill -Raw
            $e = & $chk $s
            if ($e) { throw $e }
            $bad = [regex]::Replace($s, '(?m)^(\| "[^
]*)\|[^|
]*\|\s*$', '$1| |')
            if (-not (& $chk $bad)) { throw 'calibration: empty-Source copy passed -- dead metric' }
        }
    }
    ,@{
        Name = 'rollback_and_go_nogo: Rollback step and GO/NO-GO line carry their required parts'
        Run = {
            $s = Get-Content $Skill -Raw
            $need = @('Rollback', 'revert the merge commit', 'patch version', 'GO/NO-GO', 'verify-loaded plan', 'matches the PR head commit')
            foreach ($n in $need) { if (-not $s.Contains($n)) { throw "missing: $n" } }
            $bad = $s.Replace('GO/NO-GO', 'REDACTED')
            if ($bad.Contains('GO/NO-GO')) { throw 'calibration: mutation did not remove the line' }
            if (-not $s.Contains('GO/NO-GO')) { throw 'GO/NO-GO line missing' }
        }
    }
)

$pass = 0; $fail = 0
foreach ($t in $tests) {
    try { & $t.Run; $pass++; Write-Host "PASS $($t.Name)" -ForegroundColor Green }
    catch { $fail++; Write-Host "FAIL $($t.Name): $_" -ForegroundColor Red }
}
if ($fail -eq 0) { Write-Host "EVAL PASS personal-plugin-release ($pass)" -ForegroundColor Green; exit 0 }
else { Write-Host "EVAL FAIL personal-plugin-release ($fail of $($pass+$fail))" -ForegroundColor Red; exit 1 }
