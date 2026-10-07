#requires -Version 5.1
# Use the toolchain prepared by ../setup.ps1, including in a fresh terminal.
$ErrorActionPreference = 'Stop'
$configPath = Join-Path (Split-Path $PSScriptRoot) '.venv/toolchain.json'
try {
    if (-not (Test-Path -LiteralPath $configPath)) { throw 'Run the repository-root setup.ps1 first.' }
    $toolchain = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
    foreach ($executable in @($toolchain.node, $toolchain.pnpm)) {
        if (-not $executable -or -not (Test-Path -LiteralPath $executable -PathType Leaf)) {
            throw 'The saved toolchain is unavailable. Rerun the repository-root setup.ps1.'
        }
    }
    $previousPath = $env:Path
    $pnpmBin = Join-Path (Split-Path $PSScriptRoot) '.venv/node-tools/node_modules/.bin'
    $env:Path = (Split-Path $toolchain.node) + ';' + $pnpmBin + ';' + $env:Path
    Push-Location -LiteralPath $PSScriptRoot
    try {
        & $toolchain.node $toolchain.pnpm @args
        $result = $LASTEXITCODE
    } finally {
        Pop-Location
        $env:Path = $previousPath
    }
    exit $result
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
