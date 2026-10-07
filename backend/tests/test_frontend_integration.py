"""Run the current React pages against a real HTTP server and file-backed SQLite."""

import os
from pathlib import Path
import shutil
import subprocess
from threading import Thread

import pytest
from werkzeug.serving import make_server

from backend.src.shared.paths import ROOT


def test_real_frontend_login_save_reload_conflict_logout(app):
    node = os.getenv("NODE_BINARY") or shutil.which("node")
    if not node:
        pytest.skip("Node.js is unavailable. Run setup.ps1 (Windows), or set NODE_BINARY/add Node to PATH. Use -rs for skip reasons.")
    if not (ROOT / "frontend/node_modules/jsdom").exists():
        pytest.skip("Frontend dependencies are missing. Run setup.ps1 (Windows), or pnpm install --frozen-lockfile in frontend/.")
    if not Path(node).is_file():
        pytest.fail("The configured Node executable is missing. Rerun setup.ps1 or correct NODE_BINARY.")
    server = make_server("127.0.0.1", 0, app, threaded=True)
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        result = subprocess.run(
            [node, "--import", "./tests/setup-jsx.js", "tests/us01-live.mjs"],
            cwd=ROOT / "frontend", capture_output=True, text=True, timeout=90,
            env={**os.environ, "TEST_API_BASE_URL": f"http://127.0.0.1:{server.server_port}"},
            encoding="utf-8", errors="replace",
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert "US-01 real HTTP integration passed" in result.stdout
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
