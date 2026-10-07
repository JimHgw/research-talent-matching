"""Run the current React pages against a real HTTP server and file-backed SQLite."""

import os
from pathlib import Path
import shutil
import subprocess
from threading import Thread

import pytest
from werkzeug.serving import make_server

from backend.src.shared.paths import ROOT


def frontend_node(required=False):
    """Optional for backend-only work, mandatory for setup and full acceptance."""
    node = os.getenv("NODE_BINARY") or shutil.which("node")
    hint = "Run setup.ps1 (Windows) or sh setup.sh (macOS/Linux)."
    unavailable = pytest.fail if required else pytest.skip
    if not node:
        unavailable("Node.js is unavailable. " + hint)
    if not (ROOT / "frontend/node_modules/jsdom").exists():
        unavailable("Frontend dependencies are missing. " + hint)
    if not Path(node).is_file():
        pytest.fail("The configured Node executable is missing. Correct NODE_BINARY. " + hint)
    return node


def test_real_frontend_login_save_reload_conflict_logout(app, request):
    node = frontend_node(required=request.config.getoption("--require-frontend"))
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
