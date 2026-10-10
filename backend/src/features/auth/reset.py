"""US-01: password reset using existing credentials or verified email."""

from datetime import timedelta
import secrets

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import delete, func, select, update

from ...db.database import database
from ...db.models import AuthSession, PasswordResetAttempt, PasswordResetCode, User, utcnow
from ...shared.security import current_session, digest, require_csrf
from ...shared.validation import ApiError, body, invalid
from .mail import EmailDeliveryError
from .passwords import password_matches
from .routes import login_user, new_session, reserve_login_attempt, session_response

password_reset = Blueprint("password_reset", __name__, url_prefix="/api/v1/auth/login/reset")


def reset_session(db, user_id=None):
    session, signed_user = current_session(db)
    require_csrf(session)
    if user_id is not None and signed_user is not None and signed_user.id != user_id:
        raise ApiError(403, "FORBIDDEN", "Sign out before resetting another account's password.")
    return session


def reserve_email(db, email):
    now = utcnow()
    cutoff = now - timedelta(seconds=current_app.config["RESET_WINDOW"])
    email_hash, ip_hash = digest(email), digest(request.remote_addr or "unknown")
    db.execute(delete(PasswordResetAttempt).where(PasswordResetAttempt.attempted_at < cutoff))
    latest = db.scalar(select(func.max(PasswordResetAttempt.attempted_at))
                       .where(PasswordResetAttempt.email_hash == email_hash))
    if latest and latest > now - timedelta(seconds=current_app.config["RESET_RESEND_INTERVAL"]):
        raise ApiError(429, "RATE_LIMITED", "Wait before requesting another password reset code.")
    for column, value, limit in (
        (PasswordResetAttempt.email_hash, email_hash, current_app.config["RESET_EMAIL_LIMIT"]),
        (PasswordResetAttempt.ip_hash, ip_hash, current_app.config["RESET_IP_LIMIT"]),
    ):
        count = db.scalar(select(func.count()).select_from(PasswordResetAttempt).where(column == value))
        if count >= limit:
            raise ApiError(429, "RATE_LIMITED", "Too many password reset emails. Try again later.")
    db.add(PasswordResetAttempt(email_hash=email_hash, ip_hash=ip_hash, attempted_at=now))


def code_invalid():
    raise ApiError(422, "VERIFICATION_CODE_INVALID", "The password reset code is invalid or expired.")


def current_code(db, email, session, *, verified):
    challenge = db.get(PasswordResetCode, email)
    if (challenge is None or challenge.session_hash != session.token_hash
            or challenge.sent_at is None or challenge.expires_at <= utcnow()
            or (challenge.verified_at is not None) != verified):
        code_invalid()
    user = db.get(User, challenge.user_id)
    if user is None or not user.active or user.password_hash != challenge.password_hash:
        code_invalid()
    return challenge, user


@password_reset.post("/code")
def request_code():
    with database().transaction() as db:
        reset_session(db)
    data = body("PasswordResetCodeRequest")
    email = data["email"].casefold()
    code = f"{secrets.randbelow(1_000_000):06d}"
    challenge_id = secrets.token_hex(16)
    encoded = current_app.extensions["password_hasher"].hash(code)
    now = utcnow()
    expires = now + timedelta(seconds=current_app.config["RESET_CODE_TTL"])
    with database().transaction(write=True) as db:
        session = reset_session(db)
        user = db.scalar(select(User).where(User.email == email, User.active.is_(True)))
        if user is not None:
            reset_session(db, user.id)
        reserve_email(db, email)
        db.execute(delete(PasswordResetCode).where(PasswordResetCode.email == email))
        user_id = user.id if user else None
        if user is not None:
            db.add(PasswordResetCode(email=email, user_id=user.id, challenge_id=challenge_id,
                                     session_hash=session.token_hash, code_hash=encoded,
                                     password_hash=user.password_hash, created_at=now, expires_at=expires))
    result = dict(expiresAt=expires.isoformat(timespec="microseconds") + "Z",
                  resendAfterSeconds=current_app.config["RESET_RESEND_INTERVAL"])
    # Do not disclose whether an unknown/inactive account exists, or send to it.
    if user_id is None:
        return jsonify(result), 202
    try:
        current_app.extensions["password_reset_mailer"](email, code)
    except EmailDeliveryError:
        with database().transaction(write=True) as db:
            db.execute(delete(PasswordResetCode).where(PasswordResetCode.challenge_id == challenge_id))
        raise ApiError(503, "EMAIL_DELIVERY_FAILED", "We could not send the password reset email. Try again later.") from None
    with database().transaction(write=True) as db:
        challenge = db.get(PasswordResetCode, email)
        if challenge is None or challenge.challenge_id != challenge_id or challenge.expires_at <= utcnow():
            code_invalid()
        challenge.sent_at = utcnow()
    return jsonify(result), 202


@password_reset.post("/verify")
def verify_code():
    with database().transaction() as db:
        reset_session(db)
    data = body("PasswordResetVerifyRequest")
    email = data["email"].casefold()
    with database().transaction(write=True) as db:
        session = reset_session(db)
        challenge, user = current_code(db, email, session, verified=False)
        reset_session(db, user.id)
        if challenge.attempts >= current_app.config["RESET_CODE_ATTEMPTS"]:
            raise ApiError(429, "RATE_LIMITED", "Too many code attempts. Request a new password reset code.")
        challenge.attempts += 1
        encoded, challenge_id = challenge.code_hash, challenge.challenge_id
    if not password_matches(encoded, data["code"]):
        code_invalid()
    with database().transaction(write=True) as db:
        session = reset_session(db)
        challenge, user = current_code(db, email, session, verified=False)
        reset_session(db, user.id)
        if challenge.challenge_id != challenge_id:
            code_invalid()
        challenge.verified_at = utcnow()
        expires = challenge.expires_at
    return jsonify(verified=True, expiresAt=expires.isoformat(timespec="microseconds") + "Z")


@password_reset.post("")
def reset_password():
    with database().transaction() as db:
        reset_session(db)
    data = body("PasswordResetRequest")
    if data["newPassword"] != data["confirmPassword"]:
        invalid("confirmPassword", "The new passwords must match.")
    challenge_id = None
    if data["method"] == "PASSWORD":
        identifier = data["identifier"].strip()
        reserve_login_attempt(identifier)
        with database().transaction() as db:
            user = login_user(db, identifier)
            if user is not None and not user.active:
                user = None
            if user is not None:
                reset_session(db, user.id)
            user_id = user.id if user else None
            encoded = user.password_hash if user else current_app.extensions["dummy_hash"]
        if not password_matches(encoded, data["currentPassword"]):
            raise ApiError(401, "INVALID_CREDENTIALS", "The account or current password is incorrect.")
        if user_id is None:
            raise ApiError(401, "INVALID_CREDENTIALS", "The account or current password is incorrect.")
    else:
        email = data["email"].casefold()
        with database().transaction() as db:
            session = reset_session(db)
            challenge, user = current_code(db, email, session, verified=True)
            reset_session(db, user.id)
            user_id, encoded = user.id, user.password_hash
            challenge_id = challenge.challenge_id
    if password_matches(encoded, data["newPassword"]):
        invalid("newPassword", "The new password must be different from the current password.")
    next_hash = current_app.extensions["password_hasher"].hash(data["newPassword"])
    with database().transaction(write=True) as db:
        session = reset_session(db, user_id)
        user = db.get(User, user_id)
        if user is None or not user.active or user.password_hash != encoded:
            raise ApiError(409, "PASSWORD_RESET_INVALID", "The account credentials changed. Start again.")
        if challenge_id is not None:
            challenge, _ = current_code(db, email, session, verified=True)
            if challenge.challenge_id != challenge_id:
                code_invalid()
        user.password_hash = next_hash
        now = utcnow()
        db.execute(update(AuthSession).where(AuthSession.user_id == user_id,
                                            AuthSession.revoked_at.is_(None)).values(revoked_at=now))
        session.revoked_at = now
        db.execute(delete(PasswordResetCode).where(PasswordResetCode.user_id == user_id))
        next_session, raw = new_session(db)
    # Reauthentication is required with the new password, from a fresh anonymous session.
    return session_response(next_session, None, raw)
