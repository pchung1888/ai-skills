#requires -Version 7
# Eval grader for personal-fix-decode. See evals/eval-plan.md for the failure-mode map.
# Deterministic red/green grader. Exit 0 = all checks pass; exit 1 = at least one fails.
# ASCII only (no em-dashes/smart-quotes -- Windows PowerShell 5.1 cp1252 pitfall).
$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'

$SkillDir = Resolve-Path (Join-Path $PSScriptRoot '..')
$Skill    = Join-Path $SkillDir 'SKILL.md'
$Fix      = Join-Path $PSScriptRoot 'fixtures'
$Lib      = Join-Path $SkillDir 'lib'
$Decoder  = Join-Path $Lib 'fix_decode.py'

$tests = @(
    @{
        Name = 'skill_frontmatter: SKILL.md declares the right name + a description'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?m)^name:\s*personal-fix-decode\s*$') { throw "frontmatter name not personal-fix-decode" }
            if ($s -notmatch '(?m)^description:\s*\S') { throw "frontmatter description missing" }
        }
    },
    @{
        Name = 'referential_integrity: lib/fix_decode.py referenced by SKILL.md exists on disk'
        Run = {
            if (-not (Test-Path $Decoder)) { throw "lib/fix_decode.py missing" }
            $s = Get-Content $Skill -Raw
            if ($s -notmatch [regex]::Escape('lib/fix_decode.py')) { throw "SKILL.md does not reference lib/fix_decode.py" }
        }
    },
    @{
        Name = 'decode_good_ae: decoder names TradeCaptureReport + party fields on the locked AE fixture'
        Run = {
            $out = (python $Decoder (Join-Path $Fix 'good-ae-message.txt') 2>&1) -join "`n"
            if ($LASTEXITCODE -ne 0) { throw "decoder failed on good fixture: $out" }
            if ($out -notmatch 'TradeCaptureReport') { throw "MsgType AE not decoded. Output:`n$out" }
            if ($out -notmatch 'PartyID\s+HILLTOP') { throw "tag 448 PartyID not decoded. Output:`n$out" }
            if ($out -notmatch 'ContraFirm') { throw "PartyRole 17 enum not decoded. Output:`n$out" }
        }
    },
    @{
        Name = 'decode_reject: session-reject fixture decodes RefTagID + SessionRejectReason enum'
        Run = {
            $out = (python $Decoder (Join-Path $Fix 'good-reject-message.txt') 2>&1) -join "`n"
            if ($LASTEXITCODE -ne 0) { throw "decoder failed on reject fixture: $out" }
            if ($out -notmatch 'SessionReject') { throw "MsgType 3 not decoded. Output:`n$out" }
            if ($out -notmatch 'RefTagID\s+452') { throw "tag 371 not decoded. Output:`n$out" }
            if ($out -notmatch 'ValueIsIncorrect') { throw "reason enum 5 not decoded. Output:`n$out" }
        }
    },
    @{
        Name = 'calibration_bad: non-FIX input fails loud with nonzero exit (grader that passes everything measures nothing)'
        Run = {
            $out = (python $Decoder (Join-Path $Fix 'bad-not-fix.txt') 2>&1) -join "`n"
            if ($LASTEXITCODE -eq 0) { throw "decoder accepted garbage input; expected nonzero exit. Output:`n$out" }
            if ($out -notmatch 'DECODE-FAIL') { throw "expected DECODE-FAIL marker. Output:`n$out" }
        }
    },
    @{
        Name = 'json_mode: --json output parses and carries msg_type + tag 448 row'
        Run = {
            $out = (python $Decoder (Join-Path $Fix 'good-ae-message.txt') --json 2>&1) -join "`n"
            if ($LASTEXITCODE -ne 0) { throw "--json failed: $out" }
            $j = $out | ConvertFrom-Json
            if ($j.msg_type -ne 'AE') { throw "json msg_type expected AE, got $($j.msg_type)" }
            if (-not ($j.fields | Where-Object { $_.tag -eq 448 })) { throw "json fields missing tag 448" }
        }
    }
)

$pass = 0; $fail = 0
foreach ($t in $tests) {
    try { & $t.Run; $pass++; Write-Host "PASS $($t.Name)" -ForegroundColor Green }
    catch { $fail++; Write-Host "FAIL $($t.Name): $_" -ForegroundColor Red }
}
if ($fail -eq 0) { Write-Host "EVAL PASS personal-fix-decode ($pass)" -ForegroundColor Green; exit 0 }
else { Write-Host "EVAL FAIL personal-fix-decode ($fail of $($pass+$fail))" -ForegroundColor Red; exit 1 }
