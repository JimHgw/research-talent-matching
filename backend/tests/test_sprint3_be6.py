"""BE-6: independent processes, recovery, fencing and safe diagnostics."""

from copy import deepcopy
from datetime import datetime, timezone
from io import BytesIO
import json
import logging
from pathlib import Path
import sys
import time

import pytest
from jsonschema import ValidationError
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session

from backend.src.db.models import (
    Document,
    DocumentExtraction,
    DocumentProcessingLease,
    utcnow,
)
from backend.src.features.documents import worker
from backend.src.features.documents.suggestions import build_extraction_result
from backend.src.shared.validation import validator
from backend.tests.worker_process_probe import Probe, TIMEOUT
from conftest import headers
from test_us09_extraction import TAGS, text_docx
from test_us09_worker import claim, expire, queued


PROFILE = "/api/v1/me/profile"
PRIVATE = "BE6_PRIVATE_RESUME_BODY_MUST_NOT_BE_LOGGED"


@pytest.fixture
def probes(app, tmp_path):
    active = []

    def start(action):
        probe = Probe(app, tmp_path, action, len(active) + 1)
        active.append(probe)
        probe.receive("ready")
        return probe

    yield start

    for probe in reversed(active):
        probe.close()


def state(app, document_id):
    with app.extensions["database"].transaction() as db:
        document = db.get(Document, document_id)
        lease = db.get(DocumentProcessingLease, document_id)
        result = db.get(DocumentExtraction, document_id)

        return {
            "status": document.status,
            "error": deepcopy(document.error),
            "updated_at": document.updated_at,
            "attempts": lease.attempts if lease else 0,
            "token": lease.token if lease else None,
            "expires_at": lease.expires_at if lease else None,
            "result": deepcopy(result.result) if result else None,
            "extraction_count": db.scalar(
                select(func.count())
                .select_from(DocumentExtraction)
                .where(DocumentExtraction.document_id == document_id)
            ),
        }


def run_once(probes):
    probe = probes("process")
    probe.send("go")
    assert probe.finish()["cli_finished"]
    return probe


def assert_manual_edit(signed):
    client, csrf = signed
    before = client.get(PROFILE).get_json()
    content = deepcopy(before["content"])
    content["displayName"] = "Manually maintained during processing"

    response = client.put(
        PROFILE,
        json={
            "expectedRevision": before["revision"],
            "content": content,
        },
        headers=headers(csrf),
    )

    assert response.status_code == 200, response.get_json()
    return response.get_json()


@pytest.mark.parametrize("reclaim", [False, True])
def test_independent_processes_claim_only_one_lease(
    app, queued, probes, reclaim
):
    if reclaim:
        claim(app)
        expire(app, queued)

    first, second = probes("claim"), probes("claim")
    first.send("go")
    second.send("go")
    results = [first.finish(), second.finish()]

    assert first.worker_pid != second.worker_pid
    assert sum(result["claimed"] for result in results) == 1

    claimed = next(result for result in results if result["claimed"])
    assert claimed["document_id"] == queued

    current = state(app, queued)
    assert current["status"] == "PROCESSING"
    assert current["attempts"] == (2 if reclaim else 1)
    assert current["extraction_count"] == 0


def test_killed_process_recovers_after_natural_lease_expiry(
    app, signed, queued, probes, tmp_path
):
    app.config["DOCUMENT_PROCESSING_TIMEOUT"] = 3
    started_at = datetime.now(timezone.utc).isoformat()

    first = probes("hold")
    first.send("go")
    first.receive("parsing")

    original = state(app, queued)
    assert original["status"] == "PROCESSING"
    assert original["attempts"] == 1

    # Save through the real API while another process is blocked in parsing.
    profile = assert_manual_edit(signed)

    first.stop()
    terminated = first.process.returncode
    assert terminated != 0

    stopped = state(app, queued)
    assert stopped["status"] == "PROCESSING"
    assert stopped["extraction_count"] == 0

    # Wait for real expiry; do not modify lease timestamps in this scenario.
    deadline = time.monotonic() + TIMEOUT
    while state(app, queued)["expires_at"] > utcnow():
        assert time.monotonic() < deadline, "Lease did not naturally expire."
        time.sleep(0.05)

    second = run_once(probes)
    recovered = state(app, queued)

    assert recovered["status"] == "READY"
    assert recovered["attempts"] == 2
    assert recovered["token"] != original["token"]
    assert recovered["extraction_count"] == 1
    assert recovered["result"]["documentId"] == queued

    validator("Extraction").validate(recovered["result"])

    assert signed[0].get(PROFILE).get_json() == profile
    assert second.worker_pid != first.worker_pid

    # Exclude credentials, raw lease tokens, private paths and resume text.
    record = {
        "scenario": "actual-process-stop-natural-expiry-restart",
        "startedAtUtc": started_at,
        "finishedAtUtc": datetime.now(timezone.utc).isoformat(),
        "database": app.extensions["database"].engine.dialect.name,
        "python": sys.version.split()[0],
        "documentId": queued,
        "firstWorkerPid": first.worker_pid,
        "firstWorkerExitCode": terminated,
        "secondWorkerPid": second.worker_pid,
        "secondWorkerExitCode": second.process.returncode,
        "leaseTimeoutSeconds": 3,
        "leaseExpiry": "natural; no timestamp injection",
        "states": [
            "QUEUED",
            "PROCESSING",
            "PROCESSING after stop",
            "READY",
        ],
        "attempts": [original["attempts"], recovered["attempts"]],
        "leaseTokenRotated": True,
        "validExtractionCount": recovered["extraction_count"],
        "manualSaveWhileParserBlocked": True,
        "profileUnchangedByRecovery": True,
    }

    (tmp_path / "process-restart.json").write_text(
        json.dumps(record, indent=2) + "\n",
        encoding="utf-8",
    )


@pytest.mark.parametrize("late_outcome", ["success", "failure"])
@pytest.mark.parametrize("new_state", ["PROCESSING", "READY"])
def test_late_process_cannot_overwrite_new_lease_or_ready(
    app, queued, probes, late_outcome, new_state
):
    first = probes("hold")
    first.send("go")
    first.receive("parsing")

    original = state(app, queued)
    expire(app, queued)

    second = probes(
        "hold" if new_state == "PROCESSING" else "process"
    )
    second.send("go")

    if new_state == "PROCESSING":
        second.receive("parsing")
    else:
        assert second.finish()["cli_finished"]

    before_late = state(app, queued)
    assert before_late["status"] == new_state
    assert before_late["attempts"] == 2
    assert before_late["token"] != original["token"]

    first.send(late_outcome)
    assert first.finish()["cli_finished"]

    assert state(app, queued) == before_late

    if new_state == "PROCESSING":
        second.send("success")
        assert second.finish()["cli_finished"]

    final = state(app, queued)
    assert final["status"] == "READY"
    assert final["extraction_count"] == 1
    assert final["result"]["documentId"] == queued


def test_maximum_attempts_survive_process_restarts(
    app, signed, queued, probes
):
    app.config["DOCUMENT_PROCESSING_MAX_ATTEMPTS"] = 2

    for attempt in (1, 2):
        process = probes("claim")
        process.send("go")
        assert process.finish()["claimed"]
        assert state(app, queued)["attempts"] == attempt
        expire(app, queued)

    exhausted = probes("process")
    exhausted.send("go")
    assert not exhausted.finish()["cli_finished"]

    current = state(app, queued)
    assert current["status"] == "FAILED"
    assert current["attempts"] == 2
    assert current["extraction_count"] == 0
    assert "manually" in current["error"]["message"]

    response = signed[0].get(
        f"/api/v1/me/documents/{queued}/extraction"
    )
    assert response.status_code == 422

    assert "outcome=ATTEMPTS_EXHAUSTED" in (
        exhausted.log_path.read_text(encoding="utf-8")
    )
    assert_manual_edit(signed)


@pytest.mark.parametrize("invalid", ["identity", "schema"])
def test_rejected_result_keeps_claim_until_lease_recovery(
    app, queued, probes, caplog, invalid
):
    caplog.set_level(logging.INFO, logger=app.logger.name)
    job = claim(app)
    result = build_extraction_result(queued, "Skills: Python", TAGS)

    if invalid == "identity":
        result["documentId"] = "doc_other"
        exception = ValueError
    else:
        result["reviewRequired"] = PRIVATE
        exception = ValidationError

    before = state(app, queued)

    with app.app_context(), pytest.raises(exception):
        worker.save_extraction_result(
            queued, result, job["lease_token"]
        )

    assert state(app, queued) == before
    assert "stage=validate outcome=ERROR" in caplog.text
    assert PRIVATE not in caplog.text
    assert job["lease_token"] not in caplog.text

    expire(app, queued)
    run_once(probes)

    recovered = state(app, queued)
    assert recovered["status"] == "READY"
    assert recovered["attempts"] == 2
    assert recovered["extraction_count"] == 1


@pytest.mark.parametrize("fault,stage", [
    ("missing", "file"),
    ("corrupt", "parse"),
    ("parser", "parse"),
    ("extractor", "extract"),
    ("schema", "validate"),
    ("identity", "validate"),
])
def test_failures_report_safe_stage_and_preserve_manual_edit(
    app, signed, queued, monkeypatch, caplog, fault, stage
):
    caplog.set_level(logging.INFO, logger=app.logger.name)
    before = signed[0].get(PROFILE).get_json()

    with app.extensions["database"].transaction() as db:
        private_path = (
            Path(app.config["DOCUMENT_STORAGE_DIR"])
            / db.get(Document, queued).storage_key
        )

    def fail(*args, **kwargs):
        raise RuntimeError(f"{PRIVATE} {private_path}")

    if fault == "missing":
        private_path.unlink()
    elif fault == "corrupt":
        private_path.write_bytes(b"broken docx archive")
    elif fault == "parser":
        monkeypatch.setattr(worker, "extract_document_text", fail)
    elif fault == "extractor":
        monkeypatch.setattr(worker, "build_extraction_result", fail)
    else:
        result = build_extraction_result(
            queued, "Skills: Python", TAGS
        )
        result[
            "reviewRequired" if fault == "schema" else "documentId"
        ] = PRIVATE if fault == "schema" else "doc_other"

        monkeypatch.setattr(
            worker, "build_extraction_result", lambda *args: result
        )

    with app.app_context():
        assert worker.process_next_document()

    current = state(app, queued)
    assert current["status"] == "FAILED"
    assert current["extraction_count"] == 0
    assert "manually" in current["error"]["message"]
    assert f"stage={stage} outcome=ERROR" in caplog.text

    assert PRIVATE not in caplog.text
    assert str(private_path) not in caplog.text
    assert current["token"] not in caplog.text

    assert signed[0].get(PROFILE).get_json() == before
    assert_manual_edit(signed)


@pytest.mark.parametrize("operation", ["claim", "result", "failure"])
def test_commit_failure_rolls_back_worker_state(
    app, queued, caplog, operation
):
    caplog.set_level(logging.INFO, logger=app.logger.name)
    job = claim(app) if operation != "claim" else None
    before = state(app, queued)
    engine = app.extensions["database"].engine

    def fail_commit(connection):
        raise RuntimeError(PRIVATE)

    event.listen(engine, "commit", fail_commit)
    try:
        with app.app_context(), pytest.raises(RuntimeError):
            if operation == "claim":
                worker.claim_next_document()
            elif operation == "result":
                worker.save_extraction_result(
                    queued,
                    build_extraction_result(
                        queued, "Skills: Python", TAGS
                    ),
                    job["lease_token"],
                )
            else:
                worker.save_extraction_failure(
                    queued, job["lease_token"]
                )
    finally:
        event.remove(engine, "commit", fail_commit)

    assert state(app, queued) == before
    assert PRIVATE not in caplog.text

    if operation == "claim":
        assert "outcome=CLAIMED" not in caplog.text
        assert claim(app)["document_id"] == queued
    else:
        with app.app_context():
            if operation == "result":
                assert worker.save_extraction_result(
                    queued,
                    build_extraction_result(
                        queued, "Skills: Python", TAGS
                    ),
                    job["lease_token"],
                )
            else:
                assert worker.save_extraction_failure(
                    queued, job["lease_token"]
                )


@pytest.mark.parametrize("phase", ["flush", "commit"])
def test_upload_registration_failure_cleans_saved_file(
    app, signed, tmp_path, caplog, phase
):
    caplog.set_level(logging.INFO, logger=app.logger.name)
    directory = tmp_path / "private-upload"
    app.config["DOCUMENT_STORAGE_DIR"] = str(directory)
    before = signed[0].get(PROFILE).get_json()
    observed = []

    def before_flush(session, context, instances):
        if any(
            isinstance(row, Document)
            for row in session.new
        ):
            observed.extend(directory.iterdir())
            assert len(observed) == 1
            session.info["be6_registration"] = True
            if phase == "flush":
                raise RuntimeError(PRIVATE)

    def before_commit(session):
        if (
            phase == "commit"
            and session.info.get("be6_registration")
        ):
            raise RuntimeError(PRIVATE)

    event.listen(Session, "before_flush", before_flush)
    event.listen(Session, "before_commit", before_commit)
    try:
        response = signed[0].post(
            "/api/v1/me/documents",
            headers=headers(signed[1]),
            data={
                "kind": "CV",
                "file": (
                    BytesIO(text_docx(PRIVATE)),
                    "private-resume.docx",
                ),
            },
        )
    finally:
        event.remove(Session, "before_flush", before_flush)
        event.remove(Session, "before_commit", before_commit)

    assert response.status_code == 500, response.get_json()
    validator("Error").validate(response.get_json())

    assert observed
    assert all(not path.exists() for path in observed)
    assert list(directory.iterdir()) == []

    with app.extensions["database"].transaction() as db:
        assert db.scalar(
            select(func.count()).select_from(Document)
        ) == 0
        assert db.scalar(
            select(func.count()).select_from(DocumentExtraction)
        ) == 0

    assert signed[0].get(PROFILE).get_json() == before
    assert PRIVATE not in caplog.text
    assert "private-resume.docx" not in caplog.text
    assert str(directory) not in caplog.text

    assert_manual_edit(signed)
