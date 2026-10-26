"""Run the current React pages against a real HTTP server and file-backed SQLite."""

import os
import json
from pathlib import Path
import shutil
import subprocess
from threading import Thread

import pytest
from werkzeug.serving import make_server

from backend.src.shared.paths import ROOT
from backend.src.features.auth.routes import provision_user
from conftest import PASSWORD


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


@pytest.mark.parametrize("story", ["01", "02", "03", "05", "14", "19", "01-register", "01-reset", "41", "49", "53", "i18n"])
def test_real_frontend_workflow(app, request, monkeypatch, tmp_path, story):
    if story == "53":
        contract = json.loads((ROOT / "docs/api/openapi.json").read_text(encoding="utf-8"))
        kinds = contract["components"]["schemas"]["Requirement"]["properties"]["kind"]["enum"]
        if not {"EDUCATION", "RESEARCH_EXPERIENCE", "RESEARCH_OUTPUT"}.issubset(kinds):
            pytest.skip("Task 53 academic integration needs BE-54; its API was reverted on main.")
    node = frontend_node(required=request.config.getoption("--require-frontend"))
    if story == "02":
        with app.app_context():
            provision_user("team2@example.test", PASSWORD, "Second team", "RESEARCH_TEAM")
    outbox = []
    if story == "01-register":
        monkeypatch.setattr("backend.src.features.auth.registration.secrets.randbelow", lambda _: 12345)
        app.extensions["registration_mailer"] = lambda email, code: outbox.append((email, code))
    if story == "01-reset":
        monkeypatch.setattr("backend.src.features.auth.reset.secrets.randbelow", lambda _: 12345)
        app.extensions["password_reset_mailer"] = lambda email, code: outbox.append((email, code))
    extra_env = {}
    if story in ("41", "i18n"):
        from io import BytesIO
        from docx import Document
        from backend.tests.conftest import sign_in, headers
        from backend.tests.test_us09_extraction import CV_TEXT
        from backend.src.features.documents.worker import process_next_document

        app.config["DOCUMENT_STORAGE_DIR"] = str(tmp_path / "documents")
        content = BytesIO()
        document = Document()
        for line in CV_TEXT.splitlines():
            document.add_paragraph(line)
        document.save(content)
        content.seek(0)
        client = app.test_client()
        csrf = sign_in(client)
        uploaded = client.post(
            "/api/v1/me/documents", data={"kind": "CV", "file": (content, "review-cv.docx")},
            headers=headers(csrf),
        )
        assert uploaded.status_code == 202, uploaded.get_json()
        document_id = uploaded.get_json()["id"]
        with app.app_context():
            assert process_next_document()
        assert client.get(f"/api/v1/me/documents/{document_id}").get_json()["status"] == "READY"
        extra_env["TEST_REVIEW_DOCUMENT_ID"] = document_id
    server = make_server("127.0.0.1", 0, app, threaded=True)
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        result = subprocess.run(
            [node, "--import", "./tests/setup-jsx.js", f"tests/us{story}-live.mjs"],
            cwd=ROOT / "frontend", capture_output=True, text=True, timeout=90,
            env={**os.environ, **extra_env, "TEST_API_BASE_URL": f"http://127.0.0.1:{server.server_port}"},
            encoding="utf-8", errors="replace",
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert f"US-{story} real HTTP integration passed" in result.stdout
        if story == "01-register":
            assert outbox == [("registration@example.test", "012345"),
                              ("registration-team@example.test", "012345")]
        if story == "01-reset":
            assert outbox == [("team@example.test", "012345")]
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
