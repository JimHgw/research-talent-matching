#requires -Version 5.1
<#
.SYNOPSIS
Share this computer's Docker application through a temporary HTTPS URL.
.EXAMPLE
powershell -NoProfile -ExecutionPolicy Bypass -File .\share.ps1
.EXAMPLE
powershell -NoProfile -ExecutionPolicy Bypass -File .\share.ps1 -Action stop
#>
param(
    [ValidateSet('up', 'stop', 'status', 'logs')]
    [string]$Action = 'up',
    [switch]$NoBuild
)

$ErrorActionPreference = 'Stop'
$previousPublicOrigin = [Environment]::GetEnvironmentVariable('PUBLIC_ORIGIN', 'Process')
$composeBase = @()
$composeShare = @()
$stopTunnelOnFailure = $false

function Invoke-Compose {
    param([string[]]$Arguments)
    & $script:dockerPath @script:composeShare @Arguments
    if ($LASTEXITCODE -ne 0) { throw 'Docker Compose failed. Check the output above.' }
}

function Get-CurrentTunnelUrl {
    $containerId = & $script:dockerPath @script:composeShare ps --all --quiet tunnel
    if ($LASTEXITCODE -ne 0) { throw 'Could not inspect the tunnel.' }
    if (-not $containerId) { return $null }
    $stateJson = & $script:dockerPath inspect --format '{{json .State}}' $containerId
    if ($LASTEXITCODE -ne 0) { throw 'Could not inspect the tunnel process.' }
    $state = $stateJson | ConvertFrom-Json
    if (-not $state.Running) { return $null }
    # Ignore old URLs in retained logs when the same container starts again.
    $logs = & $script:dockerPath @script:composeShare logs --no-color --since $state.StartedAt tunnel
    if ($LASTEXITCODE -ne 0) { throw 'Could not read the tunnel logs.' }
    $urls = [regex]::Matches(($logs -join "`n"), 'https://[a-z0-9-]+\.trycloudflare\.com')
    if ($urls.Count -gt 0) { return $urls[$urls.Count - 1].Value }
    return $null
}

try {
    $dockerCommand = Get-Command docker -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if (-not $dockerCommand) { throw 'Install Docker Desktop, start it, and reopen your terminal.' }
    $dockerPath = $dockerCommand.Source
    $dockerOS = & $dockerPath info --format '{{.OSType}}'
    if ($LASTEXITCODE -ne 0) { throw 'Start Docker Desktop and retry.' }
    if (($dockerOS -join '').Trim() -ne 'linux') { throw 'Switch Docker Desktop to Linux containers.' }

    $envFile = Join-Path $PSScriptRoot '.env'
    if (-not (Test-Path -LiteralPath $envFile -PathType Leaf)) {
        $envFile = Join-Path $PSScriptRoot '.env.example'
    }
    $composeBase = @('compose', '--project-directory', $PSScriptRoot,
                     '--env-file', $envFile, '--file', (Join-Path $PSScriptRoot 'compose.yaml'))
    $composeShare = @($composeBase) + @('--file', (Join-Path $PSScriptRoot 'compose.share.yaml'))
    # Only used while discovering the real URL; never a wildcard or a browser origin.
    $env:PUBLIC_ORIGIN = 'https://sharing.invalid'
    $urlFile = Join-Path $PSScriptRoot 'data/public-sharing/public-url.txt'

    if ($Action -eq 'stop') {
        Invoke-Compose -Arguments @('stop', 'tunnel')
        # Revert to the user's ordinary local HTTP settings and refresh Nginx DNS.
        & $dockerPath @composeBase up --detach --wait --wait-timeout 120 --force-recreate backend document-worker frontend
        if ($LASTEXITCODE -ne 0) { throw 'Sharing stopped, but local services could not be restored.' }
        if (Test-Path -LiteralPath $urlFile) { Set-Content -LiteralPath $urlFile -Value '' -Encoding Ascii }
        Write-Host 'Public sharing stopped. Local services and database are preserved.'
    } elseif ($Action -eq 'status') {
        Invoke-Compose -Arguments @('ps', '--all')
        $publicUrl = Get-CurrentTunnelUrl
        if ($publicUrl) { Write-Host "Running tunnel URL: $publicUrl" }
        else { Write-Host 'No running public tunnel.' }
    } elseif ($Action -eq 'logs') {
        Invoke-Compose -Arguments @('logs', '--tail', '80', 'tunnel')
    } else {
        Invoke-Compose -Arguments @('config', '--quiet')
        Write-Host 'Starting the temporary tunnel...'
        $stopTunnelOnFailure = $true
        Invoke-Compose -Arguments @('up', '--detach', '--no-deps', 'tunnel')
        $deadline = [DateTime]::UtcNow.AddSeconds(90)
        do {
            $publicUrl = Get-CurrentTunnelUrl
            if ($publicUrl) { break }
            Start-Sleep -Seconds 2
        } while ([DateTime]::UtcNow -lt $deadline)
        if (-not $publicUrl) { throw 'No URL received. Run share.ps1 -Action logs to check network connectivity.' }
        $env:PUBLIC_ORIGIN = $publicUrl

        Write-Host 'Configuring HTTPS sessions and starting the frontend, API and document worker...'
        $startArgs = @('up', '--detach', '--wait', '--wait-timeout', '120', '--force-recreate')
        if (-not $NoBuild) { $startArgs += '--build' }
        $startArgs += @('backend', 'document-worker', 'frontend')
        Invoke-Compose -Arguments $startArgs

        Write-Host 'Checking the public page and API...'
        $verified = $false
        $deadline = [DateTime]::UtcNow.AddSeconds(90)
        do {
            try {
                $health = Invoke-WebRequest -UseBasicParsing -Uri "$publicUrl/healthz" -TimeoutSec 10
                $session = Invoke-WebRequest -UseBasicParsing -Uri "$publicUrl/api/v1/auth/session" -TimeoutSec 10
                $sessionData = $session.Content | ConvertFrom-Json
                $cookie = $session.Headers['Set-Cookie'] -join ';'
                if ($health.StatusCode -ne 200 -or $health.Content.Trim() -ne 'ok' -or
                    -not $sessionData.csrfToken -or $cookie -notmatch '(?i)(^|;)\s*Secure(;|$)') {
                    throw 'The public frontend/API or secure session check failed.'
                }
                $verified = $true
            } catch {
                $verificationError = $_.Exception.Message
                Start-Sleep -Seconds 3
            }
        } while (-not $verified -and [DateTime]::UtcNow -lt $deadline)
        if (-not $verified) { throw "Public checks failed: $verificationError" }

        New-Item -ItemType Directory -Force -Path (Split-Path $urlFile) | Out-Null
        Set-Content -LiteralPath $urlFile -Value $publicUrl -Encoding Ascii
        $stopTunnelOnFailure = $false
        Write-Host ''
        Write-Host "Share this URL: $publicUrl" -ForegroundColor Green
        Write-Host 'Keep this computer awake, online, and Docker Desktop running.'
        Write-Host 'Stop sharing: powershell -NoProfile -ExecutionPolicy Bypass -File .\share.ps1 -Action stop'
    }
} catch {
    if ($stopTunnelOnFailure -and $composeShare.Count -gt 0) {
        & $dockerPath @composeShare stop tunnel
        if ($LASTEXITCODE -ne 0) { Write-Warning 'Could not stop the tunnel. Stop it manually in Docker Desktop.' }
    }
    Write-Host "Public sharing failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
} finally {
    [Environment]::SetEnvironmentVariable('PUBLIC_ORIGIN', $previousPublicOrigin, 'Process')
}
