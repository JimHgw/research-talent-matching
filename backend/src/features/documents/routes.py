"""US-09: owner-only document endpoints."""

from flask import Blueprint, jsonify
from sqlalchemy import func, select

from ...db.database import database
from ...db.models import Document, TalentProfile
from ...shared.pagination import pagination
from ...shared.security import require_user


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

        rows = db.scalars(
            query
            .order_by(Document.created_at.desc(), Document.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()

        result = {
            "items": [serialize_document(document) for document in rows],
            "page": page,
            "pageSize": page_size,
            "total": total,
        }
    return jsonify(result)

