"""Check Windows bootstrap control flow without installing system software."""

import json
import os
from pathlib import Path
import subprocess

import pytest

from backend.src.shared.paths import ROOT


@pytest.mark.skipif(os.name != "nt", reason="The bootstrap installer targets Windows.")
@pytest.mark.parametrize("fail_install", [False, True])
def test_windows_setup_handles_fresh_clone_and_install_failure(tmp_path, fail_install):
    checkout = tmp_path / "fresh clone with spaces"
    (checkout / "frontend").mkdir(parents=True)
    (checkout / "frontend/package.json").write_text('{"packageManager":"pnpm@11.25.0"}')
    quote = lambda path: "'" + str(path).replace("'", "''") + "'"
    scenario = tmp_path / "scenario.ps1"
    scenario.write_text(
        "$ErrorActionPreference = 'Stop'\n"
        f". {quote(ROOT / 'scripts/setup-windows.ps1')}\n"
        f"$repo = {quote(checkout)}\n"
        f"$failInstall = ${str(fail_install).lower()}\n"
        r"""
$events = [System.Collections.Generic.List[string]]::new()
$pythonLookups = 0
$nodeLookups = 0
function Find-Python {
    $script:pythonLookups++
    if ($script:pythonLookups -gt 1) { return 'C:\Fake Python\python.exe' }
}
function Find-Node {
    $script:nodeLookups++
    if ($script:nodeLookups -gt 1) { return 'C:\Fake Node\node.exe' }
}
function Install-Runtime {
    param([string]$Id, [switch]$UserScope)
    $events.Add("install:$Id")
    if ($failInstall) { throw 'simulated installer failure' }
}
function Invoke-Checked {
    param([string]$Executable, [string[]]$Arguments)
    $events.Add(($Arguments -join '|'))
    if ($Arguments.Length -ge 2 -and $Arguments[1] -eq 'venv') {
        New-Item -ItemType Directory -Path (Join-Path $repo '.venv/Scripts') -Force | Out-Null
    }
}
$originalLocation = (Get-Location).Path
$originalPath = $env:Path
$originalNode = $env:NODE_BINARY
$originalCI = $env:CI
$failure = $null
try { Initialize-Project -RepoRoot $repo } catch { $failure = $_.Exception.Message }
@{
    events = @($events.ToArray())
    failure = $failure
    locationRestored = ((Get-Location).Path -eq $originalLocation)
    pathRestored = ($env:Path -eq $originalPath)
    nodeRestored = ([string]$env:NODE_BINARY -eq [string]$originalNode)
    ciRestored = ([string]$env:CI -eq [string]$originalCI)
} | ConvertTo-Json -Compress
""",
        encoding="utf-8-sig",
    )
    powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    result = subprocess.run(
        [str(powershell), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(scenario)],
        cwd=tmp_path, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    outcome = json.loads(result.stdout.strip().splitlines()[-1])
    assert all(outcome[key] for key in ("locationRestored", "pathRestored", "nodeRestored", "ciRestored"))
    config = checkout / ".venv/toolchain.json"
    if fail_install:
        assert outcome["failure"] == "simulated installer failure"
        assert outcome["events"] == ["install:Python.Python.3.13"]
        assert not config.exists()
        assert "Setup complete" not in result.stdout
    else:
        assert outcome["failure"] is None
        events = outcome["events"]
        assert "install:Python.Python.3.13" in events
        assert "install:OpenJS.NodeJS.LTS" in events
        assert any("requirements-dev.txt" in event for event in events)
        assert any("pnpm@11.25.0" in event for event in events)
        assert any(event.endswith("install|--frozen-lockfile") for event in events)
        assert "-m|pytest|-q|--require-frontend" in events
        assert events[-1].endswith("|test")
        assert json.loads(config.read_text(encoding="utf-8-sig"))["node"] == r"C:\Fake Node\node.exe"
