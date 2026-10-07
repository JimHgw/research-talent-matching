import json
import os

import pytest

from backend.src.app import create_app
from backend.src.features.auth.routes import provision_user
from backend.src.features.profile.routes import seed_tags
from backend.src.shared.paths import ROOT

PASSWORD = "Test-password-123!"
ORIGIN = "http://127.0.0.1:5173"


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    """Load the local toolchain and keep temporary databases in the workspace."""
    patch = pytest.MonkeyPatch()
    config.add_cleanup(patch.undo)
    toolchain = ROOT / ".venv/toolchain.json"
    if not os.environ.get("NODE_BINARY") and toolchain.is_file():
        try:
            node = json.loads(toolchain.read_text(encoding="utf-8-sig"))["node"]
            if not isinstance(node, str) or not node:
                raise ValueError("missing Node executable")
        except (OSError, ValueError, KeyError) as error:
            raise pytest.UsageError("Invalid .venv/toolchain.json; rerun setup.ps1.") from error
        patch.setenv("NODE_BINARY", node)
    if config.getoption("basetemp") or os.environ.get("PYTEST_DEBUG_TEMPROOT"):
        return
    # Let pytest number and retain its own run directories, including concurrent runs.
    # An absolute path also supports invoking pytest from outside the repository.
    temp_root = ROOT / ".pytest_cache" / "tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    patch.setenv("PYTEST_DEBUG_TEMPROOT", str(temp_root))


@pytest.fixture
def app(tmp_path):
    app = create_app({"TESTING": True, "DATABASE_URL": f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
                      "COOKIE_SECURE": False, "LOGIN_EMAIL_LIMIT": 100, "LOGIN_IP_LIMIT": 100})
    database = app.extensions["database"]
    database.initialise()
    with app.app_context():
        seed_tags(json.loads((ROOT / "docs/api/examples/tags.json").read_text())["items"])
        for email, role in (("talent@example.test", "TALENT"), ("other@example.test", "TALENT"),
                            ("team@example.test", "RESEARCH_TEAM")):
            provision_user(email, PASSWORD, email.split("@")[0], role)
    yield app
    database.engine.dispose()


def sign_in(client, email="talent@example.test", password=PASSWORD):
    session = client.get("/api/v1/auth/session").get_json()
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password},
                           headers=headers(session["csrfToken"]))
    assert response.status_code == 200, response.get_json()
    return response.get_json()["csrfToken"]


def headers(csrf):
    return {"Origin": ORIGIN, "X-CSRF-Token": csrf}


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def signed(client):
    return client, sign_in(client)
