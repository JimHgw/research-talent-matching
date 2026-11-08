"""FE-3 polling against real HTTP, storage, SQLite and the extraction Worker."""

import os
import subprocess
from threading import Event, Thread

from werkzeug.serving import make_server

from backend.src.shared.paths import ROOT
from backend.src.features.documents import worker
from backend.tests.test_frontend_integration import frontend_node
from backend.tests.test_us09_extraction import CV_TEXT, text_docx, upload


def test_fe3_slow_worker_polling(app, signed, request, tmp_path, monkeypatch):
    node = frontend_node(required=request.config.getoption("--require-frontend"))
    app.config["DOCUMENT_STORAGE_DIR"] = str(tmp_path / "documents")
    client, csrf = signed
    document_id = upload(client, csrf, text_docx(CV_TEXT), "fe3-synthetic-cv.docx")
    release_path = tmp_path / "release-worker"
    claimed, stop = Event(), Event()
    original_extract = worker.extract_document_text

    def slow_extract(path, media_type):
        # Delay only the real parser's start; do not stub extraction results or states.
        # The lease/status is committed by the actual Worker before entering here.
        claimed.set()
        while not release_path.exists():
            if stop.wait(0.05):
                raise RuntimeError("Slow-processing test stopped")
        return original_extract(path, media_type)

    monkeypatch.setattr(worker, "extract_document_text", slow_extract)

    def process():
        with app.app_context():
            worker.process_next_document()

    process_thread = Thread(target=process, daemon=True)
    server = make_server("127.0.0.1", 0, app, threaded=True)
    http_thread = Thread(target=server.serve_forever, daemon=True)
    http_thread.start()
    process_thread.start()
    try:
        assert claimed.wait(10), "Worker did not claim the uploaded file"
        assert client.get(f"/api/v1/me/documents/{document_id}").json["status"] == "PROCESSING"
        result = subprocess.run(
            [node, "--import", "./tests/setup-jsx.js", "tests/fe3-live.mjs"],
            cwd=ROOT / "frontend", capture_output=True, text=True, timeout=110,
            env={**os.environ, "TEST_API_BASE_URL": f"http://127.0.0.1:{server.server_port}",
                 "TEST_WORKER_RELEASE_PATH": str(release_path)},
            encoding="utf-8", errors="replace",
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert "FE-3 real slow Worker integration passed" in result.stdout
        process_thread.join(timeout=5)
        assert not process_thread.is_alive()
        assert client.get(f"/api/v1/me/documents/{document_id}").json["status"] == "READY"
    finally:
        stop.set()
        process_thread.join(timeout=5)
        server.shutdown()
        server.server_close()
        http_thread.join(timeout=5)
