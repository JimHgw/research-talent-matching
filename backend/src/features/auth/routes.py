"""US-01: email/ID login, administrative accounts and server-side sessions."""

from datetime import timedelta
import secrets

from argon2.exceptions import InvalidHashError, VerificationError
from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import delete, func, select

from ...db.database import database
from ...db.models import AuthSession, LoginAttempt, User, utcnow
from ...shared.security import COOKIE, current_session, digest, require_csrf, require_user
from ...shared.validation import ApiError, body, validate
from .accounts import create_account

auth = Blueprint("auth", __name__, url_prefix="/api/v1/auth")


def public_user(user):
    return {"id": user.id, "displayName": user.display_name, "email": user.email, "role": user.role}


def new_session(db, user=None):
    raw = secrets.token_urlsafe(32)
    seconds = current_app.config["SESSION_TTL" if user else "ANONYMOUS_TTL"]
    session = AuthSession(token_hash=digest(raw), user_id=user.id if user else None,
                          csrf_token=secrets.token_urlsafe(32), expires_at=utcnow() + timedelta(seconds=seconds))
    db.add(session)
    return session, raw


def session_response(session, user, raw=None):
    response = jsonify(user=public_user(user) if user else None, csrfToken=session.csrf_token)
    if raw:
        response.set_cookie(COOKIE, raw, httponly=True, samesite="Lax", path="/",
                            secure=current_app.config["COOKIE_SECURE"])
    return response


@auth.get("/session")
def session_get():
    # Reuse an existing anonymous session, including its CSRF token.
    with database().transaction(write=True) as db:
        session, user = current_session(db)
        raw = None
        if session is None:
            session, raw = new_session(db)
    return session_response(session, user, raw)


def login_user(db, identifier):
    if "@" in identifier:
        return db.scalar(select(User).where(User.email == identifier.casefold()))
    return db.get(User, identifier)


def reserve_login_attempt(identifier):
    """Count attempts durably across workers; expensive password work is outside the write lock."""
    now = utcnow()
    cutoff = now - timedelta(seconds=current_app.config["LOGIN_WINDOW"])
    with database().transaction(write=True) as db:
        session, _ = current_session(db)
        require_csrf(session)
        user = login_user(db, identifier)
        # Both aliases share the email counter, including pre-existing attempts.
        email_hash = digest(user.email if user else identifier.casefold())
        ip_hash = digest(request.remote_addr or "unknown")
        db.execute(delete(LoginAttempt).where(LoginAttempt.attempted_at < cutoff))
        for column, value, limit in (
            (LoginAttempt.email_hash, email_hash, current_app.config["LOGIN_EMAIL_LIMIT"]),
            (LoginAttempt.ip_hash, ip_hash, current_app.config["LOGIN_IP_LIMIT"]),
        ):
            count = db.scalar(select(func.count()).select_from(LoginAttempt).where(column == value))
            if count >= limit:
                raise ApiError(429, "RATE_LIMITED", "Too many sign-in attempts. Try again later.")
        db.add(LoginAttempt(email_hash=email_hash, ip_hash=ip_hash, attempted_at=now))


@auth.post("/login")
def login():
    with database().transaction() as db:
        session, _ = current_session(db)
        require_csrf(session)
    data = body("LoginRequest")
    identifier = data.get("identifier", data.get("email", "")).strip()
    reserve_login_attempt(identifier)
    with database().transaction() as db:
        user = login_user(db, identifier)
        encoded = user.password_hash if user else current_app.extensions["dummy_hash"]
        user_id = user.id if user else None
    try:
        current_app.extensions["password_hasher"].verify(encoded, data["password"])
        valid = True
    except (VerificationError, InvalidHashError):
        valid = False
    # Recheck session, credentials and active status after password verification.
    with database().transaction(write=True) as db:
        session, _ = current_session(db)
        require_csrf(session)
        user = db.get(User, user_id) if user_id else None
        if not valid or user is None or not user.active or user.password_hash != encoded:
            raise ApiError(401, "INVALID_CREDENTIALS", "The email or password is incorrect.")
        session.revoked_at = utcnow()
        next_session, raw = new_session(db, user)
    # Never send a replacement cookie before the transaction commits.
    return session_response(next_session, user, raw)


@auth.post("/logout")
def logout():
    with database().transaction(write=True) as db:
        session, _ = require_user(db)
        require_csrf(session)
        session.revoked_at = utcnow()
    response = current_app.response_class(status=204)
    response.delete_cookie(COOKIE, path="/", secure=current_app.config["COOKIE_SECURE"],
                           httponly=True, samesite="Lax")
    return response


def provision_user(email, password, display_name, role):
    """Administrative CLI helper, never a public registration endpoint."""
    email = email.strip().casefold()
    validate("LoginRequest", {"email": email, "password": password})
    user_id = "user_" + secrets.token_hex(16)
    validate("User", {"id": user_id, "displayName": display_name, "email": email, "role": role})
    encoded = current_app.extensions["password_hasher"].hash(password)
    with database().transaction(write=True) as db:
        if db.scalar(select(User.id).where(User.email == email)):
            raise ValueError("An account with this email already exists.")
        user = create_account(db, email, encoded, display_name, role)
    return user.id
