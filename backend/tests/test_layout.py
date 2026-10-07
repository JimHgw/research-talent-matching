"""Exercise CLI entry points and resource lookup after source relocation."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from sqlalchemy import select

from backend.src.db.database import Database
from backend.src.db.models import Tag

REPO = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("directory", [".", "backend"])
def test_relative_database_path_stays_at_repository_root(monkeypatch, directory):
    monkeypatch.chdir(REPO / directory)
    database = Database("sqlite:///data/h18abanana.db")
    try:
        # Inspect the destination without connecting to or changing local data.
        assert Path(database.engine.url.database) == REPO / "data/h18abanana.db"
    finally:
        database.engine.dispose()


@pytest.mark.parametrize("directory,entry_point", [
    (".", "backend.app"),
    ("backend", "src.app"),
])
def test_cli_loads_contract_and_default_tags_from_either_directory(tmp_path, directory, entry_point):
    url = f"sqlite:///{(tmp_path / 'cli.db').as_posix()}"
    environment = {**os.environ, "DATABASE_URL": url, "COOKIE_SECURE": "false",
                   "ALLOWED_ORIGINS": "http://127.0.0.1:5173", "FLASK_SKIP_DOTENV": "1"}

    def command(name):
        result = subprocess.run(
            [sys.executable, "-m", "flask", "--app", entry_point, name],
            cwd=REPO / directory, env=environment, capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=30,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        return result.stdout

    assert "Database tables initialised." in command("init-db")
    assert "Tags seeded." in command("seed-tags")
    routes = command("routes")
    for route in ("/api/v1/auth/session", "/api/v1/auth/login", "/api/v1/auth/logout",
                  "/api/v1/me/profile", "/api/v1/tags"):
        assert route in routes

    expected = json.loads((REPO / "docs/api/examples/tags.json").read_text(encoding="utf-8"))
    database = Database(url)
    try:
        with database.transaction() as db:
            assert set(db.scalars(select(Tag.id))) == {tag["id"] for tag in expected["items"]}
    finally:
        database.engine.dispose()
