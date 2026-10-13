"""Exercise container startup and its host launchers without a Docker daemon."""

import json
import os
from pathlib import Path
import shlex
import shutil
import sqlite3
import subprocess
import sys

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

from backend.src.db.models import AuthSession, LoginAttempt, User
from backend.src.shared.paths import ROOT


def posix_shell():
    shell = shutil.which("sh")
    if not shell and os.name == "nt":
        candidate = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Git/bin/bash.exe"
        if candidate.is_file():
            shell = str(candidate)
    if not shell:
        pytest.skip("A POSIX shell is needed (Git Bash also works on Windows).")
    return shell


def test_health_check_does_not_create_sessions_or_expose_database_errors(app):
    database = app.extensions["database"]

    def counts():
        with database.transaction() as db:
            return [db.scalar(select(func.count()).select_from(model))
                    for model in (User, AuthSession, LoginAttempt)]

    before = counts()
    client = app.test_client()
    for _ in range(2):
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.json == {"status": "ok"}
        assert "Set-Cookie" not in response.headers
    assert counts() == before

    class UnavailableDatabase:
        def transaction(self):
            raise OperationalError("private SQL", {}, Exception("private database location"))

    app.extensions["database"] = UnavailableDatabase()
    try:
        response = client.get("/healthz")
        assert response.status_code == 503
        assert response.json == {"status": "unavailable"}
        assert "private" not in response.get_data(as_text=True)
    finally:
        app.extensions["database"] = database


def test_container_initialization_preserves_accounts_and_stops_on_seed_conflict(tmp_path):
    shell = posix_shell()
    # Exercise the runtime layout without the frontend or the rest of the docs.
    package = tmp_path / "runtime with spaces"
    (package / "backend").mkdir(parents=True)
    for name in ("__init__.py", "app.py"):
        shutil.copyfile(ROOT / "backend" / name, package / "backend" / name)
    shutil.copytree(ROOT / "backend/src", package / "backend/src",
                    ignore=shutil.ignore_patterns("__pycache__"))
    (package / "docs/api/examples").mkdir(parents=True)
    for name in ("openapi.json", "examples/tags.json"):
        shutil.copyfile(ROOT / "docs/api" / name, package / "docs/api" / name)

    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()
    python = tools_dir / "python"
    python.write_text(f"#!/bin/sh\nexec {shlex.quote(Path(sys.executable).as_posix())} \"$@\"\n",
                      encoding="utf-8", newline="\n")
    python.chmod(0o755)
    database_path = tmp_path / "persistent volume" / "backend.db"
    env = {**os.environ, "PATH": str(tools_dir) + os.pathsep + os.environ.get("PATH", ""),
           "PYTHONPATH": str(package), "DATABASE_URL": f"sqlite:///{database_path.as_posix()}",
           "COOKIE_SECURE": "false", "ALLOWED_ORIGINS": "http://127.0.0.1:5173",
           "FLASK_SKIP_DOTENV": "1"}

    def start():
        return subprocess.run(
            [shell, (ROOT / "backend/docker/entrypoint.sh").as_posix(),
             Path(sys.executable).as_posix(), "-c", "print('SERVER STARTED')"],
            cwd=package, env=env, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=45,
        )

    first = start()
    assert first.returncode == 0, first.stdout + first.stderr
    assert "SERVER STARTED" in first.stdout
    expected_tags = json.loads((ROOT / "docs/api/examples/tags.json").read_text(encoding="utf-8"))["items"]
    with sqlite3.connect(database_path) as db:
        assert db.execute("SELECT count(*) FROM users").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM tags").fetchone()[0] == len(expected_tags)

    # CliRunner supplies hidden password input portably; Windows getpass reads
    # the console directly even when subprocess stdin is a pipe.
    provision_code = (
        "from backend.app import create_app\n"
        "result = create_app().test_cli_runner().invoke(args=['provision-user', "
        "'--email', 'persist@example.test', '--display-name', 'Persistent User', "
        "'--role', 'TALENT'], input='Test-password-123!\\nTest-password-123!\\n')\n"
        "if result.exception: raise result.exception\n"
    )
    provision = subprocess.run(
        [sys.executable, "-c", provision_code], cwd=package, env=env,
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
    )
    assert provision.returncode == 0, provision.stdout + provision.stderr
    second = start()
    assert second.returncode == 0, second.stdout + second.stderr
    with sqlite3.connect(database_path) as db:
        assert db.execute("SELECT email FROM users").fetchall() == [("persist@example.test",)]
        assert db.execute("SELECT count(*) FROM tags").fetchone()[0] == len(expected_tags)
        db.execute("UPDATE tags SET label = ? WHERE id = ?", ("Changed vocabulary", expected_tags[0]["id"]))

    failed = start()
    assert failed.returncode != 0
    assert "SERVER STARTED" not in failed.stdout
    assert "An existing tag differs" in failed.stdout + failed.stderr
    with sqlite3.connect(database_path) as db:
        assert db.execute("SELECT email FROM users").fetchall() == [("persist@example.test",)]


@pytest.mark.parametrize("launcher", ["powershell", "shell"])
@pytest.mark.parametrize("scenario", [
    "up", "build", "stop", "down", "env_override", "startup_failure", "build_failure",
    "daemon_failure", "compose_failure", "windows_engine",
])
def test_docker_launchers_handle_paths_failures_and_preserve_volumes(tmp_path, launcher, scenario):
    if launcher == "powershell":
        powershell = shutil.which("powershell") or shutil.which("pwsh")
        if not powershell:
            pytest.skip("PowerShell is required to exercise the Windows launcher.")
    else:
        shell = posix_shell()

    checkout = tmp_path / "checkout with spaces"
    checkout.mkdir()
    for name in ("docker-backend.ps1", "docker-backend.sh", "compose.yaml", ".env.example"):
        shutil.copyfile(ROOT / name, checkout / name)
    if scenario == "env_override":
        (checkout / ".env").write_text("BACKEND_PORT=8001\n", encoding="utf-8")
    # An unrelated working-directory .env must never be used.
    (tmp_path / ".env").write_text("BACKEND_PORT=9999\n", encoding="utf-8")
    events_path = tmp_path / "events.jsonl"
    probe = tmp_path / "fake docker.py"
    probe.write_text(
        "import json, os, pathlib, sys\n"
        "args = sys.argv[1:]\n"
        "with pathlib.Path(os.environ['DOCKER_TEST_EVENTS']).open('a', encoding='utf-8') as log:\n"
        "    log.write(json.dumps(args) + '\\n')\n"
        "scenario = os.environ['DOCKER_TEST_SCENARIO']\n"
        "if args[:2] == ['compose', 'version']:\n"
        "    print('Docker Compose test double')\n"
        "    sys.exit(17 if scenario == 'compose_failure' else 0)\n"
        "if args[:1] == ['info']:\n"
        "    print('windows' if scenario == 'windows_engine' else 'linux')\n"
        "    sys.exit(17 if scenario == 'daemon_failure' else 0)\n"
        "if ('up' in args and scenario == 'startup_failure'\n"
        "        or 'build' in args and scenario == 'build_failure'):\n"
        "    sys.exit(17)\n"
        "if 'port' in args:\n"
        "    print('127.0.0.1:8000')\n",
        encoding="utf-8",
    )
    tools_dir = tmp_path / "fake tools"
    tools_dir.mkdir()
    if launcher == "powershell" and os.name == "nt":
        fake_docker = tools_dir / "docker.cmd"
        fake_docker.write_text(f'@echo off\n"{sys.executable}" "{probe}" %*\n', encoding="utf-8")
        # Match Docker Desktop's native and extensionless launchers on PATH.
        # Get-Command can return both; the host script must select just one.
        (tools_dir / "docker").write_text("#!/bin/sh\nexit 99\n", encoding="utf-8")
    else:
        fake_docker = tools_dir / "docker"
        fake_docker.write_text(
            f"#!/bin/sh\nexec {shlex.quote(Path(sys.executable).as_posix())} "
            f"{shlex.quote(probe.as_posix())} \"$@\"\n", encoding="utf-8", newline="\n",
        )
        fake_docker.chmod(0o755)
    env = {**os.environ, "PATH": str(tools_dir) + os.pathsep + os.environ.get("PATH", ""),
           "DOCKER_TEST_EVENTS": str(events_path), "DOCKER_TEST_SCENARIO": scenario}
    action = {"build_failure": "build"}.get(scenario, scenario if scenario in ("build", "stop", "down") else "up")
    if launcher == "powershell":
        command = [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                   str(checkout / "docker-backend.ps1")]
        if action != "up":
            command += ["-Action", action]
    else:
        command = [shell, (checkout / "docker-backend.sh").as_posix()]
        if action != "up":
            command.append(action)
    result = subprocess.run(command, cwd=tmp_path, env=env, capture_output=True,
                            text=True, encoding="utf-8", errors="replace", timeout=30)
    assert events_path.is_file(), result.stdout + result.stderr
    events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()]
    failures = {"startup_failure", "build_failure", "daemon_failure", "compose_failure", "windows_engine"}
    assert (result.returncode != 0) == (scenario in failures), result.stdout + result.stderr
    if scenario in failures:
        assert "Backend is healthy" not in result.stdout
        assert "Image built:" not in result.stdout
    elif action == "up":
        assert "Backend is healthy" in result.stdout
    operations = [args for args in events if "--file" in args]
    if scenario in {"daemon_failure", "compose_failure", "windows_engine"}:
        assert not operations
    else:
        assert operations
        for args in operations:
            assert Path(args[args.index("--project-directory") + 1]) == checkout
            assert Path(args[args.index("--file") + 1]) == checkout / "compose.yaml"
            env_file = ".env" if scenario == "env_override" else ".env.example"
            assert Path(args[args.index("--env-file") + 1]) == checkout / env_file
        assert action in operations[0]
        if action in ("up", "stop"):
            assert operations[0][-2:] == ["backend", "document-worker"]
        if action == "build":
            assert operations[0][-1] == "backend"
        if action == "build":
            assert all("up" not in args for args in operations)
    assert all("-v" not in args and "--volumes" not in args for args in events)
    assert (tmp_path / ".env").read_text(encoding="utf-8") == "BACKEND_PORT=9999\n"
