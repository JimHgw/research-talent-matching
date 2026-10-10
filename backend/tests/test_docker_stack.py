"""Validate Compose wiring and optionally exercise isolated real containers."""

from contextlib import ExitStack
from http.cookiejar import CookieJar
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener
from uuid import uuid4

import pytest

from backend.src.shared.paths import ROOT


@pytest.fixture
def compose_cli(request):
    standalone = os.getenv("DOCKER_COMPOSE_BINARY")
    if standalone:
        path = Path(standalone)
        if not path.is_absolute() or not path.is_file():
            pytest.fail("DOCKER_COMPOSE_BINARY must point to an existing absolute executable path.")
        return [str(path)]
    docker = shutil.which("docker")
    if docker:
        return [docker, "compose"]
    if request.config.getoption("--run-docker"):
        pytest.fail("Docker and Compose are required for --run-docker.")
    pytest.skip("Install Docker Compose to validate the actual Compose configuration.")


def stack_environment(overrides=None):
    env = os.environ.copy()
    for name in ("COMPOSE_PROJECT_NAME", "COMPOSE_FILE", "COMPOSE_PROFILES",
                 "BACKEND_PORT", "FRONTEND_PORT", "COOKIE_SECURE", "ALLOWED_ORIGINS"):
        env.pop(name, None)
    return {**env, **(overrides or {})}


def compose_args(cli):
    return [*cli, "--project-directory", str(ROOT), "--env-file", str(ROOT / ".env.example"),
            "--file", str(ROOT / "compose.yaml")]


@pytest.mark.parametrize("ports", [None, (18100, 15173)])
def test_compose_preserves_storage_and_routes_over_the_shared_network(compose_cli, ports):
    overrides = {} if ports is None else {
        "BACKEND_PORT": str(ports[0]), "FRONTEND_PORT": str(ports[1]),
        "ALLOWED_ORIGINS": f"http://127.0.0.1:{ports[1]},http://localhost:{ports[1]}",
    }
    result = subprocess.run([*compose_args(compose_cli), "config", "--format", "json"],
                            env=stack_environment(overrides), capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    config = json.loads(result.stdout)
    frontend, backend = (config["services"][name] for name in ("frontend", "backend"))
    assert Path(frontend["build"]["context"]) == ROOT / "frontend"
    assert frontend["build"]["target"] == "runtime"
    assert Path(backend["build"]["context"]) == ROOT
    assert backend["build"]["dockerfile"] == "backend/Dockerfile"
    assert frontend["environment"]["API_PROXY_TARGET"] == "http://backend:8000"
    assert not frontend.get("extra_hosts")
    assert frontend["depends_on"]["backend"]["condition"] == "service_healthy"
    assert "default" in frontend["networks"] and "default" in backend["networks"]
    assert config["networks"]["default"]["driver"] == "bridge"
    assert config["name"] == "banana-backend"
    assert config["volumes"]["backend_data"]["name"] == "banana-backend_backend_data"
    mount = next(item for item in backend["volumes"] if item["target"] == "/app/data")
    assert mount["type"] == "volume" and mount["source"] == "backend_data"
    assert backend["environment"]["DATABASE_URL"] == "sqlite:////app/data/h18abanana.db"
    assert backend["environment"]["COOKIE_SECURE"] == "false"
    backend_port, frontend_port = ports or (8000, 5173)
    for service, published, target in ((backend, backend_port, 8000), (frontend, frontend_port, 80)):
        assert service["ports"][0]["host_ip"] == "127.0.0.1"
        assert str(service["ports"][0]["published"]) == str(published)
        assert service["ports"][0]["target"] == target
    assert backend["environment"]["ALLOWED_ORIGINS"] == (
        f"http://127.0.0.1:{frontend_port},http://localhost:{frontend_port}"
    )


def test_real_stack_login_profile_and_restart_persistence(compose_cli, request, tmp_path):
    if not request.config.getoption("--run-docker"):
        pytest.skip("Use --run-docker to build and exercise isolated real containers.")
    docker = shutil.which("docker")
    if not docker:
        pytest.fail("A Docker CLI and running Linux engine are required for the container smoke test.")
    engine = subprocess.run([docker, "info", "--format", "{{.OSType}}"],
                            capture_output=True, text=True, timeout=30)
    assert engine.returncode == 0 and engine.stdout.strip() == "linux", engine.stdout + engine.stderr

    # Reserve distinct ports while selecting them; never attach to existing services.
    with ExitStack() as sockets:
        ports = []
        for _ in range(2):
            sock = sockets.enter_context(socket.socket())
            sock.bind(("127.0.0.1", 0))
            ports.append(sock.getsockname()[1])
    backend_port, frontend_port = ports
    origin = f"http://127.0.0.1:{frontend_port}"
    env = stack_environment({"BACKEND_PORT": str(backend_port), "FRONTEND_PORT": str(frontend_port),
                             "ALLOWED_ORIGINS": origin, "COOKIE_SECURE": "false"})
    project = "banana-stack-test-" + uuid4().hex[:12]
    images = [f"{project}-{service}:test" for service in ("frontend", "backend")]
    override = tmp_path / "images.json"
    override.write_text(json.dumps({"services": {
        name: {"image": image} for name, image in zip(("frontend", "backend"), images)
    }}), encoding="utf-8")
    command = [*compose_args(compose_cli), "--file", str(override), "--project-name", project]

    def compose(*args, check=True):
        result = subprocess.run([*command, *args], env=env, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=900)
        if check:
            assert result.returncode == 0, result.stdout + result.stderr
        return result

    browser = build_opener(HTTPCookieProcessor(CookieJar()))

    def api(path, method="GET", data=None, csrf=None, status=200, allowed_origin=origin):
        headers = {"Origin": allowed_origin}
        if csrf:
            headers["X-CSRF-Token"] = csrf
        body = None
        if data is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(data).encode()
        query = Request(origin + "/api/v1" + path, data=body, headers=headers, method=method)
        try:
            response = browser.open(query, timeout=20)
        except HTTPError as error:
            response = error
        with response:
            payload = response.read()
            assert response.status == status, (response.status, payload.decode(errors="replace"))
            return json.loads(payload) if payload else None

    try:
        compose("up", "--build", "--detach", "--wait", "--wait-timeout", "120")
        with browser.open(origin + "/", timeout=20) as response:
            assert b"/assets/" in response.read()
        with browser.open(origin + "/healthz", timeout=20) as response:
            assert response.read().strip() == b"ok"
        with browser.open(f"http://127.0.0.1:{backend_port}/healthz", timeout=20) as response:
            assert json.load(response) == {"status": "ok"}
        password = "Test-container-password-123!"
        provision = (
            "from backend.app import create_app\n"
            "result = create_app().test_cli_runner().invoke(args=['provision-user', "
            "'--email', 'container@example.test', '--display-name', 'Container Talent', "
            f"'--role', 'TALENT'], input={password + chr(10) + password + chr(10)!r})\n"
            "if result.exception: raise result.exception\n"
        )
        compose("exec", "-T", "backend", "python", "-c", provision)
        anonymous = api("/auth/session")
        session = api("/auth/login", "POST", {"email": "container@example.test", "password": password},
                      anonymous["csrfToken"])
        profile = api("/me/profile")
        content = {**profile["content"], "displayName": "Persisted through Nginx", "disciplineGroup": "STEM"}
        write = {"expectedRevision": profile["revision"], "content": content}
        saved = api("/me/profile", "PUT", write, session["csrfToken"])
        assert saved["revision"] == profile["revision"] + 1
        api("/me/profile", "PUT", write, session["csrfToken"], status=409)
        api("/me/profile", "PUT", {**write, "expectedRevision": saved["revision"]}, session["csrfToken"],
            status=403, allowed_origin="https://untrusted.example")
        # Replace both containers/network while preserving only this test project's volume.
        compose("down")
        compose("up", "--no-build", "--detach", "--wait", "--wait-timeout", "120")
        restored = api("/auth/session")
        assert restored["user"]["id"] == session["user"]["id"]
        assert api("/me/profile")["content"] == content
        api("/auth/logout", "POST", csrf=restored["csrfToken"], status=204)
        api("/me/profile", status=401)
        fresh = api("/auth/session")
        api("/auth/login", "POST", {"email": "container@example.test", "password": password}, fresh["csrfToken"])
        assert api("/me/profile")["revision"] == saved["revision"]
    except Exception:
        diagnostic = compose("logs", "--tail", "80", check=False)
        print(diagnostic.stdout + diagnostic.stderr)
        raise
    finally:
        # Destructive cleanup is restricted to the unique project/images created above.
        cleanup = compose("down", "--volumes", "--remove-orphans", check=False)
        subprocess.run([docker, "image", "rm", *images], capture_output=True, timeout=60)
        assert cleanup.returncode == 0, cleanup.stdout + cleanup.stderr
