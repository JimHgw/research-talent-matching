"""Consent required by team discovery, with an independent privacy revision."""

from flask import Blueprint, jsonify
from sqlalchemy import delete, select

from ...db.database import database, require_write_lock
from ...db.models import PrivacySettings, PrivacyVisibleField, TalentProfile, utcnow
from ...shared.security import require_csrf, require_user
from ...shared.validation import ApiError, body

privacy = Blueprint("privacy", __name__, url_prefix="/api/v1/me/privacy")


def own_settings(db, user):
    settings = db.scalar(
        select(PrivacySettings).join(TalentProfile)
        .where(TalentProfile.user_id == user.id)
    )
    if settings is None:
        raise ApiError(404, "NOT_FOUND", "Privacy settings not found.")
    return settings


def serialize(db, settings):
    return {
        "revision": settings.revision,
        "discoverable": settings.discoverable,
        "visibleFields": list(db.scalars(
            select(PrivacyVisibleField.field)
            .where(PrivacyVisibleField.talent_id == settings.talent_id)
            .order_by(PrivacyVisibleField.field)
        )),
        "updatedAt": settings.updated_at.isoformat(timespec="microseconds") + "Z",
    }


@privacy.get("")
def privacy_get():
    with database().transaction() as db:
        _, user = require_user(db, "TALENT")
        result = serialize(db, own_settings(db, user))
    return jsonify(result)


@privacy.put("")
def privacy_put():
    with database().transaction(write=True) as db:
        session, user = require_user(db, "TALENT")
        require_csrf(session)
        data = body("PrivacyWrite")
        settings = own_settings(db, user)
        require_write_lock(db)
        if data["expectedRevision"] != settings.revision:
            raise ApiError(409, "REVISION_CONFLICT",
                           "Your privacy settings changed. Reload the latest version.",
                           revision=settings.revision)
        current = serialize(db, settings)
        fields = sorted(data["visibleFields"])
        if (data["discoverable"] != settings.discoverable
                or fields != current["visibleFields"]):
            settings.discoverable = data["discoverable"]
            settings.revision += 1
            settings.updated_at = utcnow()
            db.execute(delete(PrivacyVisibleField)
                       .where(PrivacyVisibleField.talent_id == settings.talent_id))
            db.add_all(PrivacyVisibleField(talent_id=settings.talent_id, field=field)
                       for field in fields)
            db.flush()
        result = serialize(db, settings)
    return jsonify(result)
