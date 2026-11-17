"""Run the US-09 React workflow against the real backend."""

import os
import subprocess
import json
import hashlib
from threading import Thread

import pytest
from werkzeug.serving import make_server

from backend.tests.worker_process_probe import Probe
from backend.src.shared.paths import ROOT
from backend.tests.test_frontend_integration import frontend_node
from backend.tests.test_us09_extraction import CV_TEXT, text_pdf, text_docx, upload, process
from backend.src.db.models import Document
from backend.src.features.documents.storage import stored_file_path


@pytest.mark.parametrize("format", ["pdf", "docx"])
def test_us09_real_frontend_workflow(app, request, tmp_path, format):
    node = frontend_node(
        required=request.config.getoption("--require-frontend")
    )

    app.config["DOCUMENT_STORAGE_DIR"] = str(
        tmp_path / "documents"
    )

    # Reuse the same synthetic CV for both real supported file formats.
    document_path = tmp_path / f"review-cv.{format}"
    encode = text_pdf if format == "pdf" else text_docx
    source = CV_TEXT.replace("Python, SQL", "Python, SQL, COBOL").replace(
        "Machine learning", "Machine learning; Climate-resilient urban systems")
    document_path.write_bytes(encode(source))

    # Start the real HTTP server on an available local port.
    server = make_server("127.0.0.1", 0, app, threaded=True)
    http_thread = Thread(
        target=server.serve_forever,
        daemon=True,
    )

    http_thread.start()
    # Track the actual Worker interpreter, including Windows launchers.
    worker = Probe(app, tmp_path, "daemon", 0)

    try:
        worker.receive("ready")
        worker.send("go")
        result = subprocess.run(
            [
                node,
                "--import",
                "./tests/setup-jsx.js",
                "tests/us09-live.mjs",
            ],
            cwd=ROOT / "frontend",
            capture_output=True,
            text=True,
            timeout=90,
            encoding="utf-8",
            errors="replace",
            env={
                **os.environ,
                "TEST_API_BASE_URL": (
                    f"http://127.0.0.1:{server.server_port}"
                ),
                "TEST_DOCUMENT_PATH": str(document_path),
                "TEST_DOCUMENT_NAME": document_path.name,
                "TEST_DOCUMENT_MEDIA_TYPE": ("application/pdf" if format == "pdf" else
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            },
        )

        assert result.returncode == 0, (
            result.stdout
            + result.stderr
            + worker.log_path.read_text(encoding="utf-8")
        )
        assert "US-09 real HTTP integration passed" in result.stdout

    finally:
        worker.close()
        server.shutdown()
        server.server_close()
        http_thread.join(timeout=5)


def test_task61_review_states_and_accounts(app, signed, request, tmp_path):
    """Prepare actual worker outcomes; no background worker can consume the queued case."""
    node = frontend_node(required=request.config.getoption("--require-frontend"))
    app.config["DOCUMENT_STORAGE_DIR"] = str(tmp_path / "documents")
    client, csrf = signed
    records, hashes = {}, {}
    for key, filename, content in (
        ("readyPdf", "ready-pdf.pdf", text_pdf(CV_TEXT)),
        ("readyWord", "ready-word.docx", text_docx(CV_TEXT)),
        ("empty", "empty.docx", text_docx("")),
        ("failed", "failed.docx", text_docx(CV_TEXT)),
        ("pending", "pending.docx", text_docx(CV_TEXT)),
    ):
        document_id = upload(client, csrf, content, filename)
        records[key] = document_id
        hashes[key] = hashlib.sha256(content).hexdigest()
        if key == "failed":
            # Exercise the real worker failure path for a damaged private file.
            with app.app_context(), app.extensions["database"].transaction() as db:
                stored_file_path(db.get(Document, document_id).storage_key).write_bytes(b"damaged original")
        if key != "pending":
            process(app)
        expected = "QUEUED" if key == "pending" else "FAILED" if key == "failed" else "READY"
        assert client.get(f"/api/v1/me/documents/{document_id}").json["status"] == expected

    server = make_server("127.0.0.1", 0, app, threaded=True)
    http_thread = Thread(target=server.serve_forever, daemon=True)
    http_thread.start()
    try:
        result = subprocess.run(
            [node, "--import", "./tests/setup-jsx.js", "tests/us61-live.mjs"],
            cwd=ROOT / "frontend", capture_output=True, text=True, timeout=90,
            env={**os.environ, "TEST_API_BASE_URL": f"http://127.0.0.1:{server.server_port}",
                 "TEST_REVIEW_DOCUMENTS_JSON": json.dumps({"ids": records, "hashes": hashes})},
            encoding="utf-8", errors="replace",
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert "US-61 real HTTP integration passed" in result.stdout
    finally:
        server.shutdown()
        server.server_close()
        http_thread.join(timeout=5)
