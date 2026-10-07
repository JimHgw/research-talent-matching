#requires -Version 5.1
# Run after cloning, before starting development. See backend/README.md.
$ErrorActionPreference = 'Stop'

try {
    if ($env:OS -ne 'Windows_NT') {
        throw 'This installer supports Windows. See backend/README.md for macOS/Linux setup.'
    }
    . (Join-Path $PSScriptRoot 'scripts/setup-windows.ps1')
    Initialize-Project -RepoRoot $PSScriptRoot
} catch {
    Write-Host "Setup failed: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host 'Fix the reported problem and run setup.ps1 again.'
    exit 1
}
