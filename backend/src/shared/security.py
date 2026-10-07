"""Session lookup, role checks and CSRF validation shared by API features."""

from hashlib import sha256
from hmac import compare_digest

from flask import current_app, request

from ..db.models import AuthSession, User, utcnow
from .validation import ApiError

COOKIE = "h18_session"


def digest(value):
    return sha256(value.encode("utf-8")).hexdigest()


def current_session(db):
    token = request.cookies.get(COOKIE, "")
    if not token or len(token) > 128 or not token.isascii():
        return None, None
    session = db.get(AuthSession, digest(token))
    if session is None or session.revoked_at is not None or session.expires_at <= utcnow():
        return None, None
    user = db.get(User, session.user_id) if session.user_id else None
    if session.user_id and (user is None or not user.active):
        return None, None
    return session, user


def require_user(db, role=None):
    session, user = current_session(db)
    if user is None:
        raise ApiError(401, "UNAUTHENTICATED", "Sign in to continue.")
    if role and user.role != role:
        raise ApiError(403, "FORBIDDEN", "Your account cannot perform this operation.")
    return session, user


def require_csrf(session):
    supplied = request.headers.get("X-CSRF-Token", "")
    if (session is None or request.headers.get("Origin") not in current_app.config["ALLOWED_ORIGINS"]
            or not compare_digest(supplied.encode("utf-8"), session.csrf_token.encode("utf-8"))):
        raise ApiError(403, "CSRF_INVALID", "Refresh the page and try again.")
