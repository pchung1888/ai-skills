#requires -Version 7
# Eval grader for personal-wizard. See evals/eval-plan.md for the failure-mode map.
# Deterministic red/green grader. Exit 0 = all checks pass; exit 1 = at least one fails.
$ErrorActionPreference = 'Stop'

$SkillDir = Resolve-Path (Join-Path $PSScriptRoot '..')
$Skill    = Join-Path $SkillDir 'SKILL.md'
$Template = Join-Path $SkillDir 'template.ps1'

$tests = @(
    @{
        Name = 'skill_frontmatter: name, description and the template reference are present'
        Run = {
            $s = Get-Content $Skill -Raw
            if ($s -notmatch '(?m)^name:\s*personal-wizard\s*$') { throw "frontmatter name not personal-wizard" }
            if ($s -notmatch '(?m)^description:\s*\S') { throw "frontmatter description missing" }
            if ($s -notmatch [regex]::Escape('template.ps1')) { throw "SKILL.md does not point at template.ps1" }
            if (-not (Test-Path $Template)) { throw "template.ps1 missing" }
        }
    },
    @{
        Name = 'template_ascii_and_parses: template.ps1 is pure ASCII and parses with no errors'
        Run = {
            $bad = @([System.IO.File]::ReadAllBytes($Template) | Where-Object { $_ -gt 127 }).Count
            if ($bad) { throw "$bad non-ASCII bytes in template.ps1 (Windows PowerShell 5.1 misreads them)" }
            $errs = $null
            [void][System.Management.Automation.Language.Parser]::ParseFile($Template, [ref]$null, [ref]$errs)
            if ($errs) { throw "template.ps1 parse errors: $($errs[0].Message)" }
        }
    },
    @{
        Name = 'template_library_intact: the STAGES marker and every documented helper exist'
        Run = {
            $t = Get-Content $Template -Raw
            if ($t -notmatch '(?m)^# STAGES:') { throw "STAGES marker missing" }
            foreach ($f in @('Start-Stage','Say','Step','Note','Warn','Open-Target','Ask','Ask-Secret','Save-Value','Wait-Step','Confirm-Step','Show-Banner','Show-Finish')) {
                if ($t -notmatch "(?m)^function $([regex]::Escape($f))\b") { throw "library function missing: $f" }
            }
        }
    },
    @{
        Name = 'save_value_upserts: saving a key twice keeps one line with the new value'
        Run = {
            $t = Get-Content $Template -Raw
            $lib = $t.Substring(0, $t.IndexOf('# STAGES:'))
            $cap = Join-Path ([System.IO.Path]::GetTempPath()) "wizard-eval-$(Get-Random).txt"
            $libFile = Join-Path ([System.IO.Path]::GetTempPath()) "wizard-lib-$(Get-Random).ps1"
            Set-Content -LiteralPath $libFile -Value $lib -Encoding ASCII
            try {
                $env:WIZARD_CAPTURE_FILE = $cap
                $out = pwsh -NoProfile -Command ". '$libFile'; Save-Value 'K' 'a' *> `$null; Save-Value 'K' 'b' *> `$null; Save-Value 'J' 'c' *> `$null; Get-SavedValue 'K'" 2>&1 | Out-String
                if ($out.Trim() -ne 'b') { throw "Get-SavedValue K returned '$($out.Trim())', expected 'b'" }
                $lines = @(Get-Content -LiteralPath $cap)
                if ($lines.Count -ne 2) { throw "capture file has $($lines.Count) lines, expected 2 (K and J)" }
            } finally {
                Remove-Item Env:\WIZARD_CAPTURE_FILE -ErrorAction SilentlyContinue
                Remove-Item $cap, $libFile -ErrorAction SilentlyContinue
            }
        }
    },
    @{
        Name = 'secrets_encrypted_at_rest: a key read with Ask-Secret is saved DPAPI-encrypted and reads back intact'
        Run = {
            $t = Get-Content $Template -Raw
            $lib = $t.Substring(0, $t.IndexOf('# STAGES:'))
            $cap = Join-Path ([System.IO.Path]::GetTempPath()) "wizard-eval-$(Get-Random).txt"
            $libFile = Join-Path ([System.IO.Path]::GetTempPath()) "wizard-lib-$(Get-Random).ps1"
            Set-Content -LiteralPath $libFile -Value $lib -Encoding ASCII
            try {
                $env:WIZARD_CAPTURE_FILE = $cap
                # Mark the key secret the way Ask-Secret does, without needing keyboard input.
                $out = pwsh -NoProfile -Command ". '$libFile'; [void]`$script:SecretKeys.Add('PW'); Save-Value 'PW' 'Pl41n-S3cret' *> `$null; Get-SavedValue 'PW'" 2>&1 | Out-String
                if ($out.Trim() -ne 'Pl41n-S3cret') { throw "secret did not read back intact: '$($out.Trim())'" }
                $raw = Get-Content -LiteralPath $cap -Raw
                if ($raw -match 'Pl41n-S3cret') { throw "secret is stored as plain text in the capture file" }
                if ($raw -notmatch '(?m)^PW=dpapi:') { throw "secret line is not marked dpapi:" }
            } finally {
                Remove-Item Env:\WIZARD_CAPTURE_FILE -ErrorAction SilentlyContinue
                Remove-Item $cap, $libFile -ErrorAction SilentlyContinue
            }
        }
    },
    @{
        Name = 'shared_server_rule: SKILL.md keeps back-up-first, approval and the Confirm-Step gate'
        Run = {
            $s = Get-Content $Skill -Raw
            foreach ($k in @('back up any DLL or config before', 'approval', 'Confirm-Step', 'Never invent a step', 'Do not run it yourself')) {
                if ($s -notmatch [regex]::Escape($k)) { throw "SKILL.md lost: $k" }
            }
        }
    }
)

$pass = 0; $fail = 0
foreach ($t in $tests) {
    try { & $t.Run; $pass++; Write-Host "PASS $($t.Name)" -ForegroundColor Green }
    catch { $fail++; Write-Host "FAIL $($t.Name): $_" -ForegroundColor Red }
}
if ($fail -eq 0) { Write-Host "EVAL PASS personal-wizard ($pass)" -ForegroundColor Green; exit 0 }
else { Write-Host "EVAL FAIL personal-wizard ($fail of $($pass+$fail))" -ForegroundColor Red; exit 1 }
