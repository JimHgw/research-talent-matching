"""Background processing for uploaded documents."""

from datetime import timedelta
from secrets import token_hex

from sqlalchemy import and_, or_, select

from ...db.database import database
from ...db.models import Document, DocumentExtraction, DocumentProcessingLease, Tag, utcnow
from ...shared.validation import validator

from flask import current_app

from .storage import stored_file_path
from .text import extract_document_text
from .suggestions import build_extraction_result


def claim_next_document():
    timeout = timedelta(seconds=current_app.config["DOCUMENT_PROCESSING_TIMEOUT"])
    with database().transaction(write=True) as db:
        now = utcnow()
        # The database write lock serialises claim/reclaim with all result writes.
        document = db.scalar(
            select(Document)
            .outerjoin(DocumentProcessingLease, DocumentProcessingLease.document_id == Document.id)
            .where(or_(
                Document.status == "QUEUED",
                and_(Document.status == "PROCESSING", or_(
                    DocumentProcessingLease.expires_at <= now,
                    and_(DocumentProcessingLease.document_id.is_(None), Document.updated_at <= now - timeout),
                )),
            ))
            .order_by(Document.created_at.asc(), Document.id.asc())
            .limit(1)
        )

        if document is None:
            return None

        lease = db.get(DocumentProcessingLease, document.id)
        if lease is not None and lease.attempts >= current_app.config["DOCUMENT_PROCESSING_MAX_ATTEMPTS"]:
            _fail(document, "Processing repeatedly timed out. Try another file or enter your information manually.")
            return None
        if lease is None:
            lease = DocumentProcessingLease(document_id=document.id, attempts=1,
                                            token=token_hex(16), expires_at=now + timeout)
            db.add(lease)
        else:
            lease.attempts += 1
            lease.token = token_hex(16)
            lease.expires_at = now + timeout
        document.status = "PROCESSING"
        document.updated_at = now
        db.flush()

        return {
            "document_id": document.id,
            "storage_key": document.storage_key,
            "media_type": document.media_type,
            "kind": document.kind,
            "lease_token": lease.token,
        }

def _owns_lease(db, document, token):
    if document is None or document.status != "PROCESSING":
        return False
    lease = db.get(DocumentProcessingLease, document.id)
    return lease is not None and lease.token == token and lease.expires_at > utcnow()


def _fail(document, message):
    document.status = "FAILED"
    document.error = {"code": "EXTRACTION_FAILED", "message": message, "fieldErrors": []}
    document.updated_at = utcnow()


def save_extraction_result(document_id, result, lease_token):
    validator("Extraction").validate(result)

    if result["documentId"] != document_id:
        raise ValueError("Extraction result does not match the document.")

    with database().transaction(write=True) as db:
        document = db.get(Document, document_id)

        if not _owns_lease(db, document, lease_token):
            return False

        db.add(
            DocumentExtraction(
                document_id=document_id,
                result = result,
            )
        )

        document.status = "READY"
        document.error = None
        document.updated_at = utcnow()
        db.flush()

    return True

def save_extraction_failure(document_id, lease_token):
    with database().transaction(write=True) as db:
        document = db.get(Document, document_id)

        if not _owns_lease(db, document, lease_token):
            return False

        _fail(document, "The document could not be processed. Try another file or enter your information manually.")
        db.flush()

    return True

def process_next_document():
    job = claim_next_document()

    if job is None:
        return False

    document_id = job["document_id"]

    try:
        path = stored_file_path(job["storage_key"])
        text = extract_document_text(path, job["media_type"])

        # Read the available tags from the database.
        with database().transaction() as db:
            tags = []

            for tag in db.scalars(
                select(Tag).order_by(Tag.id.asc())
            ):
                tags.append(
                    {
                        "id": tag.id,
                        "label": tag.label,
                        "kind": tag.kind,
                    }
                )

        result = build_extraction_result(
            document_id, text, tags
        )

        saved = save_extraction_result(document_id, result, job["lease_token"])

        if not saved:
            current_app.logger.info("Document %s claim expired; discarded stale result.", document_id)

    except Exception as error:
        save_extraction_failure(document_id, job["lease_token"])

        current_app.logger.error(
            "Document %s extraction failed (%s).",
            document_id,
            type(error).__name__,
        )

    return True
