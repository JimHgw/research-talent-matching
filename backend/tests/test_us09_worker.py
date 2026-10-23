"""Persistent claims, crash recovery and fencing against stale worker writes."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest

from backend.src.db.models import Document, DocumentProcessingLease, utcnow
from backend.src.features.documents.worker import (
    claim_next_document, save_extraction_result, save_extraction_failure,
)
from backend.src.features.documents.suggestions import build_extraction_result
from backend.src.features.documents.storage import stored_file_path
from backend.tests.conftest import headers
from backend.tests.test_us09_extraction import text_docx, upload, process, TAGS


@pytest.fixture
def queued(app, signed, tmp_path):
    client, csrf = signed
    app.config["DOCUMENT_STORAGE_DIR"] = str(tmp_path / "documents")
    return upload(client, csrf, text_docx("Skills: Python"), "cv.docx")


def claim(app):
    with app.app_context():
        return claim_next_document()


def expire(app, document_id):
    with app.extensions["database"].transaction(write=True) as db:
        db.get(DocumentProcessingLease, document_id).expires_at = utcnow() - timedelta(seconds=1)


def test_unexpired_job_is_not_claimed_again(app, queued):
    first = claim(app)
    assert first["document_id"] == queued
    assert claim(app) is None


def test_worker_restart_recovers_abandoned_claim(app, signed, queued):
    claim(app)  # Simulate a worker exiting after it committed PROCESSING.
    expire(app, queued)
    process(app)
    result = signed[0].get(f"/api/v1/me/documents/{queued}/extraction")
    assert result.status_code == 200, result.json
    assert result.json["suggestedSections"]["skills"][0]["title"] == "Python"
    with app.extensions["database"].transaction() as db:
        assert db.get(DocumentProcessingLease, queued).attempts == 2


def test_stale_success_and_failure_cannot_overwrite_new_claim(app, queued):
    first = claim(app)
    expire(app, queued)
    result = build_extraction_result(queued, "Skills: Python", TAGS)
    with app.app_context():
        # Expiry alone fences writes, even before another worker reclaims it.
        assert not save_extraction_result(queued, result, first["lease_token"])
        assert not save_extraction_failure(queued, first["lease_token"])
    second = claim(app)
    assert first["lease_token"] != second["lease_token"]
    with app.app_context():
        assert not save_extraction_result(queued, result, first["lease_token"])
        assert not save_extraction_failure(queued, first["lease_token"])
        assert save_extraction_result(queued, result, second["lease_token"])
        assert not save_extraction_failure(queued, second["lease_token"])
        assert not save_extraction_result(queued, result, second["lease_token"])


def test_repeated_timeouts_become_actionable_failure_without_blocking_manual_edit(app, signed, queued):
    app.config["DOCUMENT_PROCESSING_MAX_ATTEMPTS"] = 2
    assert claim(app)
    expire(app, queued)
    assert claim(app)
    expire(app, queued)
    assert claim(app) is None
    client, csrf = signed
    response = client.get(f"/api/v1/me/documents/{queued}")
    assert response.json["status"] == "FAILED"
    assert "manually" in response.json["error"]["message"]
    assert client.get(f"/api/v1/me/documents/{queued}/extraction").status_code == 422
    before = client.get("/api/v1/me/profile").json
    response = client.put("/api/v1/me/profile", headers=headers(csrf),
                          json={"expectedRevision": before["revision"],
                                "content": {**before["content"], "displayName": "Manually edited"}})
    assert response.status_code == 200, response.json


@pytest.mark.parametrize("abandoned", [False, True])
def test_concurrent_workers_claim_only_one_attempt(app, queued, abandoned):
    if abandoned:
        claim(app)
        expire(app, queued)
    with ThreadPoolExecutor(max_workers=2) as workers:
        claims = list(workers.map(lambda _: claim(app), range(2)))
    assert sum(job is not None for job in claims) == 1
    with app.extensions["database"].transaction() as db:
        assert db.get(DocumentProcessingLease, queued).attempts == (2 if abandoned else 1)


def test_pre_upgrade_processing_document_is_recovered(app, queued):
    with app.extensions["database"].transaction(write=True) as db:
        document = db.get(Document, queued)
        document.status = "PROCESSING"
        document.updated_at = utcnow() - timedelta(seconds=301)
    process(app)
    with app.extensions["database"].transaction() as db:
        assert db.get(Document, queued).status == "READY"
        assert db.get(DocumentProcessingLease, queued).attempts == 1


def test_cli_adds_missing_lease_table_without_recreating_existing_documents(app, queued):
    DocumentProcessingLease.__table__.drop(app.extensions["database"].engine)
    process(app)
    with app.extensions["database"].transaction() as db:
        assert db.get(Document, queued).status == "READY"
        assert db.get(DocumentProcessingLease, queued).attempts == 1


def test_invalid_result_does_not_end_or_replace_claim(app, queued):
    job = claim(app)
    with app.app_context(), pytest.raises(ValueError):
        save_extraction_result(queued, build_extraction_result("doc_other", "Skills: Python", TAGS),
                               job["lease_token"])
    with app.extensions["database"].transaction() as db:
        assert db.get(Document, queued).status == "PROCESSING"


@pytest.mark.parametrize("damage", ["missing", "corrupt"])
def test_actual_missing_or_corrupt_original_fails_safely(app, signed, queued, damage):
    client, _ = signed
    before = client.get("/api/v1/me/profile").json
    with app.app_context(), app.extensions["database"].transaction() as db:
        path = stored_file_path(db.get(Document, queued).storage_key)
    if damage == "missing":
        path.unlink()
    else:
        path.write_bytes(b"damaged original")
    process(app)
    response = client.get(f"/api/v1/me/documents/{queued}")
    assert response.json["status"] == "FAILED"
    assert "manually" in response.json["error"]["message"]
    assert client.get("/api/v1/me/profile").json == before
