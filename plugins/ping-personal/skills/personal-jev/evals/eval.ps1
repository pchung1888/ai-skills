#requires -Version 7
# Eval grader for personal-jev. See evals/eval-plan.md for the failure-mode map.
# Deterministic red/green grader. Exit 0 = all checks pass; exit 1 = at least one fails.
# Runnable standalone OR from plugins/ping-personal/evals/run-all.ps1 (auto-discovered by glob).
# NEVER hits the real API: answers come from -Fake fixtures; network tests use a local listener.
# ASCII only.

$ErrorActionPreference = 'Stop'

$SkillDir = Resolve-Path (Join-Path $PSScriptRoot '..')
$Skill    = Join-Path $SkillDir 'SKILL.md'
$Jev      = Join-Path $SkillDir 'jev.ps1'
$Fix      = Join-Path $PSScriptRoot 'fixtures'
$Sentinel = 'SENTINELKEY0123456789SENTINELKEY'

function Invoke-Jev([string[]]$ArgList) {
    # Default every run to a dead local port so even a mutated/broken jev.ps1 can never reach
    # the real API from the eval (found by the F08 mutation run).
    if ($ArgList -notcontains '-Endpoint') { $ArgList += @('-Endpoint', 'http://127.0.0.1:9/v1/systemone', '-TimeoutSec', '2') }
    $prev = $env:TYPESAFE_API_KEY
    $env:TYPESAFE_API_KEY = $Sentinel
    try { $out = (& pwsh -NoProfile -File $Jev @ArgList 2>&1) -join "`n"; $code = $LASTEXITCODE }
    finally { $env:TYPESAFE_API_KEY = $prev }
    [pscustomobject]@{ out = $out; code = $code }
}
function F([string]$n) { Join-Path $Fix $n }
function New-Tmp([string]$tag) { Join-Path ([System.IO.Path]::GetTempPath()) "jev-$tag-$([guid]::NewGuid().ToString('N'))" }
# Fingerprint the script prints for a payload (read from the -Json preview).
function Get-Fp([string]$path) { ((Invoke-Jev @('-Payload', $path, '-Json')).out | ConvertFrom-Json).fingerprint }
# Run with NO key in the env and cwd in an empty temp folder: only -KeyFile can supply a key.
function Invoke-JevNoEnvKey([string[]]$ArgList) {
    $prev = $env:TYPESAFE_API_KEY; $env:TYPESAFE_API_KEY = $null
    $cwd = New-Tmp 'cwd'; $null = New-Item -ItemType Directory -Path $cwd
    Push-Location $cwd
    try { $out = (& pwsh -NoProfile -File $Jev @ArgList 2>&1) -join "`n"; $code = $LASTEXITCODE }
    finally { Pop-Location; Remove-Item -LiteralPath $cwd -Recurse -Force; $env:TYPESAFE_API_KEY = $prev }
    [pscustomobject]@{ out = $out; code = $code }
}
function Assert-NoKey($r, [string]$where) { if ($r.out -match $Sentinel) { throw "API key printed on $where path" } }

# Local TCP listener: proves whether jev.ps1 attempted a connection.
function Test-Connects([string[]]$ArgList) {
    $l = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
    $l.Start()
    try {
        $port = $l.LocalEndpoint.Port
        $r = Invoke-Jev ($ArgList + @('-Endpoint', "http://127.0.0.1:$port/v1/systemone", '-TimeoutSec', '2'))
        [pscustomobject]@{ r = $r; connected = $l.Pending() }
    }
    finally { $l.Stop() }
}

$tests = @(
    @{ Name = 'F07 skill_frontmatter: name personal-jev + model + description'
       Run = {
           $s = Get-Content $Skill -Raw
           if ($s -notmatch '(?m)^name:\s*personal-jev\s*$') { throw 'frontmatter name not personal-jev' }
           if ($s -notmatch '(?m)^model:\s*\S')              { throw 'frontmatter model missing' }
           if ($s -notmatch '(?m)^description:\s*\S')        { throw 'frontmatter description missing' }
       } },
    @{ Name = 'F07 referential_integrity: SKILL.md references jev.ps1 and it exists'
       Run = {
           if ((Get-Content $Skill -Raw) -notmatch 'jev\.ps1') { throw 'SKILL.md does not reference jev.ps1' }
           if (-not (Test-Path -LiteralPath $Jev)) { throw 'jev.ps1 missing' }
       } },
    @{ Name = 'F01 preview_is_default: no -Send => exit 0, "preview only", NO connection attempt'
       Run = {
           $t = Test-Connects @('-Payload', (F 'clean.json'))
           if ($t.r.code -ne 0) { throw "exit $($t.r.code)" }
           if ($t.r.out -notmatch 'Preview only') { throw 'no preview-only notice' }
           if ($t.connected) { throw 'connection attempted without -Send' }
       } },
    @{ Name = 'F01 control: -Send DOES connect (proves the listener detects a send)'
       Run = {
           $t = Test-Connects @('-Payload', (F 'clean.json'), '-Send', '-Approve', (Get-Fp (F 'clean.json')), '-ReceiptDir', (New-Tmp 'rcpt'))
           if (-not $t.connected) { throw 'listener saw no connection on -Send; F01 would be vacuous' }
           if ($t.r.code -ne 5) { throw "expected HTTP error exit 5 on unanswered send, got $($t.r.code)" }
           Assert-NoKey $t.r 'HTTP-error'
       } },
    @{ Name = 'F02 leak_tripwire: every leaky fixture refused with exit 4, no connection'
       Run = {
           foreach ($n in 'email', 'company', 'guid', 'connstr', 'sql', 'sproc', 'key') {
               $t = Test-Connects @('-Payload', (F "leak-$n.json"), '-Send')
               if ($t.r.code -ne 4) { throw "leak-$n.json: expected exit 4, got $($t.r.code)" }
               if ($t.connected) { throw "leak-$n.json: connection attempted despite leak" }
           }
       } },
    @{ Name = 'F02 no_false_positive: clean payload and plain-English "select from" pass'
       Run = {
           $r = Invoke-Jev @('-Payload', (F 'clean.json'))
           if ($r.code -ne 0) { throw "clean.json exit $($r.code): $($r.out)" }
           $tmp = Join-Path ([System.IO.Path]::GetTempPath()) "jev-fp-$([guid]::NewGuid().ToString('N')).json"
           '{ "state": "Which option should I select from these three? The server team prefers speed.", "questions": { "q": { "type": "noul", "instructions": "Is speed the priority?" } } }' | Set-Content -LiteralPath $tmp
           try { $r = Invoke-Jev @('-Payload', $tmp) } finally { Remove-Item -LiteralPath $tmp -Force }
           if ($r.code -ne 0) { throw "plain English tripped the wire: $($r.out)" }
       } },
    @{ Name = 'F03 key_never_printed: preview, fake, and -Json paths'
       Run = {
           Assert-NoKey (Invoke-Jev @('-Payload', (F 'clean.json'))) 'preview'
           Assert-NoKey (Invoke-Jev @('-Payload', (F 'clean.json'), '-Fake', (F 'answers-split.json'))) 'fake'
           Assert-NoKey (Invoke-Jev @('-Payload', (F 'clean.json'), '-Fake', (F 'answers-split.json'), '-Json')) 'json'
       } },
    @{ Name = 'F04 shape_check: bad score levels, noul keys, type, non-ASCII => exit 3'
       Run = {
           foreach ($n in 'bad-score-1level', 'bad-score-11levels', 'bad-noul-keys', 'bad-type', 'bad-nonascii') {
               $r = Invoke-Jev @('-Payload', (F "$n.json"))
               if ($r.code -ne 3) { throw "$n.json: expected exit 3, got $($r.code)" }
           }
       } },
    @{ Name = 'F05 math: score 2 of top 3 => 0.67; composites 0.67 / 1'
       Run = {
           $o = (Invoke-Jev @('-Payload', (F 'clean.json'), '-Fake', (F 'answers-confident.json'), '-Weights', (F 'weights.json'), '-Json')).out | ConvertFrom-Json
           $s = $o.results | Where-Object id -eq 'deploy_now__safety'
           if ($s.normalized -ne 0.67) { throw "normalized $($s.normalized), expected 0.67" }
           if ($o.composites.deploy_now -ne 0.67) { throw "composite deploy_now $($o.composites.deploy_now)" }
           if ($o.composites.wait_for_qa -ne 1) { throw "composite wait_for_qa $($o.composites.wait_for_qa)" }
       } },
    @{ Name = 'F06 your_call: split (0.48 / noul 0.52) flagged; confident (0.81 / 0.93) not'
       Run = {
           $split = (Invoke-Jev @('-Payload', (F 'clean.json'), '-Fake', (F 'answers-split.json'), '-Json')).out | ConvertFrom-Json
           if (@($split.yourCall) -notcontains 'pick' -or @($split.yourCall) -notcontains 'reversible') { throw "split yourCall = $($split.yourCall -join ',')" }
           $conf = (Invoke-Jev @('-Payload', (F 'clean.json'), '-Fake', (F 'answers-confident.json'), '-Json')).out | ConvertFrom-Json
           if (@($conf.yourCall).Count) { throw "confident run flagged: $($conf.yourCall -join ',')" }
           $txt = (Invoke-Jev @('-Payload', (F 'clean.json'), '-Fake', (F 'answers-split.json'))).out
           if ($txt -notmatch 'YOUR CALL') { throw 'text output lacks YOUR CALL' }
       } },
    @{ Name = 'F09 approval_bind: -Send without, with wrong, or with stale fingerprint => exit 6, no connection'
       Run = {
           $fp = Get-Fp (F 'clean.json')
           if ($fp -notmatch '^[0-9a-f]{12}$') { throw "bad fingerprint '$fp'" }
           if ((Get-Fp (F 'clean.json')) -ne $fp) { throw 'fingerprint not deterministic' }
           $edited = (New-Tmp 'edit') + '.json'
           (Get-Content (F 'clean.json') -Raw).Replace('one day', 'two days') | Set-Content -LiteralPath $edited
           try {
               foreach ($case in @(@{ n = 'no -Approve'; a = @('-Payload', (F 'clean.json'), '-Send') },
                                   @{ n = 'wrong -Approve'; a = @('-Payload', (F 'clean.json'), '-Send', '-Approve', '000000000000') },
                                   @{ n = 'payload edited after preview'; a = @('-Payload', $edited, '-Send', '-Approve', $fp) })) {
                   $t = Test-Connects $case.a
                   if ($t.r.code -ne 6) { throw "$($case.n): expected exit 6, got $($t.r.code)" }
                   if ($t.connected) { throw "$($case.n): connection attempted" }
                   if ($t.r.out -match $fp) { throw "$($case.n): error message leaks the correct fingerprint" }
               }
           } finally { Remove-Item -LiteralPath $edited -Force }
       } },
    @{ Name = 'F10 key_file: key found via -KeyFile outside the cwd; none anywhere => exit 1; key never printed'
       Run = {
           $kf = (New-Tmp 'key') + '.env'
           "TYPESAFE_API_KEY=$Sentinel" | Set-Content -LiteralPath $kf
           $l = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0); $l.Start()
           try {
               $r = Invoke-JevNoEnvKey @('-Payload', (F 'clean.json'), '-Send', '-Approve', (Get-Fp (F 'clean.json')), '-KeyFile', $kf,
                   '-ReceiptDir', (New-Tmp 'rcpt'), '-Endpoint', "http://127.0.0.1:$($l.LocalEndpoint.Port)/v1/systemone", '-TimeoutSec', '2')
               if (-not $l.Pending()) { throw "no connection: key file not used ($($r.out))" }
               if ($r.code -ne 5) { throw "expected exit 5 from the silent listener, got $($r.code)" }
               Assert-NoKey $r 'key-file'
           } finally { $l.Stop(); Remove-Item -LiteralPath $kf -Force }
           $r = Invoke-JevNoEnvKey @('-Payload', (F 'clean.json'), '-Send', '-Approve', (Get-Fp (F 'clean.json')), '-KeyFile', (New-Tmp 'nokey'),
               '-Endpoint', 'http://127.0.0.1:9/v1/systemone', '-TimeoutSec', '2')
           if ($r.code -ne 1) { throw "no key anywhere: expected exit 1, got $($r.code)" }
       } },
    @{ Name = 'F11 composite_honesty: missing weighted answer => null + listed; unsure input => YOUR CALL; choice ids skipped'
       Run = {
           $wf = (New-Tmp 'w') + '.json'
           '{ "pick": 1, "deploy_now__safety": 1, "wait_for_qa__safety": 1 }' | Set-Content -LiteralPath $wf
           try { $o = (Invoke-Jev @('-Payload', (F 'clean.json'), '-Fake', (F 'answers-lowconf-missing.json'), '-Weights', $wf, '-Json')).out | ConvertFrom-Json }
           finally { Remove-Item -LiteralPath $wf -Force }
           $d = $o.compositeDetail.deploy_now; $q = $o.compositeDetail.wait_for_qa
           if ($d.value -ne 0.67 -or $d.used -ne 1 -or $d.leastSure -ne 0.3 -or -not $d.yourCall) { throw "deploy_now detail wrong: $($d | ConvertTo-Json -Compress)" }
           if ($null -ne $q.value -or @($q.missing) -notcontains 'wait_for_qa__safety' -or -not $q.yourCall) { throw "wait_for_qa detail wrong: $($q | ConvertTo-Json -Compress)" }
           if ($o.compositeDetail.PSObject.Properties.Name -contains 'all') { throw 'choice id "pick" was weighted into a composite' }
           $c = (Invoke-Jev @('-Payload', (F 'clean.json'), '-Fake', (F 'answers-confident.json'), '-Weights', (F 'weights.json'), '-Json')).out | ConvertFrom-Json
           if ($c.compositeDetail.deploy_now.yourCall) { throw 'confident composite flagged YOUR CALL' }
       } },
    @{ Name = 'F12 receipt: written with full odds + schema, no key; NOT written for refused payloads'
       Run = {
           $dir = New-Tmp 'rcpt'
           try {
               $o = (Invoke-Jev @('-Payload', (F 'clean.json'), '-Fake', (F 'answers-confident.json'), '-ReceiptDir', $dir, '-Json')).out | ConvertFrom-Json
               if (-not $o.receipt -or -not (Test-Path -LiteralPath $o.receipt)) { throw 'no receipt file' }
               $txt = Get-Content -LiteralPath $o.receipt -Raw
               if ($txt -match $Sentinel) { throw 'API key written to receipt' }
               $rc = $txt | ConvertFrom-Json
               if ($rc.receiptSchema -ne 1 -or $rc.fingerprint -ne $o.fingerprint) { throw 'receipt schema/fingerprint wrong' }
               if ($rc.answers.pick.probabilities.deploy_now -ne 0.15) { throw 'receipt lost the losing option odds' }
               if ($rc.PSObject.Properties.Name -notcontains 'decision') { throw 'receipt has no decision slot' }
               $before = @(Get-ChildItem -LiteralPath $dir).Count
               $null = Invoke-Jev @('-Payload', (F 'leak-email.json'), '-Send', '-Approve', 'x', '-ReceiptDir', $dir)
               $null = Invoke-Jev @('-Payload', (F 'bad-type.json'), '-Fake', (F 'answers-confident.json'), '-ReceiptDir', $dir)
               $null = Invoke-Jev @('-Payload', (F 'clean.json'), '-Send', '-ReceiptDir', $dir)
               if (@(Get-ChildItem -LiteralPath $dir).Count -ne $before) { throw 'receipt written for a refused payload' }
           } finally { if (Test-Path -LiteralPath $dir) { Remove-Item -LiteralPath $dir -Recurse -Force } }
       } },
    @{ Name = 'usage: -Send with -Fake together is refused'
       Run = {
           $r = Invoke-Jev @('-Payload', (F 'clean.json'), '-Send', '-Fake', (F 'answers-split.json'))
           if ($r.code -ne 1) { throw "expected exit 1, got $($r.code)" }
       } }
)

$pass = 0; $fail = 0
foreach ($t in $tests) {
    try { & $t.Run; $pass++; Write-Host "PASS $($t.Name)" -ForegroundColor Green }
    catch { $fail++; Write-Host "FAIL $($t.Name): $_" -ForegroundColor Red }
}
if ($fail -eq 0) { Write-Host "EVAL PASS personal-jev ($pass)" -ForegroundColor Green; exit 0 }
else { Write-Host "EVAL FAIL personal-jev ($fail of $($pass+$fail))" -ForegroundColor Red; exit 1 }
