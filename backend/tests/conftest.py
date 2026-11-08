import json
import os
import hashlib
from pathlib import Path

import pytest

from backend.src.app import create_app
from backend.src.db.database import Database
from backend.src.db.models import Base, DatabaseWriteLock
from backend.src.features.auth.routes import provision_user
from backend.src.features.profile.routes import seed_tags
from backend.src.shared.paths import ROOT
from sqlalchemy.engine import make_url

PASSWORD = "Test-password-123!"
ORIGIN = "http://127.0.0.1:5173"


def pytest_addoption(parser):
    parser.addoption("--require-frontend", action="store_true",
                     help="Fail instead of skipping real HTTP integration when Node/jsdom is missing.")
    parser.addoption("--require-application-model", action="store_true",
                     help="Fail instead of skipping real application MiniLM HTTP tests when local resources are unavailable.")
    parser.addoption("--run-docker", action="store_true",
                     help="Build and test the real Docker stack in an isolated disposable project.")
    parser.addoption("--run-mysql", action="store_true",
                     help="Run app fixtures against MYSQL_TEST_DATABASE_URL (database name must end in _test; tables are cleared).")
    parser.addoption("--shard-index", type=int, default=1,
                     help="One-based test shard index (default: 1).")
    parser.addoption("--shard-total", type=int, default=1,
                     help="Number of disjoint test shards (default: 1, runs everything).")


def partition_test_items(items, index, total):
    """Assign every node ID to exactly one shard, independent of collection order."""
    if total < 1 or not 1 <= index <= total:
        raise ValueError("Test shard options require 1 <= --shard-index <= --shard-total.")
    selected, deselected = [], []
    for item in items:
        number = int.from_bytes(hashlib.sha256(item.nodeid.encode("utf-8")).digest(), "big") % total
        (selected if number == index - 1 else deselected).append(item)
    return selected, deselected


def pytest_collection_modifyitems(config, items):
    try:
        selected, deselected = partition_test_items(
            items, config.getoption("--shard-index"), config.getoption("--shard-total"))
    except ValueError as error:
        raise pytest.UsageError(str(error)) from None
    config.hook.pytest_deselected(items=deselected)
    items[:] = selected


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
            raise pytest.UsageError("Invalid .venv/toolchain.json; rerun setup.ps1 (Windows) or sh setup.sh (macOS/Linux).") from error
        patch.setenv("NODE_BINARY", node)
    if config.getoption("basetemp") or os.environ.get("PYTEST_DEBUG_TEMPROOT"):
        return
    # Let pytest number and retain its own run directories, including concurrent runs.
    # An absolute path also supports invoking pytest from outside the repository.
    temp_root = ROOT / ".pytest_cache" / "tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    patch.setenv("PYTEST_DEBUG_TEMPROOT", str(temp_root))


@pytest.fixture(scope="session")
def mysql_schema(request):
    """Create schema once per test process; never use a business database."""
    if not request.config.getoption("--run-mysql"):
        yield
        return
    url = os.getenv("MYSQL_TEST_DATABASE_URL", "")
    parsed = make_url(url) if url else None
    if not parsed or parsed.drivername != "mysql+pymysql" or not (parsed.database or "").endswith("_test"):
        pytest.fail("--run-mysql requires MYSQL_TEST_DATABASE_URL naming a disposable MySQL database ending in _test.")
    database = Database(url)
    try:
        Base.metadata.drop_all(database.engine)
        database.initialise()
        yield
    finally:
        try:
            Base.metadata.drop_all(database.engine)
        finally:
            database.engine.dispose()


def clear_mysql_data(database):
    """Keep tables and the writer mutex; delete child rows before their parents."""
    with database.transaction(write=True) as db:
        for table in reversed(Base.metadata.sorted_tables):
            if table.name != DatabaseWriteLock.__tablename__:
                db.execute(table.delete())


@pytest.fixture
def app(tmp_path, request, mysql_schema):
    mysql = request.config.getoption("--run-mysql")
    url = os.environ["MYSQL_TEST_DATABASE_URL"] if mysql else f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    # Baseline suites retain deterministic structured scores; application semantic
    # integration tests explicitly enable the real or substituted encoder.
    app = create_app({"TESTING": True, "DATABASE_URL": url, "SEMANTIC_MATCHING_ENABLED": False,
                      "COOKIE_SECURE": False, "LOGIN_EMAIL_LIMIT": 100, "LOGIN_IP_LIMIT": 100})
    database = app.extensions["database"]
    if not mysql:
        database.initialise()
    try:
        with app.app_context():
            seed_tags(json.loads((ROOT / "docs/api/examples/tags.json").read_text())["items"])
            for email, role in (("talent@example.test", "TALENT"), ("other@example.test", "TALENT"),
                                ("team@example.test", "RESEARCH_TEAM")):
                provision_user(email, PASSWORD, email.split("@")[0], role)
        yield app
    finally:
        try:
            if mysql:
                clear_mysql_data(database)
        finally:
            database.engine.dispose()


def sign_in(client, email="talent@example.test", password=PASSWORD):
    session = client.get("/api/v1/auth/session").get_json()
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password},
                           headers=headers(session["csrfToken"]))
    assert response.status_code == 200, response.get_json()
    return response.get_json()["csrfToken"]


@pytest.fixture(scope="session")
def application_model(request):
    """Verify the application assets, independently of the historical US-13 model.

    The BE-7/CI acceptance command requires this fixture: missing dependencies,
    incomplete files, invalid checksums and load failures must fail that run.
    Ordinary backend-only runs may explicitly report these tests as skipped.
    """
    from backend.src.features.matching.multilingual_encoder import MultilingualEncoder
    from backend.src.features.matching.semantic_runtime import model_config

    directory = Path(os.getenv("SEMANTIC_MODEL_DIR", str(ROOT / "data/semantic/model")))
    if not directory.is_absolute():
        directory = ROOT / directory
    try:
        encoder = MultilingualEncoder(directory, model_config())
        encoder.encode(["生物技术研究"])
    except Exception as error:
        message = (f"Real application model unavailable ({type(error).__name__}). "
                   "Install backend/requirements-semantic.txt and run "
                   "python -m backend.src.features.matching.prepare_semantic.")
        if request.config.getoption("--require-application-model"):
            pytest.fail(message, pytrace=False)
        pytest.skip(message)
    return directory


def headers(csrf):
    return {"Origin": ORIGIN, "X-CSRF-Token": csrf}


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def signed(client):
    return client, sign_in(client)
