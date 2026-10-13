#requires -Version 5.1
<#
.SYNOPSIS
Build and start the Flask + SQLite backend in Docker.
.EXAMPLE
powershell -NoProfile -ExecutionPolicy Bypass -File .\docker-backend.ps1
.EXAMPLE
powershell -NoProfile -ExecutionPolicy Bypass -File .\docker-backend.ps1 -Action build
#>
param(
    [ValidateSet('up', 'build', 'stop', 'down', 'logs', 'status')]
    [string]$Action = 'up'
)

$ErrorActionPreference = 'Stop'

try {
    # Docker Desktop ships both docker.exe and an extensionless shell launcher.
    # Select the first executable instead of joining all matching command paths.
    $dockerCommand = Get-Command docker -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if (-not $dockerCommand) {
        throw 'Docker is not installed or is not on PATH. Install Docker Desktop, start it, and reopen your terminal.'
    }
    $dockerPath = $dockerCommand.Source
    & $dockerPath compose version
    if ($LASTEXITCODE -ne 0) {
        throw 'Docker Compose is unavailable. Install or update Docker Desktop / the Docker Compose plugin.'
    }
    $dockerOS = & $dockerPath info --format '{{.OSType}}'
    if ($LASTEXITCODE -ne 0) {
        throw 'Cannot connect to Docker. Start Docker Desktop / Docker Engine and retry.'
    }
    if (($dockerOS -join '').Trim() -ne 'linux') {
        throw 'This image requires Linux containers. Switch Docker Desktop to Linux containers.'
    }

    $envFile = Join-Path $PSScriptRoot '.env'
    if (-not (Test-Path -LiteralPath $envFile -PathType Leaf)) {
        $envFile = Join-Path $PSScriptRoot '.env.example'
    }
    $composeArgs = @('compose', '--project-directory', $PSScriptRoot,
                     '--env-file', $envFile, '--file', (Join-Path $PSScriptRoot 'compose.yaml'))
    [string[]]$actionArgs = switch ($Action) {
        'up'     { @('up', '--build', '--detach', '--wait', '--wait-timeout', '120', 'backend', 'document-worker') }
        'build'  { @('build', 'backend') }
        'stop'   { @('stop', 'backend', 'document-worker') }
        'down'   { @('down') }
        'logs'   { @('logs', '--follow', '--tail', '100', 'backend', 'document-worker') }
        'status' { @('ps', '--all') }
    }
    & $dockerPath @composeArgs @actionArgs
    if ($LASTEXITCODE -ne 0) {
        throw 'Docker Compose failed. Check the output above; use -Action logs to inspect startup failures. Database volumes were not deleted.'
    }
    if ($Action -eq 'up') {
        Write-Host 'Backend is healthy. Published address (append /healthz to check):'
        & $dockerPath @composeArgs port backend 8000
        if ($LASTEXITCODE -ne 0) { throw 'Could not read the published backend address.' }
        Write-Host 'See README_DEVELOPER_EN.md to create accounts and connect the frontend.'
    } elseif ($Action -eq 'build') {
        Write-Host 'Image built: banana-backend:local. No container was started.'
    } elseif ($Action -eq 'down') {
        Write-Host 'Compose containers and network removed. The SQLite data volume is preserved.'
    } elseif ($Action -eq 'stop') {
        Write-Host 'Backend and document worker stopped. The SQLite data volume is preserved.'
    }
} catch {
    Write-Host "Backend Docker command failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
