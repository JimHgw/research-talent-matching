"""Run the US-09 React workflow against the real backend."""

import os
import subprocess
import sys
from threading import Thread

from docx import Document as DocxDocument
from werkzeug.serving import make_server

from backend.src.shared.paths import ROOT
from backend.tests.test_frontend_integration import frontend_node
from backend.tests.test_us09_extraction import CV_TEXT


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
    for line in CV_TEXT.replace("Python, SQL", "Python, SQL, COBOL").splitlines():
        document.add_paragraph(line)
    document.save(document_path)

    # Start the real HTTP server on an available local port.
    server = make_server("127.0.0.1", 0, app, threaded=True)
    http_thread = Thread(
        target=server.serve_forever,
        daemon=True,
    )

    http_thread.start()
    # Use the actual deployable CLI process rather than an in-test worker loop.
    worker_log = (tmp_path / "worker.log").open("w+", encoding="utf-8")
    worker = subprocess.Popen(
        [sys.executable, "-m", "flask", "--app", "backend.app", "process-documents"],
        cwd=ROOT, stdout=worker_log, stderr=subprocess.STDOUT,
        env={**os.environ, "FLASK_SKIP_DOTENV": "1", "COOKIE_SECURE": "false",
             "DATABASE_URL": app.config["DATABASE_URL"],
             "DOCUMENT_STORAGE_DIR": app.config["DOCUMENT_STORAGE_DIR"]},
    )

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

        worker_log.flush()
        worker_log.seek(0)
        assert result.returncode == 0, result.stdout + result.stderr + worker_log.read()
        assert "US-09 real HTTP integration passed" in result.stdout

    finally:
        worker.terminate()
        try:
            worker.wait(timeout=5)
        except subprocess.TimeoutExpired:
            worker.kill()
            worker.wait(timeout=5)
        worker_log.close()
        server.shutdown()
        server.server_close()
        http_thread.join(timeout=5)
