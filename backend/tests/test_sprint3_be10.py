"""Current-release workflow, correlated failures and sensitive-log boundaries."""

from copy import deepcopy
from datetime import datetime
import logging
import re

from sqlalchemy import select, text

from backend.src.app import create_app
from backend.src.db.models import DocumentProcessingLease
from backend.src.features.documents import worker
from backend.src.features.matching.semantic_runtime import model_config
from conftest import PASSWORD, headers, sign_in
from test_us04 import PROFILE, MATCHES, OPPORTUNITIES, checked, research_team
from test_us05 import share
from test_us09_extraction import CV_TEXT, text_docx, upload, process
from test_us09_worker import queued, expire
from test_us14 import opportunity

PRIVATE = "PRIVATE_RELEASE_CONTENT_PASSWORD_COOKIE_CSRF_MODEL_INPUT"


def test_release_database_identity(app, request, record_testsuite_property):
    database = app.extensions["database"]
    mysql = request.config.getoption("--run-mysql")
    assert database.engine.dialect.name == ("mysql" if mysql else "sqlite")
    with database.engine.connect() as connection:
        version = connection.scalar(text("SELECT VERSION()" if mysql else "SELECT sqlite_version()"))
    if mysql:
        assert version.startswith("8.4.")
    record_testsuite_property("BE10.database", database.engine.dialect.name)
    record_testsuite_property("BE10.databaseVersion", version)


def test_request_failure_is_correlated_without_sensitive_diagnostics(app, caplog):
    caplog.set_level(logging.INFO, logger=app.logger.name)
    def fail():
        raise RuntimeError(PRIVATE + " /private/resume.docx")
    app.add_url_rule("/_release_failure", "release_failure", fail, methods=["POST"])
    client = app.test_client()
    client.set_cookie("session", PRIVATE)
    response = client.post("/_release_failure?secret=" + PRIVATE,
        json={"password": PRIVATE, "resumeDescription": PRIVATE},
        headers={"X-CSRF-Token": PRIVATE, "Authorization": "Bearer " + PRIVATE})
    body = checked(response, "Error", 500)
    request_id = body["requestId"]
    assert response.headers["X-Request-Id"] == request_id
    messages = [r.getMessage() for r in caplog.records if request_id in r.getMessage()]
    assert len(messages) == 1
    assert "stage=request endpoint=release_failure status=500 category=INTERNAL_ERROR" in messages[0]
    assert "error_type=RuntimeError" in messages[0]
    assert re.search(r"duration_ms=\d+\.\d+", messages[0])
    assert PRIVATE not in caplog.text and "/private/resume.docx" not in caplog.text


def test_worker_cli_exposes_claim_reclaim_result_without_lease_secrets(app, queued, caplog):
    caplog.set_level(logging.INFO, logger=app.logger.name)
    with app.app_context():
        first = worker.claim_next_document()
    expire(app, queued)
    previous_level = app.logger.level
    try:
        # Verify the existing CLI enables lifecycle events from the default level.
        app.logger.setLevel(logging.WARNING)
        process(app)
    finally:
        app.logger.setLevel(previous_level)
    events = [r.getMessage() for r in caplog.records if f"job={queued}" in r.getMessage()]
    for expected in ("stage=claim outcome=CLAIMED", "stage=claim outcome=RECLAIMED",
                     "stage=parse outcome=OK", "stage=persist_result outcome=OK", "stage=process outcome=READY"):
        assert any(expected in event for event in events), events
    with app.extensions["database"].transaction() as db:
        token = db.scalar(select(DocumentProcessingLease.token).where(DocumentProcessingLease.document_id == queued))
    assert token != first["lease_token"]
    for secret in (token, first["lease_token"], app.config["DOCUMENT_STORAGE_DIR"], CV_TEXT, PASSWORD):
        assert secret not in "\n".join(events)


def release_flow(app, signed, research_team, tmp_path, monkeypatch, caplog, real_model=False):
    caplog.set_level(logging.INFO, logger=app.logger.name)
    app.config["DOCUMENT_STORAGE_DIR"] = str(tmp_path / "private-documents")
    prepare = app.test_cli_runner().invoke(args=["prepare-db"])
    assert prepare.exit_code == 0, prepare.output
    client, csrf = signed
    before = checked(client.get(PROFILE), "Profile")
    document_id = upload(client, csrf, text_docx(CV_TEXT), "release-cv.docx")
    process(app)
    extraction = checked(client.get(f"/api/v1/me/documents/{document_id}/extraction"), "Extraction")
    assert checked(client.get(PROFILE), "Profile") == before
    selected = {"skills": extraction["suggestedSections"]["skills"]}
    assert selected["skills"]
    apply_path = f"/api/v1/me/documents/{document_id}/apply"
    # A second real session edits while the review holds its original revision.
    other = app.test_client()
    other_csrf = sign_in(other)
    content = deepcopy(before["content"])
    content["displayName"] = "Current release applicant"
    newer = checked(other.put(PROFILE, json={"expectedRevision": before["revision"], "content": content},
        headers=headers(other_csrf)), "Profile")
    conflict = client.post(apply_path, json={"expectedProfileRevision": before["revision"], "sections": selected},
        headers=headers(csrf))
    failed = checked(conflict, "Error", 409)
    assert failed["error"]["code"] == "REVISION_CONFLICT"
    assert failed["requestId"] == conflict.headers["X-Request-Id"]
    assert any(failed["requestId"] in r.getMessage() and "category=REVISION_CONFLICT" in r.getMessage()
               for r in caplog.records)
    stale_write = other.put(PROFILE, json={"expectedRevision": before["revision"], "content": before["content"]},
        headers=headers(other_csrf))
    assert checked(stale_write, "Error", 409)["error"]["currentRevision"] == newer["revision"]
    assert checked(client.get(PROFILE), "Profile") == newer
    # Explicitly reload/review before retrying; there is no automatic stale retry.
    imported = checked(client.post(apply_path, json={"expectedProfileRevision": newer["revision"], "sections": selected},
        headers=headers(csrf)), "Profile")
    assert imported["confirmation"]["status"] == "UNCONFIRMED"
    assert imported["content"]["education"] == newer["content"]["education"]
    assert imported["content"]["displayName"] == newer["content"]["displayName"]
    confirmed = checked(client.post(PROFILE + "/confirmation", json={"expectedRevision": imported["revision"]},
        headers=headers(csrf)), "Profile")
    assert confirmed["confirmation"]["status"] == "CONFIRMED"
    item = opportunity(research_team, deadlineAt="2099-01-01T00:00:00Z", requirements=[{
        "id": "python", "kind": "SKILL", "label": "Python", "importance": "REQUIRED",
        "tagIds": [], "skillTitles": ["Python programming"],
    }])
    match_path = f"{MATCHES}/{item['id']}"
    match = checked(client.get(match_path), "OwnerMatch")
    assert match["profileRevision"] == confirmed["revision"]
    if real_model:
        assert match["summary"]["semanticRequirements"]["status"] == "AVAILABLE"
        assert match["summary"]["semanticRequirements"]["modelVersion"] == model_config()["modelVersion"]
        assert match["requirements"][0]["scoring"]["method"] == "SEMANTIC"
    share(signed, ["skills"])
    team_path = f"{OPPORTUNITIES}/{item['id']}/talent-matches/{confirmed['talentId']}"
    checked(research_team[0].get(team_path), "TeamMatch")
    share(signed, [], discoverable=False)
    checked(research_team[0].get(team_path), "Error", 404)

    def unavailable(texts):
        raise RuntimeError(PRIVATE + " /private/model/path")
    app.config["SEMANTIC_MATCHING_ENABLED"] = True
    monkeypatch.setattr(app.extensions["semantic_matching"], "encode", unavailable)
    response = client.get(match_path)
    fallback = checked(response, "OwnerMatch")
    assert fallback["summary"]["semanticRequirements"]["status"] == "UNAVAILABLE"
    assert app.test_client().get("/healthz").status_code == 200
    assert any(response.headers["X-Request-Id"] in r.getMessage() and "stage=semantic outcome=FALLBACK" in r.getMessage()
               for r in caplog.records)
    assert PRIVATE not in caplog.text and "/private/model/path" not in caplog.text
    for secret in (csrf, other_csrf, PASSWORD, CV_TEXT, str(tmp_path)):
        assert secret not in caplog.text
    monkeypatch.setattr("backend.src.features.opportunities.availability.utcnow", lambda: datetime(2099, 1, 1))
    monkeypatch.setattr("backend.src.features.opportunities.service.utcnow", lambda: datetime(2099, 1, 1))
    assert checked(client.get(match_path), "Error", 409)["error"]["code"] == "OPPORTUNITY_EXPIRED"
    path = f"{OPPORTUNITIES}/{item['id']}"
    future = {**item["content"], "deadlineAt": "2099-02-01T00:00:00Z"}
    edited = checked(research_team[0].put(path, json={"expectedRevision": item["revision"], "content": future},
        headers=headers(research_team[1])), "Opportunity")
    assert edited["availabilityStatus"] == "EXPIRED"
    reopened = checked(research_team[0].put(path, json={"expectedRevision": edited["revision"],
        "content": future, "reopen": True}, headers=headers(research_team[1])), "Opportunity")
    assert reopened["availabilityStatus"] == "ACTIVE"
    restarted = create_app({**app.config, "SEMANTIC_MATCHING_ENABLED": False})
    try:
        reader = restarted.test_client()
        sign_in(reader)
        assert checked(reader.get(PROFILE), "Profile") == confirmed
        assert checked(reader.get(f"/api/v1/me/documents/{document_id}/extraction"), "Extraction") == extraction
        assert reader.get("/healthz").status_code == 200
    finally:
        restarted.extensions["database"].engine.dispose()


def test_release_document_conflict_privacy_fallback_expiry_flow(app, signed, research_team, tmp_path, monkeypatch, caplog):
    release_flow(app, signed, research_team, tmp_path, monkeypatch, caplog)


def test_release_flow_actual_model(application_model, app, signed, research_team, tmp_path, monkeypatch, caplog):
    app.config["SEMANTIC_MATCHING_ENABLED"] = True
    app.extensions["semantic_matching"].directory = application_model
    release_flow(app, signed, research_team, tmp_path, monkeypatch, caplog, real_model=True)
