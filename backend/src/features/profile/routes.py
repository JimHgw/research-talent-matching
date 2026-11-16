"""HTTP adapters for owner profiles and the shared tag catalogue."""

from flask import Blueprint, jsonify, request

from ...db.database import database
from ...shared.security import require_csrf, require_user
from ...shared.validation import body, invalid, validate
from . import repository
from .serialization import serialize_profile, serialize_tag_catalogue
from .service import confirm_profile, save_profile

profiles = Blueprint("profiles", __name__, url_prefix="/api/v1")


@profiles.get("/tags")
def tags_get():
    with database().transaction() as db:
        require_user(db)
        kind = request.args.get("kind")
        if kind is not None and kind not in ("SKILL", "INTEREST"):
            invalid("kind", "Choose SKILL or INTEREST.")
        items = serialize_tag_catalogue(repository.load_tag_catalogue(db, kind))
    return jsonify(items=items)


@profiles.get("/me/profile")
def profile_get():
    with database().transaction() as db:
        _, user = require_user(db, "TALENT")
        profile = repository.own_profile(db, user)
        result = serialize_profile(profile, repository.load_profile_details(db, profile))
    return jsonify(result)


@profiles.put("/me/profile")
def profile_put():
    with database().transaction(write=True) as db:
        session, user = require_user(db, "TALENT")
        require_csrf(session)
        data = body("ProfileWrite")
        result = save_profile(
            db, user,
            expected_revision=data["expectedRevision"],
            content=data["content"],
        )
    return jsonify(result)


@profiles.post("/me/profile/confirmation")
def profile_confirm():
    with database().transaction(write=True) as db:
        session, user = require_user(db, "TALENT")
        require_csrf(session)
        # Preserve the existing owner lookup before confirmation-body parsing.
        repository.own_profile(db, user)
        data = body("RevisionRequest")
        result = confirm_profile(db, user, expected_revision=data["expectedRevision"])
    return jsonify(result)


def seed_tags(items):
    """Compatibility entry point used by the CLI and existing data fixtures."""
    validate("TagList", {"items": items})
    if len({tag["id"] for tag in items}) != len(items):
        raise ValueError("Duplicate tag ID in seed file.")
    with database().transaction(write=True) as db:
        repository.seed_tag_rows(db, items)
