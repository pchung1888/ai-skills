#requires -Version 7
# Switches the permission mode that NEW Claude Code sessions start in, for any repo.
# Edits only <repo>\.claude\settings.local.json: permissions.defaultMode and permissions.ask.
# Usage: pwsh -NoProfile -File Set-PermissionMode.ps1 -Mode <bypass|auto|status|restore> [-Repo <folder>]
#   bypass  = new sessions start in bypassPermissions; the ask rules and the old defaultMode are parked
#   auto    = put back the parked defaultMode and ask rules (no defaultMode = the user default, auto)
#   status  = show the mode and what can still prompt in bypass, change nothing
#   restore = put back the whole file as it was before bypass first went on (good.json), if a toggle broke it
# Backups: at most three files per repo, however often the mode is toggled (see "Backups" below).
# Example: pwsh -NoProfile -File Set-PermissionMode.ps1 -Mode bypass -Repo "D:\work\my-repo"
# Running sessions keep their mode: use Shift+Tab, or the ping-hud Bypass button for a live toggle.
param(
    [Parameter(Mandatory = $true)][ValidateSet('bypass', 'auto', 'status', 'restore')][string]$Mode,
    # Repo folder. Default: the git top folder of the current folder, else the current folder.
    [string]$Repo,
    # Where parked values and backups go. Default: ~/.claude/backups/permission-mode. Tests pass a temp folder.
    [string]$StateRoot = (Join-Path $HOME '.claude/backups/permission-mode'),
    # More policy files to check, on top of the managed locations that are always checked. Tests pass a temp file.
    [string[]]$ExtraManagedPaths = @()
)
# Every known managed-settings location, always checked; a file that does not exist is skipped.
$ManagedPaths = @('C:/Program Files/ClaudeCode/managed-settings.json', (Join-Path ($env:ProgramData ?? 'C:/ProgramData') 'ClaudeCode/managed-settings.json'),
    '/Library/Application Support/ClaudeCode/managed-settings.json', '/etc/claude-code/managed-settings.json') + $ExtraManagedPaths
$ErrorActionPreference = 'Stop'

if (-not $Repo) {
    $top = git rev-parse --show-toplevel 2>$null
    $Repo = if ($LASTEXITCODE -eq 0 -and $top) { $top } else { (Get-Location).Path }
}
$Repo = (Resolve-Path -LiteralPath $Repo).Path
$claudeDir = Join-Path $Repo '.claude'
$local = Join-Path $claudeDir 'settings.local.json'

function Read-Json([string]$path) {
    if (-not (Test-Path -LiteralPath $path)) { return @{} }
    $raw = Get-Content -LiteralPath $path -Raw
    if (-not $raw.Trim()) { return @{} }
    return $raw | ConvertFrom-Json -AsHashtable
}
function Count-Ask($s) { if ($s.permissions -and $s.permissions.ask) { @($s.permissions.ask).Count } else { 0 } }
function Count-PreToolUse($s) { if ($s.hooks -and $s.hooks.PreToolUse) { @($s.hooks.PreToolUse | ForEach-Object { $_.hooks }).Count } else { 0 } }
function Mode-Of($s) { if ($s.permissions -and $s.permissions.defaultMode) { $s.permissions.defaultMode } else { '(none: user default)' } }

# One state folder per repo: the folder name plus a hash of the full path, so two repos never share one.
$sha = [System.Security.Cryptography.SHA256]::Create()
$hash = -join ($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($Repo.ToLowerInvariant()))[0..3] | ForEach-Object { $_.ToString('x2') })
$state = Join-Path $StateRoot ("{0}-{1}" -f ((Split-Path $Repo -Leaf) -replace '[^\w.-]', '_'), $hash)
$stash = Join-Path $state 'parked.json'
# Backups: three fixed names, each overwritten in place, so toggling never adds files.
#   last.json   = settings.local.json as it was before the latest run
#   good.json   = settings.local.json as it was before bypass went on from a normal state (kept through toggles)
#   parked.json = the defaultMode and ask rules bypass moved out (deleted by auto)
$last = Join-Path $state 'last.json'
$good = Join-Path $state 'good.json'

# Restore runs before the current file is parsed, so it also repairs a file that is no longer valid JSON.
if ($Mode -eq 'restore') {
    if (-not (Test-Path -LiteralPath $good)) { Write-Error "Nothing to restore: no good.json in $state. Bypass was never turned on here." }
    $null = Read-Json $good   # proves the copy is valid JSON before it replaces anything
    New-Item -ItemType Directory -Force $claudeDir | Out-Null
    if (Test-Path -LiteralPath $local) { Copy-Item -LiteralPath $local -Destination $last -Force }
    Copy-Item -LiteralPath $good -Destination $local -Force
    if (Test-Path -LiteralPath $stash) { Remove-Item -LiteralPath $stash }
    "Repo: $Repo"
    "Restored settings.local.json from $good"
    "Now: $(Mode-Of (Read-Json $local)). The file before this restore is in $last."
    exit 0
}

$json = Read-Json $local
$before = Mode-Of $json

if ($Mode -eq 'status') {
    $project = Read-Json (Join-Path $claudeDir 'settings.json')
    $user = Read-Json (Join-Path $HOME '.claude/settings.json')
    "Repo: $Repo"
    "New sessions start in: $before$(if (Test-Path -LiteralPath $stash) { '   (set by personal-bypass; -Mode auto puts the old value back)' })"
    "Ask rules (these prompt even in bypass): local $(Count-Ask $json), project $(Count-Ask $project), user $(Count-Ask $user)"
    "PreToolUse hooks (can still ask in bypass): project $(Count-PreToolUse $project), local $(Count-PreToolUse $json), user $(Count-PreToolUse $user)"
    if ($user.permissions -and $user.permissions.disableBypassPermissionsMode) { "WARNING: user settings set disableBypassPermissionsMode, so bypass cannot start." }
    if ((Test-Path (Join-Path $Repo '.git')) -and (Test-Path -LiteralPath $local)) {
        git -C $Repo check-ignore -q -- '.claude/settings.local.json' 2>$null
        if ($LASTEXITCODE -ne 0) { "WARNING: .claude/settings.local.json is not git-ignored in this repo; do not commit it." }
    }
    exit 0
}

if ($Mode -eq 'bypass') {
    # Settings that forbid bypass win: user, project, local, and every managed policy file.
    $sources = @((Join-Path $HOME '.claude/settings.json'), (Join-Path $claudeDir 'settings.json'), $local) + $ManagedPaths
    foreach ($src in $sources) {
        $s = Read-Json $src
        if ($s.permissions -and $s.permissions.disableBypassPermissionsMode) { Write-Error "Refused: $src sets permissions.disableBypassPermissionsMode." }
    }
    # A tracked settings.local.json would carry bypass into a commit for everyone.
    if (Test-Path (Join-Path $Repo '.git')) {
        git -C $Repo ls-files --error-unmatch -- '.claude/settings.local.json' *> $null
        if ($LASTEXITCODE -eq 0) { Write-Error "Refused: git tracks .claude/settings.local.json in $Repo. Untrack it first." }
    }
}

New-Item -ItemType Directory -Force $state | Out-Null
$current = if (Test-Path -LiteralPath $local) { Get-Content -LiteralPath $local -Raw } else { '{}' }
Set-Content -LiteralPath $last -Value $current -NoNewline -Encoding utf8NoBOM
# The good copy is taken only when bypass goes on from a normal state; repeat toggles keep it.
if ($Mode -eq 'bypass' -and -not (Test-Path -LiteralPath $stash)) { Set-Content -LiteralPath $good -Value $current -NoNewline -Encoding utf8NoBOM }
if (-not $json.ContainsKey('permissions')) { $json['permissions'] = @{} }
$perm = $json['permissions']

if ($Mode -eq 'bypass') {
    # Park the original values once; a second bypass keeps the first parked copy.
    if (-not (Test-Path -LiteralPath $stash)) {
        $parked = @{ defaultMode = $perm['defaultMode']; ask = @($perm['ask'] | Where-Object { $_ }) }
        ConvertTo-Json -InputObject $parked -Depth 5 | Set-Content -LiteralPath $stash -Encoding utf8NoBOM
    }
    $perm['defaultMode'] = 'bypassPermissions'
    $perm['ask'] = @()
} else {
    if (Test-Path -LiteralPath $stash) {
        $parked = Get-Content -LiteralPath $stash -Raw | ConvertFrom-Json -AsHashtable
        if ($parked.defaultMode) { $perm['defaultMode'] = $parked.defaultMode } else { [void]$perm.Remove('defaultMode') }
        # Ask rules added while in bypass are kept, after the parked ones.
        $perm['ask'] = @(@($parked.ask) + @($perm['ask']) | Where-Object { $_ } | Select-Object -Unique)
        Remove-Item -LiteralPath $stash
    } elseif ($perm['defaultMode'] -eq 'bypassPermissions') {
        [void]$perm.Remove('defaultMode')
    }
    if ($perm.ContainsKey('ask') -and @($perm['ask']).Count -eq 0) { [void]$perm.Remove('ask') }
}

New-Item -ItemType Directory -Force $claudeDir | Out-Null
$json | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $local -Encoding utf8NoBOM

# Re-read to prove the file is still valid JSON and the change landed.
$check = Read-Json $local
"Repo: $Repo"
"Was: $before"
"Now: $(Mode-Of $check)   (allow: $(@($check.permissions.allow | Where-Object { $_ }).Count), deny: $(@($check.permissions.deny | Where-Object { $_ }).Count), ask: $(Count-Ask $check))"
"Backups: $state (last.json = before this run$(if (Test-Path -LiteralPath $good) { '; good.json = before bypass, for -Mode restore' }))"
"New sessions use the new mode. Running sessions: Shift+Tab, or the ping-hud Bypass button."
