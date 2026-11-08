"""FE-4 reconciliation and account isolation against real HTTP and SQLite."""

from datetime import timedelta
import json
import os
import subprocess
from threading import Thread

from werkzeug.serving import make_server

from backend.src.db.models import Opportunity, utcnow
from backend.src.shared.paths import ROOT
from backend.tests.conftest import headers, sign_in
from backend.tests.test_frontend_integration import frontend_node


def test_fe4_editor_recovery_and_sessions(app, request):
    node = frontend_node(required=request.config.getoption("--require-frontend"))
    client = app.test_client()
    csrf = sign_in(client, "team@example.test")
    content = json.loads((ROOT / "docs/api/examples/opportunity-create.json").read_text())
    created = client.post("/api/v1/opportunities", json=content, headers=headers(csrf))
    assert created.status_code == 201, created.json
    opportunity = created.json
    published = client.post(f"/api/v1/opportunities/{opportunity['id']}/publish",
                            json={"expectedRevision": opportunity["revision"]}, headers=headers(csrf))
    assert published.status_code == 200, published.json
    # Seed actual expiry without waiting or changing the production clock.
    with app.extensions["database"].transaction(write=True) as db:
        db.get(Opportunity, opportunity["id"]).deadline_at = utcnow() - timedelta(days=1)

    server = make_server("127.0.0.1", 0, app, threaded=True)
    http = Thread(target=server.serve_forever, daemon=True)
    http.start()
    try:
        result = subprocess.run(
            [node, "--import", "./tests/setup-jsx.js", "tests/fe4-live.mjs"],
            cwd=ROOT / "frontend", capture_output=True, text=True, timeout=120,
            env={**os.environ, "TEST_API_BASE_URL": f"http://127.0.0.1:{server.server_port}",
                 "TEST_FE4_EXPIRED_OPPORTUNITY": opportunity["id"]},
            encoding="utf-8", errors="replace",
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert "FE-4 real HTTP recovery and account isolation passed" in result.stdout
    finally:
        server.shutdown()
        server.server_close()
        http.join(timeout=5)
