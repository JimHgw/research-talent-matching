"""Real SQLite/API coverage for saves and consent-filtered opportunity shortlists."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from backend.src.app import create_app
from backend.src.db.collections import SavedOpportunity, ShortlistedTalent
from backend.src.db.models import Document, Opportunity, TalentProfile, User
from backend.src.features.auth.routes import provision_user
from backend.src.shared.validation import validator
from conftest import PASSWORD, headers, sign_in
from test_us04 import confirm_profile, make_opportunity, research_team
from test_us05 import share

SAVED = "/api/v1/me/saved-opportunities"


def checked(response, schema="CollectionState"):
    assert response.status_code == 200, response.get_json()
    assert response.headers["Cache-Control"] == "no-store"
    data = response.get_json()
    validator(schema).validate(data)
    return data


@pytest.fixture
def collection(signed, research_team):
    profile = confirm_profile(signed)
    share(signed, ["displayName", "skills"])
    opportunity = make_opportunity(research_team)
    shortlist = f"/api/v1/opportunities/{opportunity['id']}/shortlist"
    return signed, research_team, profile, opportunity, shortlist


def test_save_remove_deduplicate_owner_scope_and_restart(app, collection):
    (talent, csrf), _, _, opportunity, _ = collection
    url = f"{SAVED}/{opportunity['id']}"
    assert checked(talent.get(url)) == {"saved": False}
    for _ in range(2):
        assert checked(talent.put(url, headers=headers(csrf))) == {"saved": True}
    assert checked(talent.get(SAVED), "OpportunityPage")["items"] == [opportunity]
    other = app.test_client()
    other_csrf = sign_in(other, "other@example.test")
    assert checked(other.get(SAVED), "OpportunityPage")["total"] == 0
    assert checked(other.delete(url, headers=headers(other_csrf))) == {"saved": False}
    assert checked(talent.get(url))["saved"]
    assert talent.post("/api/v1/auth/logout", headers=headers(csrf)).status_code == 204
    restarted = create_app(dict(app.config))
    try:
        reader = restarted.test_client()
        token = sign_in(reader)
        assert checked(reader.get(url))["saved"]
        assert checked(reader.get(SAVED), "OpportunityPage")["total"] == 1
        with restarted.extensions["database"].transaction() as db:
            assert db.scalar(select(func.count()).select_from(SavedOpportunity)) == 1
        for _ in range(2):
            assert checked(reader.delete(url, headers=headers(token))) == {"saved": False}
        assert checked(reader.get(SAVED), "OpportunityPage")["total"] == 0
    finally:
        restarted.extensions["database"].engine.dispose()


@pytest.mark.parametrize("method", ["get", "put", "delete"])
def test_authentication_roles_and_csrf(app, collection, method):
    (talent, csrf), (team, team_csrf), profile, opportunity, shortlist = collection
    saved = f"{SAVED}/{opportunity['id']}"
    candidate = f"{shortlist}/{profile['talentId']}"
    for url in (saved, candidate):
        assert getattr(app.test_client(), method)(url).status_code == 401
    assert getattr(team, method)(saved, headers=headers(team_csrf)).status_code == 403
    assert getattr(talent, method)(candidate, headers=headers(csrf)).status_code == 403
    if method != "get":
        for client, url, token in ((talent, saved, csrf), (team, candidate, team_csrf)):
            assert getattr(client, method)(url).status_code == 403
            assert getattr(client, method)(url, headers={
                **headers(token), "Origin": "https://untrusted.test"}).status_code == 403
    assert team.get(SAVED).status_code == 403
    assert talent.get(shortlist).status_code == 403
    assert app.test_client().get(SAVED).status_code == 401
    assert app.test_client().get(shortlist).status_code == 401


@pytest.mark.parametrize("identifier,status", [("missing", 404), ("invalid!", 422)])
def test_invalid_and_missing_ids(collection, identifier, status):
    (talent, csrf), (team, token), profile, _, shortlist = collection
    for method in ("get", "put"):
        assert getattr(talent, method)(f"{SAVED}/{identifier}", headers=headers(csrf)).status_code == status
        assert getattr(team, method)(f"{shortlist}/{identifier}", headers=headers(token)).status_code == status
        url = f"/api/v1/opportunities/{identifier}/shortlist"
        assert team.get(url).status_code == status
        assert getattr(team, method)(f"{url}/{profile['talentId']}", headers=headers(token)).status_code == status


def test_drafts_and_cross_team_never_accessible(app, collection):
    (talent, csrf), team, profile, _, shortlist = collection
    draft = make_opportunity(team, publish=False)
    for method in ("get", "put"):
        assert getattr(talent, method)(f"{SAVED}/{draft['id']}", headers=headers(csrf)).status_code == 404
    with app.app_context():
        provision_user("team2@example.test", PASSWORD, "Second team", "RESEARCH_TEAM")
    other = app.test_client()
    token = sign_in(other, "team2@example.test")
    for client, csrf, url in ((other, token, shortlist),
                              (team[0], team[1], f"/api/v1/opportunities/{draft['id']}/shortlist")):
        assert client.get(url).status_code == 404
        for method in ("get", "put", "delete"):
            assert getattr(client, method)(f"{url}/{profile['talentId']}", headers=headers(csrf)).status_code == 404


def test_shortlist_remove_deduplicate_and_restart(app, collection):
    _, (team, csrf), profile, _, shortlist = collection
    url = f"{shortlist}/{profile['talentId']}"
    for _ in range(2):
        assert checked(team.put(url, headers=headers(csrf)))["saved"]
    assert checked(team.get(shortlist), "TalentMatchPage")["total"] == 1
    assert team.post("/api/v1/auth/logout", headers=headers(csrf)).status_code == 204
    restarted = create_app(dict(app.config))
    try:
        reader = restarted.test_client()
        token = sign_in(reader, "team@example.test")
        assert checked(reader.get(url))["saved"]
        assert checked(reader.get(shortlist), "TalentMatchPage")["total"] == 1
        with restarted.extensions["database"].transaction() as db:
            assert db.scalar(select(func.count()).select_from(ShortlistedTalent)) == 1
        for _ in range(2):
            assert checked(reader.delete(url, headers=headers(token))) == {"saved": False}
        assert checked(reader.get(shortlist), "TalentMatchPage")["total"] == 0
    finally:
        restarted.extensions["database"].engine.dispose()


def test_current_privacy_and_no_documents(app, collection):
    signed, (team, csrf), profile, opportunity, shortlist = collection
    url = f"{shortlist}/{profile['talentId']}"
    checked(team.put(url, headers=headers(csrf)))
    with app.extensions["database"].transaction(write=True) as db:
        db.add(Document(id="private_doc", talent_id=profile["talentId"], kind="CV",
                        file_name="secret.pdf", media_type="application/pdf", storage_key="secret_key",
                        status="READY", size_bytes=1))
    share(signed, ["displayName"])
    page = checked(team.get(shortlist), "TalentMatchPage")
    assert set(page["items"][0]["talent"]["fields"]) == {"displayName"}
    assert page["items"][0]["summary"]["unknownWeightPercent"] == 100
    assert page["items"][0]["summary"]["score"] == 0
    for secret in ("secret.pdf", "secret_key", "private_doc", "documentId", "origins", "email"):
        assert secret not in str(page)
    assert team.get("/api/v1/me/documents/private_doc/file").status_code == 403
    share(signed, [], discoverable=False)
    assert checked(team.get(shortlist), "TalentMatchPage") == {
        "items": [], "page": 1, "pageSize": 20, "total": 0}
    for method in ("get", "put"):
        assert getattr(team, method)(url, headers=headers(csrf)).status_code == 404
    # The ID-only relationship survives opt-out; a fresh opt-in reuses CURRENT visibility.
    share(signed, [])
    item = checked(team.get(shortlist), "TalentMatchPage")["items"][0]
    assert item["talent"]["fields"] == {}
    share(signed, [], discoverable=False)
    assert checked(team.delete(url, headers=headers(csrf))) == {"saved": False}
    share(signed, ["skills"])
    assert checked(team.get(shortlist), "TalentMatchPage")["total"] == 0


@pytest.mark.parametrize("state", ["unconfirmed", "inactive"])
def test_eligibility_changes_hide_existing_records(app, collection, state):
    signed, (team, csrf), profile, _, shortlist = collection
    url = f"{shortlist}/{profile['talentId']}"
    checked(team.put(url, headers=headers(csrf)))
    if state == "unconfirmed":
        content = deepcopy(profile["content"])
        content["displayName"] = "Changed profile"
        assert signed[0].put("/api/v1/me/profile", json={
            "expectedRevision": profile["revision"], "content": content},
            headers=headers(signed[1])).status_code == 200
    else:
        with app.extensions["database"].transaction(write=True) as db:
            owner_id = db.get(TalentProfile, profile["talentId"]).user_id
            db.get(User, owner_id).active = False
    assert checked(team.get(shortlist), "TalentMatchPage")["total"] == 0
    assert team.get(url).status_code == 404
    assert team.put(url, headers=headers(csrf)).status_code == 404


@pytest.mark.parametrize("query", ["page=0", "page=1&page=2", "pageSize=101"])
def test_pagination_validation(collection, query):
    (talent, _), (team, _), _, _, shortlist = collection
    assert talent.get(SAVED + "?" + query).status_code == 422
    assert team.get(shortlist + "?" + query).status_code == 422


def test_concurrent_duplicate_requests_and_constraints(app, collection):
    _, _, profile, opportunity, shortlist = collection
    for role, url, model in (("talent", f"{SAVED}/{opportunity['id']}", SavedOpportunity),
                             ("team", f"{shortlist}/{profile['talentId']}", ShortlistedTalent)):
        clients = [app.test_client(), app.test_client()]
        tokens = [sign_in(client, role + "@example.test") for client in clients]
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda pair: pair[0].put(url, headers=headers(pair[1])).status_code,
                                    zip(clients, tokens)))
        assert results == [200, 200]
        with app.extensions["database"].transaction() as db:
            assert db.scalar(select(func.count()).select_from(model)) == 1
    with pytest.raises(IntegrityError):
        with app.extensions["database"].transaction(write=True) as db:
            db.add(ShortlistedTalent(opportunity_id=opportunity["id"], talent_id=profile["talentId"]))
            db.flush()
    with pytest.raises(IntegrityError):
        with app.extensions["database"].transaction(write=True) as db:
            db.add(ShortlistedTalent(opportunity_id=opportunity["id"], talent_id="missing"))
            db.flush()
