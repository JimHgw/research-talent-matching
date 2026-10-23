from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import json
from threading import Barrier

import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy.exc import IntegrityError, OperationalError

from backend.src.app import create_app
from backend.src.db.models import (AuthSession, Document, LoginAttempt, PrivacySettings, PrivacyVisibleField,
                                   ProfileOrigin, ProfileSkill, TalentProfile, User, utcnow)
from backend.src.features.auth.routes import provision_user
from backend.src.shared.paths import ROOT
from backend.src.shared.security import COOKIE, digest
from backend.src.shared.validation import validator
from conftest import PASSWORD, headers, sign_in


def checked(response, status, schema=None):
    assert response.status_code == status, response.get_json()
    assert response.headers["Cache-Control"] == "no-store"
    data = response.get_json() if status != 204 else None
    if schema:
        validator(schema).validate(data)
    if status >= 400:
        validator("Error").validate(data)
        assert data["requestId"] == response.headers["X-Request-Id"]
    return data


def sample():
    return json.loads((ROOT / "docs/api/examples/profile-write.json").read_text())["content"]


def save(client, csrf, content, revision=0):
    return client.put("/api/v1/me/profile", json={"expectedRevision": revision, "content": content},
                      headers=headers(csrf))


def test_session_bootstrap_rotation_logout_and_replay(app, client):
    anonymous = checked(client.get("/api/v1/auth/session"), 200, "Session")
    assert anonymous["user"] is None
    old_cookie = client.get_cookie(COOKIE).value
    assert checked(client.get("/api/v1/auth/session"), 200) == anonymous
    response = client.post("/api/v1/auth/login", json={"email": "TALENT@EXAMPLE.TEST", "password": PASSWORD},
                           headers=headers(anonymous["csrfToken"]))
    session = checked(response, 200, "Session")
    cookie = client.get_cookie(COOKIE).value
    assert cookie != old_cookie and session["csrfToken"] != anonymous["csrfToken"]
    assert "HttpOnly" in response.headers["Set-Cookie"] and "SameSite=Lax" in response.headers["Set-Cookie"]
    assert "Domain=" not in response.headers["Set-Cookie"]
    assert cookie not in response.get_data(as_text=True)
    replay = app.test_client()
    replay.set_cookie(COOKIE, old_cookie)
    checked(replay.get("/api/v1/me/profile"), 401)
    checked(client.post("/api/v1/auth/logout", headers=headers(session["csrfToken"])), 204)
    assert client.get_cookie(COOKIE) is None
    replay.set_cookie(COOKIE, cookie)
    checked(replay.get("/api/v1/me/profile"), 401)
    with app.extensions["database"].transaction() as db:
        assert db.get(AuthSession, digest(cookie)).revoked_at is not None
        user = db.scalar(select(User).where(User.email == "talent@example.test"))
        assert user.password_hash.startswith("$argon2id$") and PASSWORD not in user.password_hash


@pytest.mark.parametrize("path", ["/me/profile", "/tags"])
def test_private_reads_require_login(client, path):
    checked(client.get("/api/v1" + path), 401)
    client.get("/api/v1/auth/session")
    checked(client.get("/api/v1" + path), 401)


@pytest.mark.parametrize("override", [{}, {"Origin": "https://evil.example", "X-CSRF-Token": "good"},
                                     {"Origin": "http://127.0.0.1:5173", "X-CSRF-Token": "wrong"},
                                     {"X-CSRF-Token": "good"}])
def test_login_requires_origin_and_csrf(client, override):
    csrf = client.get("/api/v1/auth/session").get_json()["csrfToken"]
    supplied = {k: csrf if v == "good" else v for k, v in override.items()}
    result = checked(client.post("/api/v1/auth/login", json={"email": "talent@example.test", "password": PASSWORD},
                                 headers=supplied), 403)
    assert result["error"]["code"] == "CSRF_INVALID"


def test_wrong_and_unknown_credentials_are_indistinguishable(client):
    csrf = client.get("/api/v1/auth/session").get_json()["csrfToken"]
    errors = [checked(client.post("/api/v1/auth/login", json={"email": email, "password": "wrong"},
                                  headers=headers(csrf)), 401)["error"]
              for email in ("talent@example.test", "unknown@example.test")]
    assert errors[0] == errors[1]


def test_expired_or_disabled_session_becomes_anonymous(app, signed):
    client, _ = signed
    cookie = client.get_cookie(COOKIE).value
    with app.extensions["database"].transaction(write=True) as db:
        db.get(AuthSession, digest(cookie)).expires_at = utcnow() - timedelta(seconds=1)
    checked(client.get("/api/v1/me/profile"), 401)
    assert checked(client.get("/api/v1/auth/session"), 200)["user"] is None
    sign_in(client)
    with app.extensions["database"].transaction(write=True) as db:
        db.scalar(select(User).where(User.email == "talent@example.test")).active = False
    checked(client.get("/api/v1/me/profile"), 401)
    assert checked(client.get("/api/v1/auth/session"), 200)["user"] is None


def test_rate_limit_survives_app_restart_and_expires(app, client):
    app.config["LOGIN_EMAIL_LIMIT"] = 2
    csrf = client.get("/api/v1/auth/session").get_json()["csrfToken"]
    for _ in range(2):
        checked(client.post("/api/v1/auth/login", json={"email": "talent@example.test", "password": "bad"},
                            headers=headers(csrf)), 401)
    restarted = create_app(dict(app.config))
    other = restarted.test_client()
    other.set_cookie(COOKIE, client.get_cookie(COOKIE).value)
    checked(other.post("/api/v1/auth/login", json={"email": "talent@example.test", "password": PASSWORD},
                       headers=headers(csrf)), 429)
    with app.extensions["database"].transaction(write=True) as db:
        for attempt in db.scalars(select(LoginAttempt)):
            attempt.attempted_at = utcnow() - timedelta(seconds=901)
    checked(other.post("/api/v1/auth/login", json={"email": "talent@example.test", "password": PASSWORD},
                       headers=headers(csrf)), 200)
    restarted.extensions["database"].engine.dispose()


def test_team_has_tags_but_no_talent_access(app, client):
    csrf = sign_in(client, "team@example.test")
    checked(client.get("/api/v1/tags"), 200, "TagList")
    checked(client.get("/api/v1/me/profile"), 403)
    checked(save(client, csrf, sample()), 403)
    with app.extensions["database"].transaction() as db:
        team_id = db.scalar(select(User.id).where(User.role == "RESEARCH_TEAM"))
        assert db.scalar(select(TalentProfile).where(TalentProfile.user_id == team_id)) is None


def test_initial_profile_and_privacy_defaults(app, signed):
    client, _ = signed
    data = checked(client.get("/api/v1/me/profile"), 200, "Profile")
    assert data["revision"] == 0 and data["origins"] == []
    assert data["content"]["displayName"] == "" and data["content"]["disciplineGroup"] is None
    assert data["content"]["researchInterestText"] == ""
    assert data["content"]["resumeDescription"] == ""
    assert all(value == [] for key, value in data["content"].items()
               if key not in ("displayName", "disciplineGroup", "researchInterestText", "resumeDescription"))
    assert data["confirmation"] == {"status": "UNCONFIRMED", "confirmedAt": None, "confirmedRevision": None}
    with app.extensions["database"].transaction() as db:
        privacy = db.get(PrivacySettings, data["talentId"])
        assert privacy.revision == 0 and privacy.discoverable is False
        assert db.scalar(select(func.count()).select_from(PrivacyVisibleField)) == 0


def test_profile_save_persists_after_restart_and_is_owner_only(app, signed):
    client, csrf = signed
    data = checked(save(client, csrf, sample()), 200, "Profile")
    assert data["revision"] == 1 and data["content"] == sample()
    restarted = create_app(dict(app.config))
    new_client = restarted.test_client()
    sign_in(new_client)
    assert checked(new_client.get("/api/v1/me/profile"), 200) == data
    sign_in(new_client, "other@example.test")
    own = checked(new_client.get("/api/v1/me/profile"), 200)
    assert own["talentId"] != data["talentId"] and own["revision"] == 0
    checked(new_client.get(f'/api/v1/me/profile/{data["talentId"]}'), 404)
    restarted.extensions["database"].engine.dispose()


def test_noop_preserves_confirmation_and_change_resets_it(app, signed):
    client, csrf = signed
    saved = checked(save(client, csrf, sample()), 200)
    with app.extensions["database"].transaction(write=True) as db:
        profile = db.get(TalentProfile, saved["talentId"])
        profile.confirmation_status, profile.confirmed_revision, profile.confirmed_at = "CONFIRMED", 1, utcnow()
    confirmed = checked(client.get("/api/v1/me/profile"), 200)
    assert checked(save(client, csrf, sample(), 1), 200) == confirmed
    changed = sample()
    changed["displayName"] = "Changed"
    result = checked(save(client, csrf, changed, 1), 200)
    assert result["revision"] == 2 and result["confirmation"]["status"] == "UNCONFIRMED"
    assert result["confirmation"]["confirmedAt"] is None
    assert result["origins"] == saved["origins"]


def test_clear_sections_and_reorder_skills(signed):
    client, csrf = signed
    content = sample()
    content["skills"] = [{"id": tag, "title": tag, "evidenceText": ""}
                         for tag in ("skill_python", "skill_sql")]
    checked(save(client, csrf, content), 200)
    content["skills"].reverse()
    data = checked(save(client, csrf, content, 1), 200)
    assert data["content"]["skills"] == content["skills"]
    content["skills"] = []
    content["education"] = []
    data = checked(save(client, csrf, content, 2), 200)
    assert data["content"] == content and data["revision"] == 3


@pytest.mark.parametrize("field,value", [
    ("skills", [{"tagId": "interest_ml", "claim": "HAS", "evidenceText": ""}]),
    ("researchInterests", ["skill_sql"]), ("researchInterests", ["missing"]),
    ("researchInterests", ["interest_ml", "interest_ml"]),
    ("disciplineGroup", "ARTS"), ("displayName", "a" * 101), ("education", [{}]),
    ("displayName", "\ud800"),
])
def test_invalid_profiles_do_not_write(signed, field, value):
    client, csrf = signed
    content = sample()
    content[field] = value
    checked(save(client, csrf, content), 422)
    assert client.get("/api/v1/me/profile").get_json()["revision"] == 0


@pytest.mark.parametrize("length", [100, 101, 200])
def test_course_codes_up_to_200_characters_persist(signed, length):
    client, csrf = signed
    content = sample()
    content["courses"] = [{"id": "course_limits", "name": "Research methods",
                           "code": "C" * length, "description": ""}]
    saved = checked(save(client, csrf, content), 200, "Profile")
    assert saved["content"]["courses"][0]["code"] == "C" * length
    assert checked(client.get("/api/v1/me/profile"), 200, "Profile") == saved


def test_course_code_over_200_characters_preserves_saved_profile(signed):
    client, csrf = signed
    content = sample()
    content["courses"] = [{"id": "course_limits", "name": "Research methods",
                           "code": "C" * 200, "description": ""}]
    saved = checked(save(client, csrf, content), 200, "Profile")
    content["courses"][0]["code"] = "C" * 201
    error = checked(save(client, csrf, content, saved["revision"]), 422, "Error")["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert [field["field"] for field in error["fieldErrors"]] == ["content.courses[0].code"]
    assert checked(client.get("/api/v1/me/profile"), 200, "Profile") == saved


@pytest.mark.parametrize("path,value,expected_field", [
    (("education", 0, "institution"), 42, "content.education[0].institution"),
    (("researchInterests", 0), 42, "content.researchInterests[0]"),
    (("displayName",), 42, "content.displayName"),
])
def test_validation_errors_use_contract_field_paths(signed, path, value, expected_field):
    client, csrf = signed
    content = sample()
    parent = content
    for key in path[:-1]:
        parent = parent[key]
    parent[path[-1]] = value
    error = checked(save(client, csrf, content), 422)["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert [field["field"] for field in error["fieldErrors"]] == [expected_field]
    assert client.get("/api/v1/me/profile").get_json()["revision"] == 0


@pytest.mark.parametrize("method,path,allowed", [
    ("POST", "/tags", {"GET", "HEAD", "OPTIONS"}),
    ("GET", "/auth/login", {"POST", "OPTIONS"}),
])
def test_unsupported_methods_return_contract_errors_and_allow_header(client, method, path, allowed):
    response = client.open("/api/v1" + path, method=method)
    error = checked(response, 405)["error"]
    assert error["code"] == "BAD_REQUEST" and error["fieldErrors"] == []
    assert set(response.headers["Allow"].split(", ")) == allowed


def test_missing_extra_duplicate_and_unsafe_url_rejected(signed):
    client, csrf = signed
    missing = sample()
    del missing["education"]
    extra = sample() | {"talentId": "another_owner"}
    duplicate = sample()
    duplicate["skills"] *= 2
    bad_url = sample()
    bad_url["researchOutputs"] = [{"id": "output", "title": "X", "type": "OTHER",
                                   "url": "javascript:alert(1)", "description": ""}]
    for content in (missing, extra, duplicate, bad_url):
        checked(save(client, csrf, content), 422)


def test_bad_json_media_type_and_csrf_never_write(signed):
    client, csrf = signed
    for payload in ('{', '{"expectedRevision": NaN}', '{"expectedRevision":0,"expectedRevision":1}'):
        checked(client.put("/api/v1/me/profile", data=payload, content_type="application/json",
                           headers=headers(csrf)), 400)
    checked(client.put("/api/v1/me/profile", data="{}", content_type="text/plain", headers=headers(csrf)), 415)
    checked(save(client, "incorrect", sample()), 403)
    checked(client.post("/api/v1/auth/logout", headers=headers("incorrect")), 403)
    assert client.get("/api/v1/me/profile").get_json()["revision"] == 0


def test_tag_filter_and_invalid_kind(signed):
    client, _ = signed
    data = checked(client.get("/api/v1/tags?kind=SKILL"), 200, "TagList")
    assert data["items"] and all(tag["kind"] == "SKILL" for tag in data["items"])
    checked(client.get("/api/v1/tags?kind=unknown"), 422)


def test_two_concurrent_writers_cannot_overwrite_same_revision(app, signed):
    client, csrf = signed
    cookie = client.get_cookie(COOKIE).value
    barrier = Barrier(2)

    def worker(name):
        concurrent_client = app.test_client()
        concurrent_client.set_cookie(COOKIE, cookie)
        content = sample() | {"displayName": name}
        barrier.wait(timeout=5)
        response = save(concurrent_client, csrf, content)
        return response.status_code, response.get_json()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(worker, ["First", "Second"]))
    assert sorted(status for status, _ in results) == [200, 409]
    winner = next(data for status, data in results if status == 200)
    loser = next(data for status, data in results if status == 409)
    assert loser["error"]["currentRevision"] == 1
    assert client.get("/api/v1/me/profile").get_json() == winner


def test_failed_save_rolls_back_all_changes(app, signed):
    client, csrf = signed
    database = app.extensions["database"]

    def fail_insert(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO profile_skill_details"):
            raise RuntimeError("injected failure")

    event.listen(database.engine, "before_cursor_execute", fail_insert)
    try:
        checked(save(client, csrf, sample()), 500)
    finally:
        event.remove(database.engine, "before_cursor_execute", fail_insert)
    profile = client.get("/api/v1/me/profile").get_json()
    assert profile["revision"] == 0 and profile["origins"] == [] and profile["content"]["skills"] == []


def test_database_constraints_and_foreign_keys(app):
    database = app.extensions["database"]
    with database.engine.connect() as first, database.engine.connect() as second:
        check = "PRAGMA foreign_keys" if database.engine.dialect.name == "sqlite" else "SELECT @@foreign_key_checks"
        assert first.scalar(text(check)) == second.scalar(text(check)) == 1
    with pytest.raises(IntegrityError), database.transaction(write=True) as db:
        db.add(ProfileSkill(talent_id="missing", tag_id="skill_sql", claim="HAS", evidence_text="", position=0))
    # PyMySQL reports MySQL CHECK violations (3819) as OperationalError.
    check_error = OperationalError if database.engine.dialect.name == "mysql" else IntegrityError
    with pytest.raises(check_error) as rejected, database.transaction(write=True) as db:
        profile = db.scalar(select(TalentProfile))
        profile.confirmation_status = "CONFIRMED"
    if database.engine.dialect.name == "mysql":
        assert rejected.value.orig.args[0] == 3819
    with app.app_context(), pytest.raises(ValueError):
        provision_user("TALENT@example.test", PASSWORD, "Duplicate", "TALENT")


def test_orm_relationships_preserve_ownership_and_restrict_deletion(app, signed):
    client, csrf = signed
    saved = checked(save(client, csrf, sample()), 200, "Profile")
    database = app.extensions["database"]
    with database.transaction() as db:
        profile = db.get(TalentProfile, saved["talentId"])
        owner = profile.user
        owner_id = owner.id
        assert owner.email == "talent@example.test"
        assert db.get(PrivacySettings, profile.talent_id).profile is profile
        session = db.get(AuthSession, digest(client.get_cookie(COOKIE).value))
        assert session.user is owner
        from backend.src.db.models import ProfileSkillDetails
        skill = db.get(ProfileSkillDetails, profile.talent_id)
        assert skill.profile is profile and skill.skills == saved["content"]["skills"]
        origin = db.get(ProfileOrigin, (profile.talent_id, "education"))
        assert origin.profile is profile and origin.document is None
    with pytest.raises(IntegrityError), database.transaction(write=True) as db:
        db.delete(db.get(User, owner_id))
        db.flush()
    assert checked(client.get("/api/v1/me/profile"), 200, "Profile") == saved


def test_document_origins_preserved_until_section_changes(app, signed):
    client, csrf = signed
    saved = checked(save(client, csrf, sample()), 200)
    with app.extensions["database"].transaction(write=True) as db:
        db.add(Document(id="doc_test", talent_id=saved["talentId"], kind="CV", file_name="test.pdf",
                        media_type="application/pdf", storage_key="private/test", status="READY", size_bytes=1))
        db.flush()
        origin = db.get(ProfileOrigin, (saved["talentId"], "education"))
        origin.source_type, origin.document_id = "USER_REVIEWED_DOCUMENT", "doc_test"
    content = sample() | {"displayName": "New name"}
    saved = checked(save(client, csrf, content, 1), 200)
    assert next(row for row in saved["origins"] if row["field"] == "education")["documentId"] == "doc_test"
    content["education"] = []
    saved = checked(save(client, csrf, content, 2), 200)
    assert next(row for row in saved["origins"] if row["field"] == "education") == {
        "field": "education", "sourceType": "MANUAL", "documentId": None}


def test_cli_idempotent_seed_and_hidden_password_provisioning(app):
    runner = app.test_cli_runner()
    assert runner.invoke(args=["init-db"]).exit_code == 0
    assert runner.invoke(args=["seed-tags"]).exit_code == 0
    response = runner.invoke(args=["provision-user", "--email", "cli@example.test", "--display-name", "CLI",
                                   "--role", "TALENT"], input=f"{PASSWORD}\n{PASSWORD}\n")
    assert response.exit_code == 0 and PASSWORD not in response.output
    client = app.test_client()
    sign_in(client, "cli@example.test")
    checked(client.get("/api/v1/me/profile"), 200, "Profile")


def test_secure_cookie_configuration(app):
    app.config["COOKIE_SECURE"] = True
    response = app.test_client().get("/api/v1/auth/session")
    assert "Secure" in response.headers["Set-Cookie"]


def test_failed_login_commit_keeps_original_session(app, client):
    anonymous = client.get("/api/v1/auth/session").get_json()
    original_cookie = client.get_cookie(COOKIE).value
    database = app.extensions["database"]

    def fail_new_session(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO auth_sessions"):
            raise RuntimeError("injected failure")

    event.listen(database.engine, "before_cursor_execute", fail_new_session)
    try:
        response = client.post("/api/v1/auth/login", json={"email": "talent@example.test", "password": PASSWORD},
                               headers=headers(anonymous["csrfToken"]))
        checked(response, 500)
        assert "Set-Cookie" not in response.headers
    finally:
        event.remove(database.engine, "before_cursor_execute", fail_new_session)
    assert client.get_cookie(COOKIE).value == original_cookie
    assert client.get("/api/v1/auth/session").get_json() == anonymous
    with database.transaction() as db:
        assert db.get(AuthSession, digest(original_cookie)).revoked_at is None

def test_us15_profile_changes_and_logout_do_not_affect_another_session(app):
    first = app.test_client()
    second = app.test_client()

    first_csrf = sign_in(first)
    second_csrf = sign_in(second, "other@example.test")

    first_identity = checked(
        first.get("/api/v1/auth/session"), 200, "Session"
    )["user"]

    second_session = checked(
        second.get("/api/v1/auth/session"), 200, "Session"
    )

    second_before = checked(
        second.get("/api/v1/me/profile"), 200, "Profile"
    )

    second_cookie = second.get_cookie(COOKIE).value

    assert first_identity["id"] != second_session["user"]["id"]

    # Saving A's profile must not change B's identity or profile.
    first_content = sample()
    first_content["displayName"] = "US-15 first private profile"
    first_saved = checked(
        save(first, first_csrf, first_content), 200, "Profile"
    )

    assert checked(
        second.get("/api/v1/auth/session"), 200, "Session"
    ) == second_session

    assert checked(
        second.get("/api/v1/me/profile"), 200, "Profile"
    ) == second_before

    # Saving B's profile must not overwrite A's profile.
    second_content = sample()
    second_content["displayName"] = "US-15 second private profile"
    second_saved = checked(
        save(second, second_csrf, second_content), 200, "Profile"
    )

    assert first_saved["talentId"] != second_saved["talentId"]
    assert checked(
        first.get("/api/v1/me/profile"), 200, "Profile"
    ) == first_saved

    # Logging out A must revoke A's cookie while preserving B's session.
    old_cookie = first.get_cookie(COOKIE).value
    checked(
        first.post("/api/v1/auth/logout", headers=headers(first_csrf)),
        204,
    )

    replay = app.test_client()
    replay.set_cookie(COOKIE, old_cookie)
    checked(replay.get("/api/v1/me/profile"), 401)

    assert second.get_cookie(COOKIE).value == second_cookie
    assert checked(
        second.get("/api/v1/auth/session"), 200, "Session"
    ) == second_session
    assert checked(
        second.get("/api/v1/me/profile"), 200, "Profile"
    ) == second_saved

    # Switching A's browser to B must resolve B's identity and private data.
    sign_in(first, "other@example.test")
    assert checked(
        first.get("/api/v1/auth/session"), 200, "Session"
    )["user"] == second_session["user"]
    assert checked(
        first.get("/api/v1/me/profile"), 200, "Profile"
    ) == second_saved


@pytest.mark.parametrize(
    "email,role,forged_role,forbidden_path",
    [
        (
            "talent@example.test",
            "TALENT",
            "RESEARCH_TEAM",
            "/api/v1/opportunities?scope=mine&role=RESEARCH_TEAM",
        ),
        (
            "team@example.test",
            "RESEARCH_TEAM",
            "TALENT",
            "/api/v1/me/profile?role=TALENT",
        ),
    ],
)
def test_us15_client_role_cannot_override_stored_role(
    app, email, role, forged_role, forbidden_path
):
    client = app.test_client()
    anonymous = checked(
        client.get("/api/v1/auth/session"), 200, "Session"
    )

    # Login must reject an extra role field instead of granting that role.
    result = checked(
        client.post(
            "/api/v1/auth/login",
            json={
                "identifier": email,
                "password": PASSWORD,
                "role": forged_role,
            },
            headers=headers(anonymous["csrfToken"]),
        ),
        422,
    )
    assert result["error"]["code"] == "VALIDATION_ERROR"
    assert checked(
        client.get("/api/v1/auth/session"), 200, "Session"
    )["user"] is None

    # Query parameters and headers must not override the stored role.
    sign_in(client, email)
    identity = checked(
        client.get("/api/v1/auth/session"), 200, "Session"
    )["user"]
    assert identity["role"] == role

    result = checked(
        client.get(
            forbidden_path,
            headers={
                "X-Role": forged_role,
                "X-User-Id": "user_forged",
            },
        ),
        403,
    )
    assert result["error"]["code"] == "FORBIDDEN"
    assert checked(
        client.get("/api/v1/auth/session"), 200, "Session"
    )["user"] == identity