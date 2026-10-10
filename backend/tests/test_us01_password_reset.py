"""Password policy, both reset methods, verification grants and atomic revocation."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import pytest
from sqlalchemy import event, func, select

from backend.src.app import create_app
from backend.src.db.models import (AuthSession, PasswordResetAttempt, PasswordResetCode,
                                   RegistrationCode, User, utcnow)
from backend.src.features.auth.mail import EmailDeliveryError, send_password_reset_code
from backend.src.features.auth.routes import provision_user
from backend.src.shared.security import COOKIE, digest
from backend.src.shared.validation import ApiError, validator
from conftest import PASSWORD, headers, sign_in

RESET = "/api/v1/auth/login/reset"
EMAIL = "talent@example.test"
NEXT_PASSWORD = "New-password-456!"


@pytest.fixture
def reset(app, client, monkeypatch):
    outbox = []
    monkeypatch.setattr("backend.src.features.auth.reset.secrets.randbelow", lambda _: 7)
    app.extensions["password_reset_mailer"] = lambda email, code: outbox.append((email, code))
    csrf = client.get("/api/v1/auth/session").get_json()["csrfToken"]
    return client, csrf, outbox


def checked(response, status, schema="Error"):
    assert response.status_code == status, response.get_json()
    assert response.headers["Cache-Control"] == "no-store"
    validator(schema).validate(response.get_json())
    return response.get_json()


def post(reset, suffix="", **data):
    client, csrf, _ = reset
    return client.post(RESET + suffix, json=data, headers=headers(csrf))


def reset_body(**changes):
    return {"method": "PASSWORD", "identifier": EMAIL, "currentPassword": PASSWORD,
            "newPassword": NEXT_PASSWORD, "confirmPassword": NEXT_PASSWORD, **changes}


def email_body(**changes):
    return {"method": "EMAIL_CODE", "email": EMAIL, "newPassword": NEXT_PASSWORD,
            "confirmPassword": NEXT_PASSWORD, **changes}


def verify(reset, email=EMAIL, code="000007"):
    return post(reset, "/verify", email=email, code=code)


def issue(reset, email=EMAIL):
    return post(reset, "/code", email=email)


def authorize(reset):
    checked(issue(reset), 202, "PasswordResetCodeResponse")
    checked(verify(reset), 200, "PasswordResetVerifyResponse")


def allow_resend(app):
    with app.extensions["database"].transaction(write=True) as db:
        for attempt in db.scalars(select(PasswordResetAttempt)):
            attempt.attempted_at = utcnow() - timedelta(seconds=61)


@pytest.mark.parametrize("email", [EMAIL, "team@example.test"])
@pytest.mark.parametrize("use_id", [False, True])
def test_current_password_reset_both_roles_and_login_aliases(app, reset, email, use_id):
    signed = app.test_client()
    sign_in(signed, email)
    signed_cookie = signed.get_cookie(COOKIE).value
    with app.extensions["database"].transaction() as db:
        user = db.scalar(select(User).where(User.email == email))
        user_id = user.id
    identifier = user_id if use_id else email.upper()
    old_cookie = reset[0].get_cookie(COOKIE).value
    response = post(reset, **reset_body(identifier=identifier))
    session = checked(response, 200, "Session")
    assert session["user"] is None and session["csrfToken"] != reset[1]
    assert reset[0].get_cookie(COOKIE).value != old_cookie
    assert NEXT_PASSWORD not in response.get_data(as_text=True)
    with app.extensions["database"].transaction() as db:
        assert db.get(AuthSession, digest(signed_cookie)).revoked_at is not None
        assert db.get(AuthSession, digest(old_cookie)).revoked_at is not None
        assert app.extensions["password_hasher"].verify(db.get(User, user_id).password_hash, NEXT_PASSWORD)
    checked(signed.get("/api/v1/me/profile"), 401)
    client = reset[0]
    checked(client.post("/api/v1/auth/login", json={"identifier": identifier, "password": PASSWORD},
                        headers=headers(session["csrfToken"])), 401)
    logged = checked(client.post("/api/v1/auth/login", json={"identifier": identifier, "password": NEXT_PASSWORD},
                                 headers=headers(session["csrfToken"])), 200, "Session")
    assert logged["user"]["id"] == user_id


@pytest.mark.parametrize("password", ["abcdefgh1", "ABCDEFGH1", "Abcdefgh", "Abcd123", "Aa1" + "x" * 198])
def test_password_policy_applies_to_registration_reset_and_provisioning(app, reset, password):
    assert not validator("NewPassword").is_valid(password)
    checked(post(reset, **reset_body(newPassword=password, confirmPassword=password)), 422)
    registration = {"email": "new@example.test", "code": "000007", "password": password,
                    "displayName": "New", "role": "TALENT"}
    checked(reset[0].post("/api/v1/auth/register", json=registration, headers=headers(reset[1])), 422)
    with app.app_context(), pytest.raises(ApiError):
        provision_user("new@example.test", password, "New", "TALENT")


def test_minimum_password_length_and_legacy_password_remain_usable(app, reset):
    with app.extensions["database"].transaction(write=True) as db:
        user = db.scalar(select(User).where(User.email == EMAIL))
        user.password_hash = app.extensions["password_hasher"].hash("legacy")
    other = app.test_client()
    sign_in(other, EMAIL, "legacy")
    checked(post(reset, **reset_body(currentPassword="legacy", newPassword="Abcdefg1",
                                     confirmPassword="Abcdefg1")), 200, "Session")


@pytest.mark.parametrize("changes", [{"currentPassword": "wrong"}, {"identifier": "unknown@example.test"}])
def test_wrong_current_credentials_cannot_reset(reset, changes):
    checked(post(reset, **reset_body(**changes)), 401)


@pytest.mark.parametrize("method", ["PASSWORD", "EMAIL_CODE"])
@pytest.mark.parametrize("changes", [{"confirmPassword": "Different123!"},
                                     {"newPassword": PASSWORD, "confirmPassword": PASSWORD}])
def test_confirmation_and_reusing_current_password_are_rejected(app, reset, method, changes):
    if method == "EMAIL_CODE": authorize(reset)
    data = reset_body(**changes) if method == "PASSWORD" else email_body(**changes)
    result = checked(post(reset, **data), 422)
    assert result["error"]["code"] == "VALIDATION_ERROR"
    with app.extensions["database"].transaction() as db:
        user = db.scalar(select(User).where(User.email == EMAIL))
        assert app.extensions["password_hasher"].verify(user.password_hash, PASSWORD)
        if method == "EMAIL_CODE": assert db.get(PasswordResetCode, EMAIL).verified_at is not None


def test_email_verification_is_required_and_grant_survives_restart(app, reset):
    checked(post(reset, **email_body()), 422)
    checked(issue(reset, EMAIL.upper()), 202, "PasswordResetCodeResponse")
    assert reset[2] == [(EMAIL, "000007")]
    checked(post(reset, **email_body()), 422)
    with app.extensions["database"].transaction() as db:
        record = db.get(PasswordResetCode, EMAIL)
        assert record.code_hash.startswith("$argon2id$")
        assert record.sent_at is not None and record.verified_at is None
    checked(verify(reset), 200, "PasswordResetVerifyResponse")
    checked(verify(reset), 422)
    restarted = create_app(dict(app.config))
    try:
        other = restarted.test_client()
        other.set_cookie(COOKIE, reset[0].get_cookie(COOKIE).value)
        result = checked(other.post(RESET, json=email_body(), headers=headers(reset[1])), 200, "Session")
        checked(other.post(RESET, json=email_body(), headers=headers(result["csrfToken"])), 422)
        with app.extensions["database"].transaction() as db:
            assert db.get(PasswordResetCode, EMAIL) is None
    finally:
        restarted.extensions["database"].engine.dispose()


def test_code_and_verified_grant_are_bound_to_requesting_session(app, reset):
    checked(issue(reset), 202, "PasswordResetCodeResponse")
    other = app.test_client()
    csrf = other.get("/api/v1/auth/session").get_json()["csrfToken"]
    checked(other.post(RESET + "/verify", json={"email": EMAIL, "code": "000007"}, headers=headers(csrf)), 422)
    checked(verify(reset, email="other@example.test"), 422)
    checked(verify(reset), 200, "PasswordResetVerifyResponse")
    checked(other.post(RESET, json=email_body(), headers=headers(csrf)), 422)
    checked(post(reset, **email_body()), 200, "Session")


@pytest.mark.parametrize("verified", [False, True])
def test_expired_code_or_verified_grant_cannot_reset(app, reset, verified):
    checked(issue(reset), 202, "PasswordResetCodeResponse")
    if verified: checked(verify(reset), 200, "PasswordResetVerifyResponse")
    with app.extensions["database"].transaction(write=True) as db:
        db.get(PasswordResetCode, EMAIL).expires_at = utcnow() - timedelta(seconds=1)
    checked(post(reset, **email_body()) if verified else verify(reset), 422)


def test_resend_invalidates_even_a_verified_grant(app, reset, monkeypatch):
    authorize(reset)
    checked(issue(reset), 429)
    allow_resend(app)
    monkeypatch.setattr("backend.src.features.auth.reset.secrets.randbelow", lambda _: 123456)
    checked(issue(reset), 202, "PasswordResetCodeResponse")
    checked(post(reset, **email_body()), 422)
    checked(verify(reset), 422)
    checked(verify(reset, code="123456"), 200, "PasswordResetVerifyResponse")
    checked(post(reset, **email_body()), 200, "Session")


def test_attempt_limit_is_durable_and_correct_fifth_attempt_succeeds(app, reset):
    checked(issue(reset), 202, "PasswordResetCodeResponse")
    for _ in range(4): checked(verify(reset, code="123456"), 422)
    checked(verify(reset), 200, "PasswordResetVerifyResponse")
    allow_resend(app)
    checked(issue(reset), 202, "PasswordResetCodeResponse")
    for _ in range(5): checked(verify(reset, code="123456"), 422)
    restarted = create_app(dict(app.config))
    try:
        other = restarted.test_client()
        other.set_cookie(COOKIE, reset[0].get_cookie(COOKIE).value)
        checked(other.post(RESET + "/verify", json={"email": EMAIL, "code": "000007"},
                           headers=headers(reset[1])), 429)
    finally:
        restarted.extensions["database"].engine.dispose()


@pytest.mark.parametrize("scope", ["email", "ip"])
def test_sending_limits_include_failed_attempts_and_survive_restart(app, reset, scope):
    app.config["RESET_EMAIL_LIMIT" if scope == "email" else "RESET_IP_LIMIT"] = 1
    checked(issue(reset), 202, "PasswordResetCodeResponse")
    allow_resend(app)
    restarted = create_app(dict(app.config))
    try:
        other = restarted.test_client()
        other.set_cookie(COOKIE, reset[0].get_cookie(COOKIE).value)
        checked(other.post(RESET + "/code", json={"email": EMAIL if scope == "email" else "other@example.test"},
                           headers=headers(reset[1])), 429)
    finally:
        restarted.extensions["database"].engine.dispose()


@pytest.mark.parametrize("inactive", [False, True])
def test_unknown_or_inactive_email_has_generic_response_without_sending(app, reset, inactive):
    email = EMAIL if inactive else "unknown@example.test"
    if inactive:
        with app.extensions["database"].transaction(write=True) as db:
            db.scalar(select(User).where(User.email == EMAIL)).active = False
    checked(issue(reset, email), 202, "PasswordResetCodeResponse")
    assert reset[2] == []
    checked(verify(reset, email=email), 422)
    if inactive: checked(post(reset, **reset_body()), 401)


def test_pending_or_failed_mail_cannot_authorize_reset(app, reset):
    def fail(email, code):
        checked(verify(reset), 422)
        raise EmailDeliveryError("Simulated SMTP refusal")
    app.extensions["password_reset_mailer"] = fail
    checked(issue(reset), 503)
    checked(verify(reset), 422)
    with app.extensions["database"].transaction() as db:
        assert db.get(PasswordResetCode, EMAIL) is None
        assert db.scalar(select(func.count()).select_from(PasswordResetAttempt)) == 1


@pytest.mark.parametrize("suffix,data", [("/code", {"email": EMAIL}),
    ("/verify", {"email": EMAIL, "code": "000007"}), ("", reset_body())])
@pytest.mark.parametrize("override", [{}, {"Origin": "https://other.test", "X-CSRF-Token": "good"},
                                     {"Origin": "http://127.0.0.1:5173", "X-CSRF-Token": "bad"}])
def test_all_reset_steps_require_csrf_and_origin(reset, suffix, data, override):
    headers_value = {key: reset[1] if value == "good" else value for key, value in override.items()}
    checked(reset[0].post(RESET + suffix, json=data, headers=headers_value), 403)


def test_signed_in_user_cannot_reset_a_different_account(app):
    client = app.test_client()
    csrf = sign_in(client)
    checked(client.post(RESET, json=reset_body(identifier="team@example.test"), headers=headers(csrf)), 403)
    checked(client.post(RESET + "/code", json={"email": "team@example.test"}, headers=headers(csrf)), 403)
    checked(client.post(RESET, json=reset_body(), headers=headers(csrf)), 200, "Session")


def test_password_reset_invalidates_outstanding_email_grants(app, reset):
    authorize(reset)
    other = app.test_client()
    csrf = other.get("/api/v1/auth/session").get_json()["csrfToken"]
    checked(other.post(RESET, json=reset_body(), headers=headers(csrf)), 200, "Session")
    checked(post(reset, **email_body()), 422)


def test_registration_code_cannot_be_used_for_password_reset(app, reset):
    with app.extensions["database"].transaction(write=True) as db:
        db.add(RegistrationCode(email=EMAIL, challenge_id="registration", session_hash=digest(reset[0].get_cookie(COOKIE).value),
                                code_hash=app.extensions["password_hasher"].hash("000007"),
                                expires_at=utcnow() + timedelta(minutes=10), sent_at=utcnow()))
    checked(verify(reset), 422)


def test_password_update_code_consumption_and_session_revocation_roll_back_together(app, reset):
    authorize(reset)
    signed = app.test_client()
    sign_in(signed)
    token = signed.get_cookie(COOKIE).value
    engine = app.extensions["database"].engine
    def fail(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO auth_sessions"):
            raise RuntimeError("Simulated session persistence failure")
    event.listen(engine, "before_cursor_execute", fail)
    try:
        checked(post(reset, **email_body()), 500)
    finally:
        event.remove(engine, "before_cursor_execute", fail)
    with app.extensions["database"].transaction() as db:
        assert db.get(PasswordResetCode, EMAIL).verified_at is not None
        assert db.get(AuthSession, digest(token)).revoked_at is None
        assert app.extensions["password_hasher"].verify(db.scalar(select(User).where(User.email == EMAIL)).password_hash, PASSWORD)
    checked(post(reset, **email_body()), 200, "Session")


def test_simultaneous_reset_grant_replay_succeeds_only_once(app, reset):
    authorize(reset)
    cookie = reset[0].get_cookie(COOKIE).value
    barrier = Barrier(2)
    def submit(_):
        client = app.test_client()
        client.set_cookie(COOKIE, cookie)
        barrier.wait(timeout=5)
        return client.post(RESET, json=email_body(), headers=headers(reset[1])).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(submit, range(2)))
    assert statuses.count(200) == 1 and all(status in {200, 403, 409, 422} for status in statuses)


def test_current_password_checks_share_login_rate_limit(app, reset):
    app.config["LOGIN_EMAIL_LIMIT"] = 1
    checked(post(reset, **reset_body(currentPassword="wrong")), 401)
    checked(reset[0].post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD},
                          headers=headers(reset[1])), 429)


def test_pruning_removes_expired_reset_records(app, reset):
    authorize(reset)
    with app.extensions["database"].transaction(write=True) as db:
        db.get(PasswordResetCode, EMAIL).expires_at = utcnow() - timedelta(seconds=1)
        for attempt in db.scalars(select(PasswordResetAttempt)):
            attempt.attempted_at = utcnow() - timedelta(hours=2)
    assert app.test_cli_runner().invoke(args=["prune-sessions"]).exit_code == 0
    with app.extensions["database"].transaction() as db:
        assert db.get(PasswordResetCode, EMAIL) is None
        assert db.scalar(select(func.count()).select_from(PasswordResetAttempt)) == 0


def test_password_reset_email_uses_smtp_and_separate_purpose(app, monkeypatch):
    messages = []
    class SMTP:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def starttls(self, **kwargs): pass
        def send_message(self, message):
            messages.append(message)
            return {}
    monkeypatch.setattr("backend.src.features.auth.mail.smtplib.SMTP", SMTP)
    app.config.update(SMTP_HOST="smtp.example.test", SMTP_FROM="noreply@example.test", SMTP_USERNAME="")
    with app.app_context(): send_password_reset_code(EMAIL, "000007")
    assert "password reset" in messages[0]["Subject"]
    assert "000007" in messages[0].get_content() and "10 minutes" in messages[0].get_content()
