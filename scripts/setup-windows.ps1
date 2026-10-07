# Functions are separate from the entry point so installation failure paths can be tested.
Set-StrictMode -Version Latest

function Invoke-Checked {
    param([string]$Executable, [string[]]$Arguments)
    & $Executable @Arguments | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw "$Executable failed with exit code $LASTEXITCODE."
    }
}

function Test-Python {
    param([string]$Executable)
    if (-not $Executable -or -not (Test-Path -LiteralPath $Executable -PathType Leaf)) { return $false }
    try {
        & $Executable -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)' 2>$null | Out-Null
        return $LASTEXITCODE -eq 0
    } catch { return $false }
}

function Find-Python {
    $candidates = @()
    foreach ($version in @('313', '312', '314')) {
        $candidates += Join-Path $env:LOCALAPPDATA "Programs/Python/Python$version/python.exe"
        $candidates += Join-Path $env:ProgramFiles "Python$version/python.exe"
    }
    $command = Get-Command python.exe -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($command -and $command.Source -notlike '*\Microsoft\WindowsApps\*') {
        $candidates += $command.Source
    }
    foreach ($candidate in $candidates) {
        if (Test-Python $candidate) { return $candidate }
    }
    $launcher = Get-Command py.exe -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($launcher) {
        try {
            $candidate = & $launcher.Source -3 -c 'import sys; print(sys.executable)' 2>$null
            if ($LASTEXITCODE -eq 0 -and (Test-Python "$candidate")) { return "$candidate" }
        } catch { }
    }
    return $null
}

function Find-Node {
    $candidates = @(
        (Join-Path $env:ProgramFiles 'nodejs/node.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs/nodejs/node.exe')
    )
    $command = Get-Command node.exe -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($command) { $candidates += $command.Source }
    foreach ($candidate in $candidates) {
        if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) { continue }
        # npm ships with the official Node installer and bootstraps our local pnpm.
        $npm = Join-Path (Split-Path $candidate) 'node_modules/npm/bin/npm-cli.js'
        if (-not (Test-Path -LiteralPath $npm -PathType Leaf)) { continue }
        try {
            $version = & $candidate --version 2>$null
            if ($LASTEXITCODE -eq 0 -and "$version" -match '^v(\d+\.\d+\.\d+)$') {
                if ([version]$Matches[1] -ge [version]'22.13.0') { return $candidate }
            }
        } catch { }
    }
    return $null
}

function Install-Runtime {
    param([string]$Id, [switch]$UserScope)
    $winget = Get-Command winget.exe -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $winget) {
        throw 'WinGet is required to install missing runtimes. Install Microsoft App Installer from https://aka.ms/getwinget and rerun setup.ps1.'
    }
    Write-Host "Installing $Id using WinGet..."
    $installArguments = @('install', '--id', $Id, '--exact', '--source', 'winget',
        '--accept-package-agreements', '--accept-source-agreements', '--disable-interactivity', '--silent')
    if ($UserScope) { $installArguments += @('--scope', 'user') }
    Invoke-Checked $winget.Source $installArguments
    # Installers update the stored PATH; make it visible without reopening this process.
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
        [Environment]::GetEnvironmentVariable('Path', 'User') + ';' + $env:Path
}

function Initialize-Project {
    param([string]$RepoRoot)
    $RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
    $venv = Join-Path $RepoRoot '.venv'
    $python = Join-Path $venv 'Scripts/python.exe'
    $frontend = Join-Path $RepoRoot 'frontend'
    $previousPath = $env:Path
    $previousNode = $env:NODE_BINARY
    $previousCI = $env:CI
    Push-Location -LiteralPath $RepoRoot
    try {
        Write-Host '[1/6] Preparing Python (3.12 or newer)...'
        if (Test-Path -LiteralPath $venv) {
            if (-not (Test-Python $python)) {
                throw 'The existing .venv is broken or uses Python older than 3.12. Rename .venv and rerun setup.ps1; it will not be overwritten.'
            }
        } else {
            $basePython = Find-Python
            if (-not $basePython) {
                Install-Runtime -Id 'Python.Python.3.13' -UserScope
                $basePython = Find-Python
            }
            if (-not $basePython) { throw 'Python was not found after installation. Reopen PowerShell and rerun setup.ps1.' }
            Invoke-Checked $basePython @('-m', 'venv', $venv)
        }
        Invoke-Checked $python @('--version')

        Write-Host '[2/6] Preparing Node.js (22.13 or newer)...'
        $node = Find-Node
        if (-not $node) {
            Install-Runtime -Id 'OpenJS.NodeJS.LTS'
            $node = Find-Node
        }
        if (-not $node) { throw 'Node.js was not found after installation. Reopen PowerShell and rerun setup.ps1.' }
        $env:Path = (Split-Path $node) + ';' + $env:Path
        $env:NODE_BINARY = $node
        Invoke-Checked $node @('--version')

        Write-Host '[3/6] Installing backend and test dependencies...'
        Invoke-Checked $python @('-m', 'pip', '--disable-pip-version-check', 'install', '-r',
            (Join-Path $RepoRoot 'backend/requirements-dev.txt'))
        Invoke-Checked $python @('-m', 'pip', 'check')

        Write-Host '[4/6] Preparing the pinned project-local pnpm...'
        $package = Get-Content -LiteralPath (Join-Path $frontend 'package.json') -Raw | ConvertFrom-Json
        if ($package.packageManager -notmatch '^pnpm@(\d+\.\d+\.\d+)$') {
            throw 'frontend/package.json must pin packageManager to pnpm@X.Y.Z.'
        }
        $pnpmVersion = $Matches[1]
        $tools = Join-Path $venv 'node-tools'
        $pnpm = Join-Path $tools 'node_modules/pnpm/bin/pnpm.cjs'
        $installedVersion = ''
        if (Test-Path -LiteralPath $pnpm) {
            $installedVersion = & $node $pnpm --version
            if ($LASTEXITCODE -ne 0) { $installedVersion = '' }
        }
        if ("$installedVersion".Trim() -ne $pnpmVersion) {
            $npm = Join-Path (Split-Path $node) 'node_modules/npm/bin/npm-cli.js'
            Invoke-Checked $node @($npm, 'install', '--prefix', $tools, '--no-audit', '--no-fund',
                '--ignore-scripts', '--package-lock=false', "pnpm@$pnpmVersion")
        }
        Invoke-Checked $node @($pnpm, '--version')
        $env:Path = (Join-Path $tools 'node_modules/.bin') + ';' + $env:Path

        Write-Host '[5/6] Installing frontend dependencies from the lockfile...'
        $env:CI = 'true'
        Push-Location -LiteralPath $frontend
        try {
            Invoke-Checked $node @($pnpm, 'install', '--frozen-lockfile')
        } finally { Pop-Location }

        # Local machine paths stay in the ignored venv, never in tracked source.
        # Fresh terminals and pytest can find Node without a Codex-specific PATH.
        @{ node = $node; pnpm = $pnpm } | ConvertTo-Json |
            Set-Content -LiteralPath (Join-Path $venv 'toolchain.json') -Encoding UTF8

        Write-Host '[6/6] Verifying backend, frontend and real HTTP integration...'
        Invoke-Checked $python @('-m', 'pytest', '-q', '--require-frontend')
        Push-Location -LiteralPath $frontend
        try {
            Invoke-Checked $node @($pnpm, 'test')
        } finally { Pop-Location }

        Write-Host 'Setup complete. Dependencies are installed and tests passed.' -ForegroundColor Green
        Write-Host 'Next: follow backend/README.md to initialise your development database and start both services.'
    } finally {
        Pop-Location
        $env:Path = $previousPath
        $env:NODE_BINARY = $previousNode
        $env:CI = $previousCI
    }
}
