# Person-in-the-loop reproduction loop, for steps only a person can do (for example RDP to a client box).
# Copy this file, edit the steps between the markers, and run it:
#   powershell -ExecutionPolicy Bypass -File <copy>.ps1
# The person follows the prompts. The captured answers print at the end as KEY=VALUE for the agent.
# Capture observations only. Signing in stays a Step, so no password is ever printed.
# Keep this file pure ASCII: Windows PowerShell 5.1 misreads other characters.

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'
$script:Captured = [ordered]@{}

# Shows one instruction and waits for Enter.
function Step([string]$Instruction) {
  Write-Host ''
  Write-Host ">>> $Instruction"
  [void](Read-Host '    [Enter when done]')
}

# Asks one question and keeps the answer under KEY.
function Capture([string]$Key, [string]$Question) {
  Write-Host ''
  Write-Host ">>> $Question"
  $script:Captured[$Key] = Read-Host '    >'
}

# --- edit below ---------------------------------------------------------------

Step 'Open Remote Desktop to the client box and sign in.'

Capture 'ERRORED' 'Open the Browse page and press Search with the client''s filter. Did an error show? (y/n)'

Capture 'ERROR_TEXT' 'Paste the error number and message (or none):'

# --- edit above ---------------------------------------------------------------

Write-Host ''
Write-Host '--- Captured ---'
foreach ($k in $script:Captured.Keys) { Write-Host "$k=$($script:Captured[$k])" }
