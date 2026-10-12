"""Run the US-09 React workflow against the real backend."""

import os
import subprocess
from threading import Event, Thread

from docx import Document as DocxDocument
from werkzeug.serving import make_server

from backend.src.features.documents.worker import process_next_document
from backend.src.shared.paths import ROOT
from backend.tests.test_frontend_integration import frontend_node


def test_us09_real_frontend_workflow(app, request, tmp_path):
    node = frontend_node(
        required=request.config.getoption("--require-frontend")
    )

    app.config["DOCUMENT_STORAGE_DIR"] = str(
        tmp_path / "documents"
    )

    # Prepare a real Word document for the React upload form.
    document_path = tmp_path / "review-cv.docx"
    document = DocxDocument()
    document.add_paragraph("Skills: Python, SQL")
    document.add_paragraph(
        "Research interests: Machine learning"
    )
    document.save(document_path)

    # Start the real HTTP server on an available local port.
    server = make_server("127.0.0.1", 0, app, threaded=True)
    http_thread = Thread(
        target=server.serve_forever,
        daemon=True,
    )

    # Process uploaded documents while the React test runs.
    stop = Event()

    def process_documents():
        with app.app_context():
            while not stop.is_set():
                if not process_next_document():
                    stop.wait(0.05)

    document_thread = Thread(
        target=process_documents,
        daemon=True,
    )

    http_thread.start()
    document_thread.start()

    try:
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
            },
        )

        assert result.returncode == 0, result.stdout + result.stderr
        assert "US-09 real HTTP integration passed" in result.stdout

    finally:
        stop.set()
        document_thread.join(timeout=5)
        server.shutdown()
        server.server_close()
        http_thread.join(timeout=5)