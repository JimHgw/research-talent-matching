"""Exercise bootstrap failures and platform paths without network installations."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from scripts import dev
from backend.tests import test_frontend_integration as integration


@pytest.mark.parametrize("platform", ["darwin", "linux", "win32"])
@pytest.mark.parametrize("failure", [None, "dependencies", "integration"])
def test_setup_uses_local_tools_and_stops_on_failure(tmp_path, monkeypatch, capsys, platform, failure):
    checkout = tmp_path / "fresh checkout with spaces"
    (checkout / "frontend").mkdir(parents=True)
    (checkout / "frontend/package.json").write_text('{"packageManager":"pnpm@11.25.0"}', encoding="utf-8")
    runtime = tmp_path / "installed tools"
    (runtime / "node_modules/npm/bin").mkdir(parents=True)
    (runtime / "node_modules/npm/bin/npm-cli.js").touch()
    node = runtime / "node"
    npm = runtime / "npm"
    events = []
    monkeypatch.setattr(dev.sys, "platform", platform)
    monkeypatch.setattr(dev.shutil, "which", lambda name, **kwargs: str(npm if name == "npm" else node))
    monkeypatch.chdir(tmp_path)
    original_env = os.environ.copy()

    def fake_run(args, *, cwd, env, capture=False):
        args = [str(arg) for arg in args]
        events.append((args, cwd))
        assert env["NODE_BINARY"] == str(node)
        assert str(runtime) in env["PATH"].split(os.pathsep)
        if "--frozen-lockfile" in args or args[-1] == "test":
            assert str(checkout / ".venv/node-tools/node_modules/.bin") in env["PATH"].split(os.pathsep)
        if args == [str(node), "--version"]:
            return "v22.13.0"
        if args[1:3] == ["-m", "venv"]:
            python = Path(args[3]) / ("Scripts/python.exe" if platform == "win32" else "bin/python")
            python.parent.mkdir(parents=True)
            python.touch()
        if "--prefix" in args:
            pnpm = Path(args[args.index("--prefix") + 1]) / "node_modules/pnpm/bin/pnpm.cjs"
            pnpm.parent.mkdir(parents=True)
            pnpm.touch()
        if args[-1] == "--version":
            return "11.25.0"
        if (failure == "dependencies" and "--frozen-lockfile" in args
                or failure == "integration" and "pytest" in args):
            raise subprocess.CalledProcessError(7, args)

    monkeypatch.setattr(dev, "run", fake_run)
    if failure:
        with pytest.raises(subprocess.CalledProcessError):
            dev.setup(checkout)
        assert "Setup complete" not in capsys.readouterr().out
        assert events[-1][0][-1] == ("--frozen-lockfile" if failure == "dependencies" else "--require-frontend")
    else:
        dev.setup(checkout)
        assert "Setup complete" in capsys.readouterr().out
        config = json.loads((checkout / ".venv/toolchain.json").read_text(encoding="utf-8"))
        assert config["node"] == str(node)
        assert Path(config["pnpm"]).is_file()
        python = checkout / ".venv" / ("Scripts/python.exe" if platform == "win32" else "bin/python")
        assert ([str(python), "-m", "pytest", "-q", "--require-frontend"], checkout) in events
        assert events[-1] == ([str(node), config["pnpm"], "test"], checkout / "frontend")
        assert any(args[-2:] == ["install", "--frozen-lockfile"] for args, _ in events)
        assert any(args[-1] == "pnpm@11.25.0" for args, _ in events)
    assert Path.cwd() == tmp_path
    assert os.environ == original_env


@pytest.mark.parametrize("problem", ["missing_node", "old_node", "missing_npm", "foreign_venv"])
def test_setup_rejects_unusable_environment_before_installing(tmp_path, monkeypatch, problem):
    (tmp_path / "frontend").mkdir()
    (tmp_path / "frontend/package.json").write_text('{"packageManager":"pnpm@11.25.0"}', encoding="utf-8")
    (tmp_path / ".venv").mkdir()
    marker = tmp_path / ".venv/do-not-overwrite.txt"
    marker.write_text("existing environment", encoding="utf-8")
    monkeypatch.delenv("NODE_BINARY", raising=False)
    monkeypatch.setattr(dev.shutil, "which", lambda name, **kwargs:
                        None if problem == "missing_" + name else str(tmp_path / name))
    events = []

    def fake_run(args, **kwargs):
        events.append(args)
        return "v22.12.0" if problem == "old_node" else "v24.0.0"

    monkeypatch.setattr(dev, "run", fake_run)
    with pytest.raises(RuntimeError):
        dev.setup(tmp_path)
    assert all(args[-1] == "--version" for args in events)
    assert marker.read_text(encoding="utf-8") == "existing environment"


def test_frontend_runner_preserves_arguments_cwd_and_failure_code(tmp_path, monkeypatch):
    (tmp_path / ".venv").mkdir()
    (tmp_path / "frontend").mkdir()
    # A real subprocess stands in for Node/pnpm, so spaces and exit codes are checked.
    probe = tmp_path / "pnpm stand in.py"
    result_path = tmp_path / "result.json"
    probe.write_text(
        "import json, os, pathlib, sys\n"
        "import shutil\n"
        "pathlib.Path(sys.argv[1]).write_text(json.dumps({'args': sys.argv[2:], 'cwd': os.getcwd(), 'path': os.environ['PATH'], 'pnpm': shutil.which('pnpm')}))\n"
        "sys.exit(7)\n", encoding="utf-8",
    )
    (tmp_path / ".venv/toolchain.json").write_text(
        json.dumps({"node": sys.executable, "pnpm": str(probe)}), encoding="utf-8-sig",
    )
    pnpm_bin = tmp_path / ".venv/node-tools/node_modules/.bin"
    pnpm_bin.mkdir(parents=True)
    launcher = pnpm_bin / ("pnpm.cmd" if os.name == "nt" else "pnpm")
    launcher.write_text("@exit /b 0\n" if os.name == "nt" else "#!/bin/sh\nexit 0\n")
    launcher.chmod(0o755)
    monkeypatch.chdir(tmp_path.parent)
    with pytest.raises(subprocess.CalledProcessError) as error:
        dev.frontend([str(result_path), "argument with spaces", "--host", "127.0.0.1"], tmp_path)
    assert error.value.returncode == 7
    result = json.loads(result_path.read_text())
    assert result["args"] == ["argument with spaces", "--host", "127.0.0.1"]
    assert Path(result["cwd"]) == tmp_path / "frontend"
    assert Path(result["path"].split(os.pathsep)[0]) == Path(sys.executable).parent
    assert Path(result["pnpm"]) == launcher


@pytest.mark.parametrize("required", [False, True])
@pytest.mark.parametrize("missing", ["node", "jsdom"])
def test_frontend_requirement_fails_instead_of_skipping(tmp_path, monkeypatch, required, missing):
    monkeypatch.delenv("NODE_BINARY", raising=False)
    monkeypatch.setattr(integration.shutil, "which", lambda _: None if missing == "node" else sys.executable)
    monkeypatch.setattr(integration, "ROOT", tmp_path)
    with pytest.raises(pytest.fail.Exception if required else pytest.skip.Exception,
                       match="Node.js is unavailable" if missing == "node" else "Frontend dependencies are missing"):
        integration.frontend_node(required=required)


@pytest.mark.parametrize("entry", ["setup.sh", "frontend/run.sh"])
def test_shell_launchers_from_another_directory(tmp_path, entry):
    shell = shutil.which("sh")
    if not shell and os.name == "nt":
        git_bash = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Git/bin/bash.exe"
        if git_bash.is_file():
            shell = str(git_bash)
    if not shell:
        pytest.skip("A POSIX shell is required to exercise shell launchers (Git Bash works on Windows).")
    checkout = tmp_path / "checkout with spaces"
    launcher = checkout / entry
    launcher.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(dev.ROOT / entry, launcher)
    python = checkout / ".venv/bin/python"
    python.parent.mkdir(parents=True)
    python.write_text('#!/bin/sh\nprintf \'%s\\n\' "$@" > "$PROBE_OUTPUT"\nexit 23\n', encoding="utf-8", newline="\n")
    python.chmod(0o755)
    output = tmp_path / "arguments.txt"
    result = subprocess.run(
        [shell, launcher.as_posix(), "argument with spaces", "--host", "127.0.0.1"],
        cwd=tmp_path, env={**os.environ, "PYTHON": python.as_posix(), "PROBE_OUTPUT": output.as_posix()},
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 23, result.stdout + result.stderr
    args = output.read_text().splitlines()
    # Git Bash may canonicalise C:/ into /c/; either way the checkout is preserved.
    assert args[0].endswith("/checkout with spaces/scripts/dev.py")
    assert args[1:] == (["setup"] if entry == "setup.sh"
                        else ["frontend", "argument with spaces", "--host", "127.0.0.1"])
