"""Persistent document leases with fenced writes and safe stage diagnostics."""

from contextlib import contextmanager
from datetime import timedelta
import logging
from secrets import token_hex
from time import perf_counter

from flask import current_app
from sqlalchemy import and_, or_, select

from ...db.database import database
from ...db.models import Document, DocumentExtraction, DocumentProcessingLease, Tag, utcnow
from ...shared.validation import validator
from .storage import stored_file_path
from .suggestions import build_extraction_result
from .text import extract_document_text


def _diagnostic(document_id, stage, outcome, *, error=None, duration_ms=None, attempts=None):
    # Never log exception messages, resume text, storage paths or lease tokens.
    current_app.logger.log(
        logging.ERROR if error is not None else logging.INFO,
        "Document job=%s stage=%s outcome=%s error_type=%s duration_ms=%s attempts=%s",
        document_id,
        stage,
        outcome,
        type(error).__name__ if error is not None else "-",
        duration_ms if duration_ms is not None else "-",
        attempts if attempts is not None else "-",
    )


@contextmanager
def _stage(document_id, name):
    started = perf_counter()
    event = {"outcome": "OK"}
    try:
        yield event
    except Exception as error:
        _diagnostic(
            document_id,
            name,
            "ERROR",
            error=error,
            duration_ms=round((perf_counter() - started) * 1000, 2),
        )
        raise
    else:
        _diagnostic(
            document_id,
            name,
            event["outcome"],
            duration_ms=round((perf_counter() - started) * 1000, 2),
        )


def claim_next_document():
    timeout = timedelta(seconds=current_app.config["DOCUMENT_PROCESSING_TIMEOUT"])
    with database().transaction(write=True) as db:
        now = utcnow()
        # Serialise claim/reclaim with all result writes.
        document = db.scalar(
            select(Document)
            .outerjoin(
                DocumentProcessingLease,
                DocumentProcessingLease.document_id == Document.id,
            )
            .where(or_(
                Document.status == "QUEUED",
                and_(
                    Document.status == "PROCESSING",
                    or_(
                        DocumentProcessingLease.expires_at <= now,
                        and_(
                            DocumentProcessingLease.document_id.is_(None),
                            Document.updated_at <= now - timeout,
                        ),
                    ),
                ),
            ))
            .order_by(Document.created_at.asc(), Document.id.asc())
            .limit(1)
        )
        if document is None:
            return None

        document_id = document.id
        reclaim = document.status == "PROCESSING"
        lease = db.get(DocumentProcessingLease, document_id)
        legacy = reclaim and lease is None

        if (
            lease is not None
            and lease.attempts >= current_app.config["DOCUMENT_PROCESSING_MAX_ATTEMPTS"]
        ):
            _fail(
                document,
                "Processing repeatedly timed out. Try another file or enter your information manually.",
            )
            attempts = lease.attempts
            outcome = "ATTEMPTS_EXHAUSTED"
            job = None
        else:
            if lease is None:
                lease = DocumentProcessingLease(
                    document_id=document_id,
                    attempts=1,
                    token=token_hex(16),
                    expires_at=now + timeout,
                )
                db.add(lease)
            else:
                lease.attempts += 1
                lease.token = token_hex(16)
                lease.expires_at = now + timeout

            document.status = "PROCESSING"
            document.updated_at = now
            db.flush()

            attempts = lease.attempts
            outcome = (
                "RECOVERED_LEGACY" if legacy
                else "RECLAIMED" if reclaim
                else "CLAIMED"
            )
            job = {
                "document_id": document_id,
                "storage_key": document.storage_key,
                "media_type": document.media_type,
                "kind": document.kind,
                "lease_token": lease.token,
            }

    # Report claims only after the transaction commits.
    _diagnostic(document_id, "claim", outcome, attempts=attempts)
    return job


def _owns_lease(db, document, token):
    if document is None or document.status != "PROCESSING":
        return False
    lease = db.get(DocumentProcessingLease, document.id)
    return (
        lease is not None
        and lease.token == token
        and lease.expires_at > utcnow()
    )


def _fail(document, message):
    document.status = "FAILED"
    document.error = {
        "code": "EXTRACTION_FAILED",
        "message": message,
        "fieldErrors": [],
    }
    document.updated_at = utcnow()


def save_extraction_result(document_id, result, lease_token):
    # Validate before opening the write transaction.
    with _stage(document_id, "validate"):
        validator("Extraction").validate(result)
        if result["documentId"] != document_id:
            raise ValueError("Extraction result does not match the document.")

    with _stage(document_id, "persist_result") as event:
        with database().transaction(write=True) as db:
            document = db.get(Document, document_id)
            if not _owns_lease(db, document, lease_token):
                event["outcome"] = "STALE"
            else:
                db.add(DocumentExtraction(
                    document_id=document_id,
                    result=result,
                ))
                document.status = "READY"
                document.error = None
                document.updated_at = utcnow()
                db.flush()

    return event["outcome"] == "OK"


def save_extraction_failure(document_id, lease_token):
    with _stage(document_id, "persist_failure") as event:
        with database().transaction(write=True) as db:
            document = db.get(Document, document_id)
            if not _owns_lease(db, document, lease_token):
                event["outcome"] = "STALE"
            else:
                _fail(
                    document,
                    "The document could not be processed. Try another file or enter your information manually.",
                )
                db.flush()

    return event["outcome"] == "OK"


def process_next_document():
    job = claim_next_document()
    if job is None:
        return False

    document_id = job["document_id"]

    try:
        with _stage(document_id, "file"):
            path = stored_file_path(job["storage_key"])

        with _stage(document_id, "parse"):
            text = extract_document_text(path, job["media_type"])

        with _stage(document_id, "read_tags"):
            with database().transaction() as db:
                tags = [
                    {
                        "id": tag.id,
                        "label": tag.label,
                        "kind": tag.kind,
                    }
                    for tag in db.scalars(
                        select(Tag)
                        .where(Tag.kind == "INTEREST")
                        .order_by(Tag.id.asc())
                    )
                ]

        with _stage(document_id, "extract"):
            result = build_extraction_result(document_id, text, tags)

        saved = save_extraction_result(
            document_id, result, job["lease_token"]
        )
        _diagnostic(document_id, "process", "READY" if saved else "STALE")
    except Exception as error:
        _diagnostic(document_id, "process", "ERROR", error=error)
        save_extraction_failure(document_id, job["lease_token"])

    return True
