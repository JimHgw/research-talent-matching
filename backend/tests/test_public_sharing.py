"""Check tunnel deployment settings and HTTPS login/write behavior."""

import json
from pathlib import Path
import shutil
import subprocess

import pytest

from backend.src.shared.paths import ROOT
from conftest import PASSWORD
from test_docker_stack import compose_cli, stack_environment


ORIGIN = "https://banana-demo.trycloudflare.com"


@pytest.mark.parametrize("frontend_port", [5173, 15173])
def test_public_compose_preserves_local_origins_and_existing_storage(frontend_port):
    docker = shutil.which("docker")
    if not docker:
        pytest.skip("Docker Compose is required to validate deployment settings.")
    result = subprocess.run(
        [docker, "compose", "--project-directory", str(ROOT),
         "--env-file", str(ROOT / ".env.example"),
         "--file", str(ROOT / "compose.yaml"),
         "--file", str(ROOT / "compose.share.yaml"), "config", "--format", "json"],
        env=stack_environment({"PUBLIC_ORIGIN": ORIGIN, "FRONTEND_PORT": str(frontend_port)}), capture_output=True,
        text=True, encoding="utf-8", errors="replace", timeout=30,
    )
    assert result.returncode == 0, result.stderr
    config = json.loads(result.stdout)
    backend = config["services"]["backend"]
    tunnel = config["services"]["tunnel"]
    assert backend["environment"]["ALLOWED_ORIGINS"].split(",") == [
        ORIGIN, f"http://127.0.0.1:{frontend_port}", f"http://localhost:{frontend_port}",
    ]
    assert backend["environment"]["COOKIE_SECURE"] == "true"
    assert config["volumes"]["backend_data"]["name"] == "banana-backend_backend_data"
    assert any(mount["source"] == "backend_data" and mount["target"] == "/app/data"
               for mount in backend["volumes"])
    assert not tunnel.get("ports") and not tunnel.get("volumes")
    assert tunnel["restart"] == "no"
    assert tunnel["command"][-2:] == ["--url", "http://frontend:80"]
    assert "default" in tunnel["networks"]
    assert Path(config["services"]["frontend"]["build"]["context"]) == ROOT / "frontend"
    for name in ("frontend", "backend"):
        assert all(port["host_ip"] == "127.0.0.1" for port in config["services"][name]["ports"])


@pytest.mark.parametrize("frontend_port", [5173, 15173])
def test_ngrok_compose_routes_directly_to_frontend(compose_cli, tmp_path, frontend_port):
    agent_env = tmp_path / "ngrok-agent.env"
    agent_env.write_text("NGROK_AUTHTOKEN=test-not-a-real-token\n", encoding="utf-8")
    ngrok_url = "https://banana-demo.ngrok-free.dev"
    origins = f"{ngrok_url},{ORIGIN}"
    result = subprocess.run(
        [*compose_cli, "--project-directory", str(ROOT),
         "--env-file", str(ROOT / ".env.example"),
         "--file", str(ROOT / "compose.yaml"),
         "--file", str(ROOT / "compose.ngrok.yaml"), "config", "--format", "json"],
        env=stack_environment({"NGROK_URL": ngrok_url, "PUBLIC_ORIGINS": origins,
                               "FRONTEND_PORT": str(frontend_port),
                               "NGROK_AGENT_ENV_FILE": str(agent_env)}),
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
    )
    assert result.returncode == 0, result.stderr
    config = json.loads(result.stdout)
    ngrok = config["services"]["ngrok"]
    backend = config["services"]["backend"]
    assert ngrok["command"] == ["http", "--url", ngrok_url, "http://frontend:80"]
    assert "default" in ngrok["networks"]
    assert not ngrok.get("ports")
    assert ngrok["environment"]["NGROK_AUTHTOKEN"] == "test-not-a-real-token"
    assert ngrok["restart"] == "unless-stopped"
    assert backend["environment"]["ALLOWED_ORIGINS"].split(",") == [
        ngrok_url, ORIGIN, f"http://127.0.0.1:{frontend_port}", f"http://localhost:{frontend_port}",
    ]
    assert backend["environment"]["COOKIE_SECURE"] == "true"
    assert config["volumes"]["backend_data"]["name"] == "banana-backend_backend_data"


@pytest.mark.parametrize("origin", [ORIGIN, "https://banana-demo.ngrok-free.dev"])
def test_https_tunnel_session_login_and_profile_write(app, origin):
    app.config.update(COOKIE_SECURE=True, ALLOWED_ORIGINS={origin})
    client = app.test_client()
    response = client.get("/api/v1/auth/session", base_url=origin)
    assert response.status_code == 200
    assert "Secure" in response.headers["Set-Cookie"]
    csrf = response.get_json()["csrfToken"]
    login = {"email": "talent@example.test", "password": PASSWORD}
    response = client.post("/api/v1/auth/login", base_url=origin, json=login,
                           headers={"Origin": "https://untrusted.trycloudflare.com", "X-CSRF-Token": csrf})
    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "CSRF_INVALID"
    response = client.post("/api/v1/auth/login", base_url=origin, json=login,
                           headers={"Origin": origin, "X-CSRF-Token": csrf})
    assert response.status_code == 200
    assert "Secure" in response.headers["Set-Cookie"]
    csrf = response.get_json()["csrfToken"]
    content = json.loads((ROOT / "docs/api/examples/profile-write.json").read_text())["content"]
    response = client.put("/api/v1/me/profile", base_url=origin,
                          json={"expectedRevision": 0, "content": content},
                          headers={"Origin": origin, "X-CSRF-Token": csrf})
    assert response.status_code == 200
    response = client.get("/api/v1/me/profile", base_url=origin)
    assert response.status_code == 200
    assert response.get_json()["content"] == content
