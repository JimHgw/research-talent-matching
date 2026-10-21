"""US-01 supplement: email verification before self-service account creation."""

from datetime import timedelta
import secrets

from argon2.exceptions import InvalidHashError, VerificationError
from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import delete, func, select

from ...db.database import database
from ...db.models import RegistrationAttempt, RegistrationCode, User, utcnow
from ...shared.security import current_session, digest, require_csrf
from ...shared.validation import ApiError, body, invalid
from .accounts import create_account
from .mail import EmailDeliveryError
from .routes import new_session, session_response

registration = Blueprint("registration", __name__, url_prefix="/api/v1/auth")


def anonymous_session(db):
    session, user = current_session(db)
    require_csrf(session)
    if user is not None:
        raise ApiError(403, "FORBIDDEN", "Sign out before registering a new account.")
    return session


def available_email(db, email):
    if db.scalar(select(User.id).where(User.email == email)):
        raise ApiError(409, "EMAIL_ALREADY_REGISTERED", "This email already has an account. Sign in instead.")


def reserve_email(db, email):
    now = utcnow()
    cutoff = now - timedelta(seconds=current_app.config["REGISTER_WINDOW"])
    email_hash, ip_hash = digest(email), digest(request.remote_addr or "unknown")
    db.execute(delete(RegistrationAttempt).where(RegistrationAttempt.attempted_at < cutoff))
    latest = db.scalar(select(func.max(RegistrationAttempt.attempted_at))
                       .where(RegistrationAttempt.email_hash == email_hash))
    if latest and latest > now - timedelta(seconds=current_app.config["REGISTER_RESEND_INTERVAL"]):
        raise ApiError(429, "RATE_LIMITED", "Wait before requesting another registration code.")
    for column, value, limit in (
        (RegistrationAttempt.email_hash, email_hash, current_app.config["REGISTER_EMAIL_LIMIT"]),
        (RegistrationAttempt.ip_hash, ip_hash, current_app.config["REGISTER_IP_LIMIT"]),
    ):
        count = db.scalar(select(func.count()).select_from(RegistrationAttempt).where(column == value))
        if count >= limit:
            raise ApiError(429, "RATE_LIMITED", "Too many registration emails. Try again later.")
    db.add(RegistrationAttempt(email_hash=email_hash, ip_hash=ip_hash, attempted_at=now))


@registration.post("/register/code")
def registration_code():
    with database().transaction() as db:
        anonymous_session(db)
    data = body("RegistrationCodeRequest")
    email = data["email"].strip().casefold()
    code = f"{secrets.randbelow(1_000_000):06d}"
    encoded = current_app.extensions["password_hasher"].hash(code)
    challenge_id = secrets.token_hex(16)
    now = utcnow()
    expires = now + timedelta(seconds=current_app.config["REGISTER_CODE_TTL"])
    with database().transaction(write=True) as db:
        session = anonymous_session(db)
        available_email(db, email)
        reserve_email(db, email)
        # Only the latest request can be verified, in the browser session that requested it.
        db.execute(delete(RegistrationCode).where(RegistrationCode.email == email))
        db.add(RegistrationCode(email=email, challenge_id=challenge_id,
                                session_hash=session.token_hash, code_hash=encoded,
                                expires_at=expires, created_at=now))
    try:
        # SMTP must not hold the database write lock; undelivered codes stay unusable.
        current_app.extensions["registration_mailer"](email, code)
    except EmailDeliveryError:
        with database().transaction(write=True) as db:
            db.execute(delete(RegistrationCode).where(RegistrationCode.challenge_id == challenge_id))
        raise ApiError(503, "EMAIL_DELIVERY_FAILED", "We could not send the registration email. Try again later.") from None
    with database().transaction(write=True) as db:
        challenge = db.get(RegistrationCode, email)
        if challenge is None or challenge.challenge_id != challenge_id or challenge.expires_at <= utcnow():
            raise ApiError(409, "VERIFICATION_CODE_INVALID", "Request a new registration code.")
        challenge.sent_at = utcnow()
    return jsonify(expiresAt=expires.isoformat(timespec="microseconds") + "Z",
                   resendAfterSeconds=current_app.config["REGISTER_RESEND_INTERVAL"]), 202


def current_code(db, email, session):
    challenge = db.get(RegistrationCode, email)
    if (challenge is None or challenge.session_hash != session.token_hash
            or challenge.sent_at is None or challenge.expires_at <= utcnow()):
        raise ApiError(422, "VERIFICATION_CODE_INVALID", "The registration code is invalid or expired.")
    return challenge


@registration.post("/register")
def register():
    with database().transaction() as db:
        anonymous_session(db)
    data = body("RegistrationRequest")
    email = data["email"].strip().casefold()
    display_name = data["displayName"].strip()
    if not display_name:
        invalid("displayName", "Enter a display name.")
    with database().transaction(write=True) as db:
        session = anonymous_session(db)
        available_email(db, email)
        challenge = current_code(db, email, session)
        if challenge.attempts >= current_app.config["REGISTER_CODE_ATTEMPTS"]:
            raise ApiError(429, "RATE_LIMITED", "Too many code attempts. Request a new registration code.")
        # Commit this reservation even if verification fails; counters survive restarts.
        challenge.attempts += 1
        encoded, challenge_id = challenge.code_hash, challenge.challenge_id
    try:
        current_app.extensions["password_hasher"].verify(encoded, data["code"])
    except (VerificationError, InvalidHashError):
        raise ApiError(422, "VERIFICATION_CODE_INVALID", "The registration code is invalid or expired.") from None
    password_hash = current_app.extensions["password_hasher"].hash(data["password"])
    with database().transaction(write=True) as db:
        session = anonymous_session(db)
        available_email(db, email)
        challenge = current_code(db, email, session)
        if challenge.challenge_id != challenge_id:
            raise ApiError(422, "VERIFICATION_CODE_INVALID", "Use the most recently emailed registration code.")
        user = create_account(db, email, password_hash, display_name, data["role"])
        db.delete(challenge)
        session.revoked_at = utcnow()
        next_session, raw = new_session(db, user)
    return session_response(next_session, user, raw), 201
