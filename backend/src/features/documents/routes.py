"""US-09: owner-only document endpoints."""

from flask import Blueprint, jsonify
from sqlalchemy import func, select
from uuid import uuid4

from ...db.database import database
from ...db.models import Document, TalentProfile
from ...shared.pagination import pagination
from ...shared.security import require_csrf, require_user

from ..profile.routes import own_profile
from .storage import save_upload
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

