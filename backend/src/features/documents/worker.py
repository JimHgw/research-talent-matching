"""Background processing for uploaded documents."""

from sqlalchemy import select

from ...db.database import database
from ...db.models import Document, DocumentExtraction, Tag, utcnow
from ...shared.validation import validator

from flask import current_app

from .storage import stored_file_path
from .text import extract_document_text
from .suggestions import build_extraction_result


def claim_next_document():
    with database().transaction(write=True) as db:
        document = db.scalar(
            select(Document)
            .where(Document.status == "QUEUED")
            .order_by(Document.created_at.asc(), Document.id.asc())
            .limit(1)
        )

        if document is None:
            return None

        document.status = "PROCESSING"
        document.updated_at = utcnow()
        db.flush()

        return {
            "document_id": document.id,
            "storage_key": document.storage_key,
            "media_type": document.media_type,
            "kind": document.kind,
        }

def save_extraction_result(document_id, result):
    validator("Extraction").validate(result)

    if result["documentId"] != document_id:
        raise ValueError("Extraction result does not match the document.")

    with database().transaction(write=True) as db:
        document = db.get(Document, document_id)

        if document is None or document.status != "PROCESSING":
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

def save_extraction_failure(document_id):
    with database().transaction(write=True) as db:
        document = db.get(Document, document_id)

        if document is None or document.status != "PROCESSING":
            return False

        document.status = "FAILED"
        document.error = {
            "code": "EXTRACTION_FAILED",
            "message": (
                "The document could not be processed. "
                "Try another file or enter your information manually."
            ),
            "fieldErrors": [],
        }
        document.updated_at = utcnow()
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

        saved = save_extraction_result(document_id, result)

        if not saved:
            raise RuntimeError(
                "Document state changed before saving."
            )

    except Exception as error:
        save_extraction_failure(document_id)

        current_app.logger.error(
            "Document %s extraction failed (%s).",
            document_id,
            type(error).__name__,
        )

    return True