"""Email registration, replay protection, SMTP delivery and ID/email login."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from email import policy
from email.parser import BytesParser
from socketserver import StreamRequestHandler, TCPServer
from threading import Barrier, Thread

import pytest
from sqlalchemy import event, func, select

from backend.src.app import create_app
from backend.src.db.models import (AuthSession, PrivacySettings, RegistrationAttempt,
                                   RegistrationCode, TalentProfile, User, utcnow)
from backend.src.features.auth.mail import EmailDeliveryError, send_registration_code
from backend.src.shared.security import COOKIE, digest
from backend.src.shared.validation import validator
from conftest import PASSWORD, headers

CODE_URL = "/api/v1/auth/register/code"
REGISTER_URL = "/api/v1/auth/register"
EMAIL = "register@example.test"


@pytest.fixture
def registration(app, client, monkeypatch):
    outbox = []
    monkeypatch.setattr("backend.src.features.auth.registration.secrets.randbelow", lambda _: 7)
    app.extensions["registration_mailer"] = lambda email, code: outbox.append((email, code))
    csrf = client.get("/api/v1/auth/session").get_json()["csrfToken"]
    return client, csrf, outbox


def checked(response, status, schema="Error"):
    assert response.status_code == status, response.get_json()
    assert response.headers["Cache-Control"] == "no-store"
    data = response.get_json()
    validator(schema).validate(data)
    return data


def send(registration, email=EMAIL):
    client, csrf, _ = registration
    return client.post(CODE_URL, json={"email": email}, headers=headers(csrf))


def payload(**overrides):
    return {"email": EMAIL, "code": "000007", "password": PASSWORD,
            "displayName": "New account", "role": "TALENT", **overrides}


def register(registration, **overrides):
    client, csrf, _ = registration
    return client.post(REGISTER_URL, json=payload(**overrides), headers=headers(csrf))


def allow_resend(app):
    with app.extensions["database"].transaction(write=True) as db:
        for attempt in db.scalars(select(RegistrationAttempt)):
            attempt.attempted_at = utcnow() - timedelta(seconds=61)


@pytest.mark.parametrize("role", ["TALENT", "RESEARCH_TEAM"])
def test_register_both_roles_atomic_defaults_and_email_id_login(app, registration, role):
    client, csrf, outbox = registration
    old_cookie = client.get_cookie(COOKIE).value
    sent = checked(send(registration, "REGISTER@EXAMPLE.TEST"), 202, "RegistrationCodeResponse")
    assert sent["resendAfterSeconds"] == 60 and outbox == [(EMAIL, "000007")]
    assert "code" not in sent
    with app.extensions["database"].transaction() as db:
        stored = db.get(RegistrationCode, EMAIL)
        assert stored.code_hash.startswith("$argon2id$") and "000007" not in stored.code_hash
        assert stored.sent_at is not None
        assert (stored.expires_at - stored.created_at).total_seconds() == 600
    response = register(registration, role=role, email="REGISTER@EXAMPLE.TEST")
    session = checked(response, 201, "Session")
    user_id = session["user"]["id"]
    assert user_id.startswith("user_") and len(user_id) == 37
    assert session["user"]["email"] == EMAIL and session["user"]["role"] == role
    assert csrf != session["csrfToken"] and old_cookie != client.get_cookie(COOKIE).value
    assert PASSWORD not in response.get_data(as_text=True) and "000007" not in response.get_data(as_text=True)
    with app.extensions["database"].transaction() as db:
        user = db.get(User, user_id)
        assert user.password_hash.startswith("$argon2id$")
        assert app.extensions["password_hasher"].verify(user.password_hash, PASSWORD)
        assert db.get(RegistrationCode, EMAIL) is None
        assert db.get(AuthSession, digest(old_cookie)).revoked_at is not None
        profile = db.scalar(select(TalentProfile).where(TalentProfile.user_id == user_id))
        if role == "TALENT":
            assert profile.revision == 0 and profile.confirmation_status == "UNCONFIRMED"
            assert not db.get(PrivacySettings, profile.talent_id).discoverable
        else:
            assert profile is None
    for identifier in (EMAIL.upper(), user_id):
        other = app.test_client()
        token = other.get("/api/v1/auth/session").get_json()["csrfToken"]
        logged = checked(other.post("/api/v1/auth/login", json={"identifier": identifier, "password": PASSWORD},
                                   headers=headers(token)), 200, "Session")
        assert logged["user"]["id"] == user_id


def test_code_is_bound_to_email_and_requesting_session(app, registration):
    checked(send(registration), 202, "RegistrationCodeResponse")
    checked(register(registration, email="different@example.test"), 422)
    other = app.test_client()
    csrf = other.get("/api/v1/auth/session").get_json()["csrfToken"]
    checked(other.post(REGISTER_URL, json=payload(), headers=headers(csrf)), 422)
    checked(register(registration), 201, "Session")


def test_wrong_attempts_commit_and_survive_restart(app, registration):
    client, csrf, _ = registration
    checked(send(registration), 202, "RegistrationCodeResponse")
    for _ in range(5):
        assert checked(register(registration, code="123456"), 422)["error"]["code"] == "VERIFICATION_CODE_INVALID"
    restarted = create_app(dict(app.config))
    try:
        other = restarted.test_client()
        other.set_cookie(COOKIE, client.get_cookie(COOKIE).value)
        checked(other.post(REGISTER_URL, json=payload(), headers=headers(csrf)), 429)
        with app.extensions["database"].transaction() as db:
            assert db.get(RegistrationCode, EMAIL).attempts == 5
            assert db.scalar(select(User).where(User.email == EMAIL)) is None
    finally:
        restarted.extensions["database"].engine.dispose()


def test_correct_fifth_code_attempt_succeeds(registration):
    checked(send(registration), 202, "RegistrationCodeResponse")
    for _ in range(4):
        checked(register(registration, code="123456"), 422)
    checked(register(registration), 201, "Session")


def test_expired_and_missing_code_cannot_create_account(app, registration):
    checked(register(registration), 422)
    checked(send(registration), 202, "RegistrationCodeResponse")
    with app.extensions["database"].transaction(write=True) as db:
        db.get(RegistrationCode, EMAIL).expires_at = utcnow() - timedelta(seconds=1)
    checked(register(registration), 422)


def test_resend_replaces_old_code_and_enforces_cooldown(app, registration, monkeypatch):
    checked(send(registration), 202, "RegistrationCodeResponse")
    checked(send(registration), 429)
    allow_resend(app)
    monkeypatch.setattr("backend.src.features.auth.registration.secrets.randbelow", lambda _: 123456)
    checked(send(registration), 202, "RegistrationCodeResponse")
    checked(register(registration), 422)
    checked(register(registration, code="123456"), 201, "Session")


@pytest.mark.parametrize("scope", ["email", "ip"])
def test_email_rate_limits_are_durable(app, registration, scope):
    app.config["REGISTER_EMAIL_LIMIT" if scope == "email" else "REGISTER_IP_LIMIT"] = 1
    checked(send(registration), 202, "RegistrationCodeResponse")
    allow_resend(app)
    restarted = create_app(dict(app.config))
    try:
        restarted.extensions["registration_mailer"] = lambda *_: pytest.fail("Rate-limited email was sent")
        client, csrf, _ = registration
        other = restarted.test_client()
        other.set_cookie(COOKIE, client.get_cookie(COOKIE).value)
        email = EMAIL if scope == "email" else "different@example.test"
        checked(other.post(CODE_URL, json={"email": email}, headers=headers(csrf)), 429)
    finally:
        restarted.extensions["database"].engine.dispose()


def test_failed_delivery_leaves_no_usable_code_or_account(app, registration):
    def fail(*_):
        raise EmailDeliveryError("SMTP credentials must not reach clients")
    app.extensions["registration_mailer"] = fail
    response = send(registration)
    assert checked(response, 503)["error"]["code"] == "EMAIL_DELIVERY_FAILED"
    assert "credentials" not in response.get_data(as_text=True)
    checked(register(registration), 422)
    with app.extensions["database"].transaction() as db:
        assert db.get(RegistrationCode, EMAIL) is None
        assert db.scalar(select(User).where(User.email == EMAIL)) is None
        assert db.scalar(select(func.count()).select_from(RegistrationAttempt)) == 1


def test_code_cannot_be_used_before_email_delivery_finishes(app, registration):
    def delivery(email, code):
        assert (email, code) == (EMAIL, "000007")
        checked(register(registration), 422)
    app.extensions["registration_mailer"] = delivery
    checked(send(registration), 202, "RegistrationCodeResponse")
    checked(register(registration), 201, "Session")


def test_duplicate_email_and_signed_in_registration_are_rejected(app, registration):
    checked(send(registration, "TALENT@EXAMPLE.TEST"), 409)
    checked(send(registration), 202, "RegistrationCodeResponse")
    checked(register(registration), 201, "Session")
    client, _, _ = registration
    token = client.get("/api/v1/auth/session").get_json()["csrfToken"]
    checked(client.post(CODE_URL, json={"email": "another@example.test"}, headers=headers(token)), 403)
    checked(client.post(REGISTER_URL, json=payload(), headers=headers(token)), 403)
    other = app.test_client()
    token = other.get("/api/v1/auth/session").get_json()["csrfToken"]
    checked(other.post(REGISTER_URL, json=payload(), headers=headers(token)), 409)


@pytest.mark.parametrize("url,data", [(CODE_URL, {"email": EMAIL}), (REGISTER_URL, payload())])
@pytest.mark.parametrize("override", [{}, {"Origin": "https://other.example", "X-CSRF-Token": "good"},
                                     {"Origin": "http://127.0.0.1:5173", "X-CSRF-Token": "bad"}])
def test_registration_requires_csrf_and_origin(registration, url, data, override):
    client, csrf, outbox = registration
    supplied = {key: csrf if value == "good" else value for key, value in override.items()}
    checked(client.post(url, json=data, headers=supplied), 403)
    assert outbox == []


@pytest.mark.parametrize("changes", [{"code": "12345"}, {"code": 123456}, {"code": "１２３４５６"},
                                    {"password": "short"}, {"displayName": "  "}, {"role": "ADMIN"},
                                    {"email": "a@b\r\nBcc:other@example.test"}, {"userId": "chosen-id"}])
def test_invalid_registration_payloads_do_not_send_or_write(registration, changes):
    checked(register(registration, **changes), 422)


def test_profile_failure_rolls_back_account_code_and_session(app, registration):
    checked(send(registration), 202, "RegistrationCodeResponse")
    client, _, _ = registration
    cookie = client.get_cookie(COOKIE).value
    def fail(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO privacy_settings"):
            raise RuntimeError("Simulated persistence failure")
    engine = app.extensions["database"].engine
    event.listen(engine, "before_cursor_execute", fail)
    try:
        checked(register(registration), 500)
    finally:
        event.remove(engine, "before_cursor_execute", fail)
    with app.extensions["database"].transaction() as db:
        assert db.scalar(select(User).where(User.email == EMAIL)) is None
        assert db.get(RegistrationCode, EMAIL) is not None
        assert db.get(AuthSession, digest(cookie)).revoked_at is None
    checked(register(registration), 201, "Session")


def test_simultaneous_code_replay_creates_only_one_account(app, registration):
    checked(send(registration), 202, "RegistrationCodeResponse")
    client, csrf, _ = registration
    cookie = client.get_cookie(COOKIE).value
    barrier = Barrier(2)
    def submit():
        other = app.test_client()
        other.set_cookie(COOKIE, cookie)
        barrier.wait(timeout=5)
        return other.post(REGISTER_URL, json=payload(), headers=headers(csrf)).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(lambda _: submit(), range(2)))
    assert statuses.count(201) == 1
    assert all(status in {201, 403, 409, 422} for status in statuses)
    with app.extensions["database"].transaction() as db:
        assert db.scalar(select(func.count()).select_from(User).where(User.email == EMAIL)) == 1


def test_login_aliases_share_the_same_rate_limit(app, client):
    app.config["LOGIN_EMAIL_LIMIT"] = 2
    with app.extensions["database"].transaction() as db:
        user_id = db.scalar(select(User.id).where(User.email == "talent@example.test"))
    csrf = client.get("/api/v1/auth/session").get_json()["csrfToken"]
    for value in ({"email": "talent@example.test"}, {"identifier": user_id}):
        checked(client.post("/api/v1/auth/login", json={**value, "password": "wrong"}, headers=headers(csrf)), 401)
    checked(client.post("/api/v1/auth/login", json={"identifier": user_id, "password": PASSWORD}, headers=headers(csrf)), 429)


@pytest.mark.parametrize("extra", [{}, {"email": "talent@example.test", "identifier": "user_test"}])
def test_login_requires_exactly_one_identifier(client, extra):
    csrf = client.get("/api/v1/auth/session").get_json()["csrfToken"]
    checked(client.post("/api/v1/auth/login", json={**extra, "password": PASSWORD}, headers=headers(csrf)), 422)


def test_pruning_removes_expired_registration_state(app, registration):
    checked(send(registration), 202, "RegistrationCodeResponse")
    with app.extensions["database"].transaction(write=True) as db:
        db.get(RegistrationCode, EMAIL).expires_at = utcnow() - timedelta(seconds=1)
        for attempt in db.scalars(select(RegistrationAttempt)):
            attempt.attempted_at = utcnow() - timedelta(hours=2)
    assert app.test_cli_runner().invoke(args=["prune-sessions"]).exit_code == 0
    with app.extensions["database"].transaction() as db:
        assert db.get(RegistrationCode, EMAIL) is None
        assert db.scalar(select(func.count()).select_from(RegistrationAttempt)) == 0


@pytest.mark.parametrize("security", ["starttls", "ssl", "plain"])
def test_smtp_delivery_protocol_and_six_digit_message(app, monkeypatch, security):
    events = []
    class SMTP:
        def __init__(self, host, port, **kwargs):
            events.append((host, port, "context" in kwargs))
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def starttls(self, **kwargs): events.append("starttls")
        def login(self, username, password): events.append((username, password))
        def send_message(self, message):
            assert message["To"] == EMAIL
            assert "000007" in message.get_content()
            assert "10 minutes" in message.get_content()
            events.append("sent")
            return {}
    monkeypatch.setattr("backend.src.features.auth.mail.smtplib.SMTP", SMTP)
    monkeypatch.setattr("backend.src.features.auth.mail.smtplib.SMTP_SSL", SMTP)
    app.config.update(SMTP_HOST="smtp.example.test", SMTP_FROM="Banana <noreply@example.test>",
                      SMTP_USERNAME="mailer", SMTP_PASSWORD="smtp-test", SMTP_SECURITY=security)
    with app.app_context(): send_registration_code(EMAIL, "000007")
    assert events[0] == ("smtp.example.test", 587, security == "ssl")
    assert ("starttls" in events) == (security == "starttls")
    assert events[-2:] == [("mailer", "smtp-test"), "sent"]


def test_unconfigured_smtp_fails_without_exposing_code(app, registration):
    app.extensions["registration_mailer"] = send_registration_code
    app.config.update(SMTP_HOST="", SMTP_FROM="")
    response = send(registration)
    checked(response, 503)
    assert "000007" not in response.get_data(as_text=True)


def test_registration_delivers_real_smtp_message_to_local_server(app, registration):
    messages = []

    class LocalSMTP(StreamRequestHandler):
        def handle(self):
            self.connection.settimeout(5)
            self.wfile.write(b"220 localhost test SMTP\r\n")
            while line := self.rfile.readline():
                command = line.split(b" ", 1)[0].strip().upper()
                if command == b"DATA":
                    self.wfile.write(b"354 End with a dot\r\n")
                    content = []
                    while (part := self.rfile.readline()) not in {b".\r\n", b""}:
                        content.append(part[1:] if part.startswith(b"..") else part)
                    messages.append(BytesParser(policy=policy.default).parsebytes(b"".join(content)))
                    self.wfile.write(b"250 Message accepted\r\n")
                elif command == b"QUIT":
                    self.wfile.write(b"221 Goodbye\r\n")
                    return
                else:
                    self.wfile.write(b"250 localhost\r\n")

    with TCPServer(("127.0.0.1", 0), LocalSMTP) as server:
        worker = Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            app.config.update(SMTP_HOST="127.0.0.1", SMTP_PORT=server.server_address[1],
                              SMTP_SECURITY="plain", SMTP_USERNAME="", SMTP_PASSWORD="",
                              SMTP_FROM="noreply@example.test")
            app.extensions["registration_mailer"] = send_registration_code
            checked(send(registration), 202, "RegistrationCodeResponse")
            assert len(messages) == 1
            assert messages[0]["To"] == EMAIL
            assert "000007" in messages[0].get_content()
            checked(register(registration), 201, "Session")
        finally:
            server.shutdown()
            worker.join(timeout=5)
