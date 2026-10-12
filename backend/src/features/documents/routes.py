"""US-09: owner-only document endpoints."""

from flask import Blueprint, jsonify, send_file
from sqlalchemy import func, select
from uuid import uuid4

from ...db.database import database
from ...db.models import Document, DocumentExtraction, TalentProfile
from ...shared.pagination import pagination
from ...shared.security import require_csrf, require_user
from ...shared.validation import ApiError, invalid, validator

from ..profile.routes import own_profile
from .storage import save_upload, stored_file_path
from .uploads import read_upload, validate_file

documents = Blueprint("documents", __name__, url_prefix="/api/v1")

def serialize_document(document):
    return {
        "id": document.id,
        "kind": document.kind,
        "fileName": document.file_name,
        "mediaType": document.media_type,
        "sizeBytes": document.size_bytes,
        "status": document.status,
        "createdAt": document.created_at.isoformat(
            timespec="microseconds"
        ) + "Z",
        "updatedAt":  document.updated_at.isoformat(
            timespec="microseconds"
        ) + "Z",
        "error": document.error
    }

def own_document(db, user, document_id):
    # Validate the document ID against the API contract.
    if not validator("Id").is_valid(document_id):
        invalid(
            "documentId",
            "Use an ID of 1–64 letters, digits, underscores or hyphens.",
        )

    document = db.scalar(
        select(Document)
        .join(TalentProfile)
        .where(
            Document.id == document_id,
            TalentProfile.user_id == user.id,
        )
    )

    if document is None:
        raise ApiError(
            404,
            "NOT_FOUND",
            "Document not found.",
        )

    return document


@documents.get("/me/documents")
def documents_get():
    with database().transaction() as db:
        # Only signed-in talent accounts can access their documents.
        _, user = require_user(db, "TALENT")
        page, page_size = pagination()

        # Select documents belonging to the signed-in user.
        query = (
            select(Document)
            .join(TalentProfile)
            .where(TalentProfile.user_id == user.id)
        )

        # Count all owned documents before applying pagination.
        total = db.scalar(
            select(func.count()).select_from(query.subquery())
        )

        offset = (page - 1) * page_size

        if offset >= total:
            rows = []
        else:
            rows = db.scalars(
                query
                .order_by(Document.created_at.desc(), Document.id.asc())
                .offset(offset)
                .limit(page_size)
            ).all()

        result = {
            "items": [serialize_document(document) for document in rows],
            "page": page,
            "pageSize": page_size,
            "total": total,
        }
    return jsonify(result)


@documents.post("/me/documents")
def documents_post():
    # Check permissions before reading or saving the upload.
    with database().transaction() as db:
        session, _ = require_user(db, "TALENT")
        require_csrf(session)

    file_name, kind, content = read_upload()
    media_type = validate_file(file_name, content)
    storage_key, saved_path = save_upload(content)

    try:
        with database().transaction(write=True) as db:
            session, user = require_user(db, "TALENT")
            require_csrf(session)

            profile = own_profile(db, user)
            document = Document(
                id=f"doc_{uuid4().hex}",
                talent_id=profile.talent_id,
                kind=kind,
                file_name=file_name,
                media_type=media_type,
                storage_key=storage_key,
                size_bytes=len(content),
                status="QUEUED",
                error=None,
            )

            db.add(document)
            db.flush()

            result = serialize_document(document)

    except Exception:
        # Remove the saved file if the database operation fails.
        saved_path.unlink(missing_ok=True)
        raise

    return jsonify(result), 202

@documents.get("/me/documents/<document_id>")
def document_get(document_id):
    with database().transaction() as db:
        _, user = require_user(db, "TALENT")

        document = own_document(db, user, document_id)
        result = serialize_document(document)

    return jsonify(result)

@documents.get("/me/documents/<document_id>/file")
def document_file_get(document_id):
    with database().transaction() as db:
        _, user = require_user(db, "TALENT")

        document = own_document(db, user, document_id)

        path = stored_file_path(document.storage_key)
        media_type = document.media_type
        file_name = document.file_name

    return send_file(
        path,
        mimetype=media_type,
        as_attachment=True,
        download_name=file_name,
        conditional=False,
        etag=False,
    )

@documents.get("/me/documents/<document_id>/extraction")
def document_extraction_get(document_id):
    with database().transaction() as db:
        _, user = require_user(db, "TALENT")
        document = own_document(db, user, document_id)

        if document.status in ("QUEUED", "PROCESSING"):
            raise ApiError(
                409,
                "EXTRACTION_NOT_READY",
                "The document is still being processed.",
            )

        if document.status == "FAILED":
            raise ApiError(
                422,
                "EXTRACTION_FAILED",
                "The document could not be processed.",
            )

        extraction = db.get(DocumentExtraction, document_id)

        if extraction is None:
            raise ApiError(
                500,
                "INTERNAL_ERROR",
                "The extraction result is unavailable.",
            )

        result = extraction.result

    return jsonify(result)