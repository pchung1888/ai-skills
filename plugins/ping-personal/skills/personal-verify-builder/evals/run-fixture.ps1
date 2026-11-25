#requires -Version 7
# Tier 2 behavior eval for personal-verify-builder (see evals/eval-plan.md, failure mode 13).
# A headless claude session follows `create` on a copy of fixtures/tiny-ledger. The generated
# "Run all checks" command must pass on clean code, stay green on a neutral edit, fail on each
# planted bug, and pass after revert. Costs one headless session, so run-all.ps1 skips it.
# Prints FIXTURE PASS or FIXTURE FAIL.
#
# Usage:
#   pwsh plugins/ping-personal/skills/personal-verify-builder/evals/run-fixture.ps1
#   pwsh .../run-fixture.ps1 -Model opus -Keep     # keep the temp repo to inspect it
[CmdletBinding()]
param([string]$Model = 'sonnet', [switch]$Keep, [int]$CheckTimeoutSec = 300, [int]$SessionTimeoutSec = 1800)

$ErrorActionPreference = 'Stop'
$SkillDir = Resolve-Path (Join-Path $PSScriptRoot '..')
$Fixture  = Join-Path $PSScriptRoot 'fixtures\tiny-ledger'
$Port     = 8765

# Each edit: file, text to find, replacement, and whether the runner must go red.
# Keep the bug sites in step with fixture_oracle in eval.ps1.
$Edits = @(
    @{ Name = 'neutral comment';           File = 'queries.py'; From = 'GROUP BY symbol'; To = "GROUP BY symbol -- neutral edit"; Red = $false },
    @{ Name = 'SQL counts cancelled';      File = 'queries.py'; From = "WHERE status = 'open'"; To = 'WHERE 1 = 1'; Red = $true },
    @{ Name = 'page total drops rows';     File = 'app.py';     From = 'sum(r[2] for r in rows)'; To = 'sum(r[2] for r in rows[:1])'; Red = $true }
)

$fails = [System.Collections.Generic.List[string]]::new()
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$root  = Join-Path ([IO.Path]::GetTempPath()) "verify-builder-fixture-$stamp"
$work  = Join-Path $root 'repo'

function Invoke-Native([string]$what, [scriptblock]$cmd) {
    $out = & $cmd 2>&1
    if ($LASTEXITCODE -ne 0) { throw "$what failed (exit $LASTEXITCODE): $out" }
    return $out
}

function Get-PortListeners { @((Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue).OwningProcess | Sort-Object -Unique) }

# Stop listeners on the fixture port that appeared after this run began (the start-up snapshot
# in $PreexistingPids is never touched). Returns how many it stopped.
function Stop-OwnedListeners {
    $n = 0
    foreach ($p in Get-PortListeners) {
        if ($script:PreexistingPids -notcontains $p) { Stop-Process -Id $p -Force -ErrorAction SilentlyContinue; $n++ }
    }
    return $n
}

function Invoke-Runner([string]$cmd) {
    $job = Start-Job -ScriptBlock { param($d, $c) Set-Location $d; pwsh -NoProfile -Command $c *> $null; $LASTEXITCODE } -ArgumentList $work, $cmd
    $code = if (Wait-Job $job -Timeout $CheckTimeoutSec) { Receive-Job $job } else { Stop-Job $job; 'timeout' }
    Remove-Job $job -Force
    if ((Stop-OwnedListeners) -gt 0) { $script:fails.Add("runner left a server on port $Port after: $cmd") }
    return $code
}

function Get-Frontmatter([string]$text) {
    $m = [regex]::Match($text, '\A---\r?\n(?<fm>.*?)\r?\n---\r?\n', 'Singleline')
    if ($m.Success) { return $m.Groups['fm'].Value } else { return $null }
}

$PreexistingPids = Get-PortListeners
if ($PreexistingPids.Count) { Write-Host "FIXTURE FAIL: port $Port is already in use by PID $($PreexistingPids -join ', '); free it first" -ForegroundColor Red; exit 1 }

New-Item -ItemType Directory -Path $work | Out-Null
Push-Location $work
try {
    # The agent under test reads a copy of the skill, so it cannot edit the real source.
    $skillCopy = Join-Path $root 'skill-copy'
    Copy-Item -Path $SkillDir -Destination $skillCopy -Recurse
    Copy-Item -Path (Join-Path $Fixture '*') -Destination $work -Recurse
    Set-Content -Path (Join-Path $work '.gitignore') -Value "ledger.db`n*.log`n__pycache__/" -NoNewline
    Invoke-Native 'git init' { git init -q } | Out-Null
    Invoke-Native 'git add' { git add -A } | Out-Null
    Invoke-Native 'git commit' { git -c user.email=eval@local -c user.name=eval commit -qm fixture } | Out-Null
    $base = (Invoke-Native 'git rev-parse' { git rev-parse HEAD }).Trim()

    # Headless Claude Code refuses file-tool writes under .claude/ even with allow rules, so
    # .claude/skills/verify is a junction to _verify_staging/, which the agent may write.
    $staging = Join-Path $work '_verify_staging'
    New-Item -ItemType Directory -Path $staging | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $work '.claude\skills') -Force | Out-Null
    New-Item -ItemType Junction -Path (Join-Path $work '.claude\skills\verify') -Target $staging | Out-Null
    $settings = Join-Path $root 'settings.json'
    @{ permissions = @{ allow = @(
        'Edit(./_verify_staging/**)', 'Edit(./.gitignore)',
        'Bash(python *)', 'Bash(curl *)', 'Bash(git *)', 'Bash(mkdir *)', 'Bash(ls *)', 'Bash(cat *)', 'Bash(sleep *)'
    ) } } | ConvertTo-Json -Depth 4 | Set-Content $settings

    $prompt = @"
Read the skill at $skillCopy\SKILL.md and its references, then follow its create mode on the repo
in the current folder. Work only inside this folder. This is a local fixture: there are no shared
servers. If you start the app, use port $Port and stop it when you finish. Do not commit.
This headless run cannot write under .claude/ with file tools. The folder .claude/skills/verify
is a junction to _verify_staging/ at the repo root: write the generated skill's files into
_verify_staging/, and inside the files refer to them as .claude/skills/verify/ as usual. Run
commands through the .claude/skills/verify/ path. End with the hand-off table.
"@
    $log = Join-Path $root 'claude.log'
    Write-Host "Running headless create in $work (model $Model, limit $SessionTimeoutSec s)..."
    $pidFile = Join-Path $root 'session.pid'
    $session = Start-Job -ScriptBlock {
        param($d, $p, $m, $s, $k, $l, $pf)
        Set-Content $pf $PID
        Set-Location $d
        $null | claude -p $p --model $m --permission-mode acceptEdits --settings $s --add-dir $k *> $l
        $LASTEXITCODE
    } -ArgumentList $work, $prompt, $Model, $settings, $skillCopy, $log, $pidFile
    if (-not (Wait-Job $session -Timeout $SessionTimeoutSec)) {
        # Stop-Job alone can leave claude running; kill the job host's whole process tree.
        if (Test-Path $pidFile) { taskkill /T /F /PID (Get-Content $pidFile) *> $null }
        Stop-Job $session
        throw "headless session passed $SessionTimeoutSec s; process tree stopped"
    }
    $exit = Receive-Job $session
    Write-Host "Headless session exit code $exit; log: $log"
    if ("$exit" -ne '0') { $fails.Add("headless session exited $exit") }
    Remove-Job $session -Force
    if ((Stop-OwnedListeners) -gt 0) { $fails.Add("the create session left a server on port $Port") }

    if ([int](Invoke-Native 'git rev-list' { git rev-list --count "$base..HEAD" }) -ne 0) { $fails.Add('the agent committed') }
    $productDiff = Invoke-Native 'git diff' { git diff $base --name-only -- app.py queries.py seed.py }
    if ($productDiff) { $fails.Add("product code changed: $productDiff") }

    $gen = Join-Path $work '.claude\skills\verify\SKILL.md'
    if (-not (Test-Path $gen)) { $fails.Add('no .claude/skills/verify/SKILL.md written') }
    else {
        $g  = Get-Content $gen -Raw
        $fm = Get-Frontmatter $g
        if ($null -eq $fm) { $fails.Add('generated SKILL.md has no --- frontmatter block') }
        elseif ($fm -notmatch '(?m)^name:\s*verify\s*$') { $fails.Add('generated skill is not named exactly verify') }
        if ($fm -match '(?m)^disable-model-invocation:') { $fails.Add('generated skill sets disable-model-invocation') }
        if (-not (Get-ChildItem (Join-Path $work '.claude\skills\verify\features') -Filter *.md -ErrorAction SilentlyContinue)) { $fails.Add('no features/*.md written') }
        foreach ($k in 'Proof it can fail', 'Synced at', '## Safety') { if ($g -cnotmatch [regex]::Escape($k)) { $fails.Add("generated SKILL.md lacks: $k") } }
        if ((Get-Content (Join-Path $work '.gitignore') -Raw) -notmatch [regex]::Escape('.claude/verify-evidence/')) { $fails.Add('.gitignore lacks .claude/verify-evidence/') }

        $m = [regex]::Match($g, '(?s)## Run all checks\s*```[A-Za-z0-9]*\s*\r?\n(?<cmd>.*?)\r?\n```')
        if (-not $m.Success) { $fails.Add('no code block under ## Run all checks') }
        elseif ($m.Groups['cmd'].Value.Trim() -match '\n') { $fails.Add('runner command is not a single line') }
        else {
            $cmd = $m.Groups['cmd'].Value.Trim()
            Write-Host "Runner: $cmd"
            $clean = Invoke-Runner $cmd
            Write-Host ("  {0,-24} -> {1} (want 0)" -f 'clean code', $clean)
            if ("$clean" -ne '0') { $fails.Add("runner not green on clean code ($clean)") }

            foreach ($e in $Edits) {
                $path = Join-Path $work $e.File
                $text = Get-Content $path -Raw
                if (-not $text.Contains($e.From)) { $fails.Add("edit site missing for '$($e.Name)'"); continue }
                $text.Replace($e.From, $e.To) | Set-Content $path -NoNewline
                $code = Invoke-Runner $cmd
                Invoke-Native "revert $($e.File)" { git checkout -q $base -- $e.File } | Out-Null
                if ($e.Red) {
                    Write-Host ("  {0,-24} -> {1} (want a non-zero exit code)" -f $e.Name, $code)
                    if (-not ("$code" -match '^-?\d+$' -and [int]$code -ne 0)) { $fails.Add("runner did not exit non-zero on '$($e.Name)' ($code)") }
                } else {
                    Write-Host ("  {0,-24} -> {1} (want 0)" -f $e.Name, $code)
                    if ("$code" -ne '0') { $fails.Add("runner went red on '$($e.Name)', which changes no behavior ($code)") }
                }
            }

            $again = Invoke-Runner $cmd
            Write-Host ("  {0,-24} -> {1} (want 0)" -f 'after revert', $again)
            if ("$again" -ne '0') { $fails.Add("runner not green after revert ($again)") }
        }
    }
}
catch { $fails.Add("harness error: $_") }
finally {
    Stop-OwnedListeners | Out-Null
    Pop-Location
}

if ($fails.Count -eq 0) {
    if (-not $Keep) { Remove-Item $root -Recurse -Force -ErrorAction SilentlyContinue }
    Write-Host 'FIXTURE PASS personal-verify-builder' -ForegroundColor Green; exit 0
}
$fails | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
Write-Host "FIXTURE FAIL personal-verify-builder (kept $root)" -ForegroundColor Red; exit 1
