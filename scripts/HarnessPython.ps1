# Dot-source this file, then call Find-HarnessPython to get a real python.exe path (or $null).
# Skips the Microsoft Store "python" alias, which opens the Store instead of running Python.
# Windows PowerShell 5.1 compatible; ASCII only.

function Test-PythonRuntime([string]$Candidate) {
    if (-not $Candidate -or -not (Test-Path -LiteralPath $Candidate)) { return $false }
    if ($Candidate -like '*\WindowsApps\*') { return $false }
    try {
        $version = & $Candidate -c "import sys; print(sys.version_info >= (3, 9))" 2>$null
        return ($LASTEXITCODE -eq 0) -and ("$version".Trim() -eq 'True')
    } catch {
        return $false
    }
}

function Find-HarnessPython {
    $candidates = @()
    foreach ($name in @('python', 'python3')) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if ($command) { $candidates += $command.Source }
    }
    $launcher = Get-Command py -ErrorAction SilentlyContinue
    if ($launcher) {
        try {
            $fromLauncher = & $launcher.Source -3 -c "import sys; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $fromLauncher) { $candidates += "$fromLauncher".Trim() }
        } catch { }
    }
    $patterns = @(
        (Join-Path $env:LOCALAPPDATA 'Python\*\python.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python3*\python.exe'),
        'C:\Python3*\python.exe',
        (Join-Path $env:ProgramFiles 'Python3*\python.exe')
    )
    foreach ($pattern in $patterns) {
        $candidates += @(Get-ChildItem -Path $pattern -ErrorAction SilentlyContinue |
            Sort-Object FullName -Descending | ForEach-Object { $_.FullName })
    }
    foreach ($candidate in $candidates) {
        if (Test-PythonRuntime $candidate) { return $candidate }
    }
    return $null
}
