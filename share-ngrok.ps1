#requires -Version 5.1
<#
.SYNOPSIS
Use an assigned ngrok HTTPS URL with the existing Docker application.
.EXAMPLE
powershell -NoProfile -ExecutionPolicy Bypass -File .\share-ngrok.ps1 -Url https://your-name.ngrok-free.dev
#>
param(
    [ValidateSet('up', 'stop', 'status', 'logs')]
    [string]$Action = 'up',
    [string]$Url
)

$ErrorActionPreference = 'Stop'
$savedEnvironment = @{}
foreach ($name in @('NGROK_URL', 'NGROK_AGENT_ENV_FILE', 'PUBLIC_ORIGINS')) {
    $savedEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}

try {
    $dockerCommand = Get-Command docker -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if (-not $dockerCommand) { throw 'Install and start Docker Desktop first.' }
    $dockerPath = $dockerCommand.Source
    $dockerOS = & $dockerPath info --format '{{.OSType}}'
    if ($LASTEXITCODE -ne 0 -or ($dockerOS -join '').Trim() -ne 'linux') {
        throw 'Start Docker Desktop with Linux containers and retry.'
    }
    $stateDir = Join-Path $PSScriptRoot 'data/public-sharing'
    $urlFile = Join-Path $stateDir 'ngrok-url.txt'
    $agentFile = Join-Path $stateDir 'ngrok-agent.env'
    if (-not $Url -and (Test-Path -LiteralPath $urlFile)) {
        $Url = (Get-Content -LiteralPath $urlFile -Raw).Trim()
    }
    # Accept a copied root URL, then store its origin without a trailing slash.
    $Url = ([string]$Url).Trim()
    if ($Url -notmatch '^https://[a-z0-9-]+\.ngrok-free\.(dev|app)/?$') {
        throw 'Provide the assigned HTTPS root URL using -Url https://your-name.ngrok-free.dev (or .app), without a path or query.'
    }
    $Url = $Url.TrimEnd('/')
    $env:NGROK_URL = $Url
    $env:NGROK_AGENT_ENV_FILE = $agentFile
    $origins = @($Url)
    $cloudflareUrlFile = Join-Path $stateDir 'public-url.txt'
    if (Test-Path -LiteralPath $cloudflareUrlFile) {
        $cloudflareUrl = (Get-Content -LiteralPath $cloudflareUrlFile -Raw).Trim()
        if ($cloudflareUrl -match '^https://[a-z0-9-]+\.trycloudflare\.com$') {
            $origins += $cloudflareUrl
        }
    }
    $env:PUBLIC_ORIGINS = $origins -join ','
    $envFile = Join-Path $PSScriptRoot '.env'
    if (-not (Test-Path -LiteralPath $envFile)) { $envFile = Join-Path $PSScriptRoot '.env.example' }
    $composeArgs = @('compose', '--project-directory', $PSScriptRoot, '--env-file', $envFile,
                     '--file', (Join-Path $PSScriptRoot 'compose.yaml'),
                     '--file', (Join-Path $PSScriptRoot 'compose.ngrok.yaml'))

    if ($Action -eq 'up') {
        New-Item -ItemType Directory -Force -Path $stateDir | Out-Null
        if (-not (Test-Path -LiteralPath $agentFile)) {
            $authToken = $env:NGROK_AUTHTOKEN
            if (-not $authToken) {
                # Reuse this computer's already configured ngrok credentials.
                # Capture in memory; never print the token or put it in arguments.
                $extensionJson = & $dockerPath exec ngrok_ngrok-docker-extension-desktop-extension-service cat /data/state.json
                if ($LASTEXITCODE -ne 0) { throw 'Set NGROK_AUTHTOKEN locally, or configure the ngrok Docker extension first.' }
                $extensionState = ($extensionJson -join "`n") | ConvertFrom-Json
                $authToken = $extensionState.agentConfig.authToken
            }
            if (-not $authToken -or $authToken -match '[\r\n]') { throw 'No valid local ngrok token found.' }
            Set-Content -LiteralPath $agentFile -Value "NGROK_AUTHTOKEN=$authToken" -Encoding Ascii
            $authToken = $null
            $extensionJson = $null
            $extensionState = $null
        }
        & $dockerPath @composeArgs config --quiet
        if ($LASTEXITCODE -ne 0) { throw 'The ngrok deployment configuration is invalid.' }
        Write-Host 'Updating public login origins and refreshing frontend/API containers...'
        & $dockerPath @composeArgs up --detach --wait --wait-timeout 120 --force-recreate backend document-worker frontend
        if ($LASTEXITCODE -ne 0) { throw 'Application startup failed.' }
        Write-Host 'Connecting ngrok directly to the frontend container...'
        & $dockerPath @composeArgs up --detach --no-deps ngrok
        if ($LASTEXITCODE -ne 0) { throw 'ngrok startup failed. Stop the same endpoint in the Docker extension first.' }
        $verified = $false
        $deadline = [DateTime]::UtcNow.AddSeconds(90)
        do {
            try {
                $headers = @{'ngrok-skip-browser-warning' = '1'}
                $health = Invoke-WebRequest -UseBasicParsing -Uri "$Url/healthz" -Headers $headers -TimeoutSec 10
                $session = Invoke-WebRequest -UseBasicParsing -Uri "$Url/api/v1/auth/session" -Headers $headers -TimeoutSec 10
                $sessionData = $session.Content | ConvertFrom-Json
                if ($health.Content.Trim() -ne 'ok' -or -not $sessionData.csrfToken -or
                    ($session.Headers['Set-Cookie'] -join ';') -notmatch '(?i)(^|;)\s*Secure(;|$)') {
                    throw 'Public page/API session verification failed.'
                }
                $verified = $true
            } catch {
                $lastError = $_.Exception.Message
                Start-Sleep -Seconds 3
            }
        } while (-not $verified -and [DateTime]::UtcNow -lt $deadline)
        if (-not $verified) {
            & $dockerPath @composeArgs stop ngrok
            throw "Public checks failed: $lastError. Run -Action logs to inspect the ngrok connection."
        }
        Set-Content -LiteralPath $urlFile -Value $Url -Encoding Ascii
        Write-Host "Share this URL: $Url" -ForegroundColor Green
        Write-Host 'Keep the computer awake and Docker Desktop running.'
    } else {
        [string[]]$actionArgs = switch ($Action) {
            'stop' { @('stop', 'ngrok') }
            'status' { @('ps', '--all', 'ngrok') }
            'logs' { @('logs', '--tail', '80', 'ngrok') }
        }
        & $dockerPath @composeArgs @actionArgs
        if ($LASTEXITCODE -ne 0) { throw 'Docker Compose command failed.' }
        if ($Action -eq 'stop') { Write-Host 'ngrok sharing stopped. Application data is preserved.' }
    }
} catch {
    Write-Host "ngrok sharing failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
} finally {
    foreach ($name in $savedEnvironment.Keys) {
        [Environment]::SetEnvironmentVariable($name, $savedEnvironment[$name], 'Process')
    }
}
