"""Sprint 3 BE-5: authorisation and team-visible data boundaries.

Every check uses the real Flask routes, SQLite/MySQL persistence and separate
test clients (independent cookie jars).
"""

from copy import deepcopy
from datetime import timedelta
from hashlib import sha256
from io import BytesIO
import json

import pytest
from pypdf import PdfWriter

from backend.src.db.models import (AuthSession, Document, ProfileComponentOrigin, ProfileOrigin,
                                   ProfileSkillDetails, TalentProfile, User, utcnow)
from backend.src.features.auth.routes import provision_user
from backend.src.features.matching import team_service
from backend.src.features.matching.team_repository import PERSONAL_TAG_KEYS, SKILL_KEYS
from backend.src.shared.security import COOKIE, digest
from conftest import PASSWORD, headers, sign_in
from test_us04 import (MATCHES, OPPORTUNITIES, PROFILE, RECOMMENDATIONS, assert_error, checked,
                       confirm_profile, example, make_opportunity, research_team)  # noqa: F401
from test_us05 import share

PRIVACY = "/api/v1/me/privacy"
DOCUMENTS = "/api/v1/me/documents"
SAVED = "/api/v1/me/saved-opportunities"

# Strings that must never reach a team response or a team scoring/model input.
RESUME = "PRIVATE_RESUME_SENTINEL"
HIDDEN = ("HIDDEN_INTEREST_SENTINEL", "HIDDEN_TAG_SENTINEL", "HIDDEN_EXPERIENCE_SENTINEL",
          "HIDDEN_ORG_SENTINEL", "HIDDEN_OUTPUT_SENTINEL", "HIDDEN_COURSE_SENTINEL", RESUME)
PRIVATE_KEYS = {"origins", "documentId", "sourceType", "confirmedRevision", "fileName",
                "storageKey", "downloadUrl", "email", "resumeDescription", "revision"}

REQUIREMENTS = [
    {"id": "req_skill", "label": "Python", "kind": "SKILL", "importance": "REQUIRED",
     "tagIds": [], "skillTitles": ["Python"]},
    {"id": "req_interest", "label": "Machine learning", "kind": "INTEREST",
     "importance": "REQUIRED", "tagIds": ["interest_ml"]},
    {"id": "req_education", "label": "Masters", "kind": "EDUCATION", "importance": "PREFERRED",
     "tagIds": [], "criteria": {"qualification": "Master of IT"}},
    {"id": "req_experience", "label": "Graph research", "kind": "RESEARCH_EXPERIENCE",
     "importance": "PREFERRED", "tagIds": [], "criteria": {"title": "Graph neural networks"}},
]
VISIBLE = ["displayName", "skills", "education"]


class RecordingEncoder:
    """Deterministic, non-degenerate vectors; records every model input batch."""

    def __init__(self):
        self.calls = []

    def encode(self, texts):
        self.calls.append(list(texts))
        vectors = []
        for text in texts:
            seed = sha256(text.encode("utf-8")).digest() * 12
            vectors.append([(byte - 127.5) / 127.5 for byte in seed[:384]])
        return vectors


@pytest.fixture
def encoder(app):
    app.config["SEMANTIC_MATCHING_ENABLED"] = True
    recording = RecordingEncoder()
    app.extensions["semantic_matching"]._encoder = recording
    return recording


def client_for(app, email):
    client = app.test_client()
    return client, sign_in(client, email)


def content_for(skill_title, *, hidden=False):
    content = deepcopy(example("profile-write.json")["content"])
    content["skills"] = [{"id": "skill_main", "title": skill_title, "evidenceText": "Visible evidence."}]
    content["researchInterests"] = []
    content["researchExperience"] = []
    content["researchOutputs"] = []
    content["courses"] = []
    content["researchInterestText"] = ""
    content["customInterestTags"] = []
    content["resumeDescription"] = ""
    if hidden:
        content["researchInterests"] = ["interest_ml"]
        content["researchInterestText"] = "HIDDEN_INTEREST_SENTINEL machine learning"
        content["customInterestTags"] = [{"label": "HIDDEN_TAG_SENTINEL"}]
        content["researchExperience"] = [{"id": "exp_hidden", "title": "Graph neural networks",
                                          "organisation": "HIDDEN_ORG_SENTINEL",
                                          "description": "HIDDEN_EXPERIENCE_SENTINEL"}]
        content["researchOutputs"] = [{"id": "out_hidden", "title": "HIDDEN_OUTPUT_SENTINEL",
                                       "type": "PUBLICATION", "url": None, "description": ""}]
        content["courses"] = [{"id": "course_hidden", "name": "HIDDEN_COURSE_SENTINEL",
                               "code": None, "description": ""}]
        content["resumeDescription"] = f"{RESUME} Python machine learning graph neural networks"
    return content


def assert_no_private(value):
    text = json.dumps(value, ensure_ascii=False)
    for secret in HIDDEN:
        assert secret not in text

    def walk(item):
        if isinstance(item, dict):
            assert not PRIVATE_KEYS & set(item), PRIVATE_KEYS & set(item)
            for child in item.values():
                walk(child)
        elif isinstance(item, list):
            for child in item:
                walk(child)
    walk(value)


def without_time(value):
    value = deepcopy(value)
    value.pop("evaluatedAt", None)
    return value


@pytest.fixture
def world(app, research_team):
    """Two discoverable talent, one owning team and one unrelated team."""
    talents = []
    for email, skill in (("talent@example.test", "Python"), ("other@example.test", "SQL")):
        signed = client_for(app, email)
        profile = confirm_profile(signed, content_for(skill))
        share(signed, VISIBLE)
        talents.append((signed, profile))
    opportunity = make_opportunity(research_team, REQUIREMENTS)
    with app.app_context():
        provision_user("team2@example.test", PASSWORD, "Other team", "RESEARCH_TEAM")
    other_team = client_for(app, "team2@example.test")
    base = f"{OPPORTUNITIES}/{opportunity['id']}"
    return {"talents": talents, "team": research_team, "other_team": other_team,
            "opportunity": opportunity, "matches": f"{base}/talent-matches",
            "shortlist": f"{base}/shortlist"}


def team_view(team, world):
    """Every team read that can expose filtering, scores, ranks or evidence."""
    url, ids = world["matches"], [profile["talentId"] for _, profile in world["talents"]]
    view = {"list": checked(team.get(url), "TalentMatchPage")}
    for name, query in (("q-hidden", "q=graph"), ("q-sentinel", "q=HIDDEN_INTEREST_SENTINEL"),
                        ("q-resume", "q=machine"), ("interest", "interestTagId=interest_ml"),
                        ("skill", "skill=python"), ("paged", "page=2&pageSize=1")):
        view[name] = checked(team.get(f"{url}?{query}"), "TalentMatchPage")
    for talent_id in ids:
        view[talent_id] = without_time(checked(team.get(f"{url}/{talent_id}"), "TeamMatch"))
    view["shortlist"] = checked(team.get(world["shortlist"]), "TalentMatchPage")
    return view


# --------------------------------------------------------------------------
# 1. Access matrix
# --------------------------------------------------------------------------

def upload(app, signed, tmp_path):
    app.config["DOCUMENT_STORAGE_DIR"] = str(tmp_path / "documents")
    buffer = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.write(buffer)
    client, csrf = signed
    response = client.post(DOCUMENTS, data={"kind": "CV", "file": (BytesIO(buffer.getvalue()), "cv.pdf")},
                           content_type="multipart/form-data", headers=headers(csrf))
    assert response.status_code == 202, response.get_json()
    return response.get_json()["id"]


ACTORS = ("anonymous", "invalid", "expired", "owner", "other_talent", "owner_team", "other_team")
# endpoint -> expected status per actor, in ACTORS order.
MATRIX = {
    "GET /me/profile":                          (401, 401, 401, 200, 200, 403, 403),
    "GET /me/privacy":                          (401, 401, 401, 200, 200, 403, 403),
    "GET /me/documents":                        (401, 401, 401, 200, 200, 403, 403),
    "GET /me/documents/{doc}":                  (401, 401, 401, 200, 404, 403, 403),
    "GET /me/documents/{doc}/file":             (401, 401, 401, 200, 404, 403, 403),
    "GET /me/documents/{doc}/extraction":       (401, 401, 401, 409, 404, 403, 403),
    "GET /me/recommendations":                  (401, 401, 401, 200, 409, 403, 403),
    "GET /me/opportunity-matches/{opp}":        (401, 401, 401, 200, 409, 403, 403),
    "GET /me/saved-opportunities":              (401, 401, 401, 200, 200, 403, 403),
    "GET /opportunities/{draft}":               (401, 401, 401, 404, 404, 200, 404),
    "GET /opportunities/{opp}/talent-matches":  (401, 401, 401, 403, 403, 200, 404),
    "GET /opportunities/{opp}/talent-matches/{talent}": (401, 401, 401, 403, 403, 200, 404),
    "GET /opportunities/{opp}/shortlist":       (401, 401, 401, 403, 403, 200, 404),
    "GET /opportunities/{opp}/shortlist/{talent}": (401, 401, 401, 403, 403, 200, 404),
}


def test_access_matrix(app, tmp_path, research_team, record_testsuite_property):
    owner = client_for(app, "talent@example.test")
    profile = confirm_profile(owner)
    share(owner, ["skills"])
    other_talent = client_for(app, "other@example.test")  # Unconfirmed profile.
    document_id = upload(app, owner, tmp_path)
    opportunity = make_opportunity(research_team)
    draft = make_opportunity(research_team, publish=False)
    with app.app_context():
        provision_user("team2@example.test", PASSWORD, "Other team", "RESEARCH_TEAM")
    clients = {"anonymous": app.test_client(), "owner": owner[0], "other_talent": other_talent[0],
               "owner_team": research_team[0], "other_team": client_for(app, "team2@example.test")[0]}
    clients["invalid"] = app.test_client()
    clients["invalid"].set_cookie(COOKIE, "forged-session-token")
    expired = client_for(app, "talent@example.test")[0]
    with app.extensions["database"].transaction(write=True) as db:
        db.get(AuthSession, digest(expired.get_cookie(COOKIE).value)).expires_at = utcnow() - timedelta(seconds=1)
    clients["expired"] = expired

    values = {"doc": document_id, "opp": opportunity["id"], "draft": draft["id"],
              "talent": profile["talentId"]}
    observed = {}
    for endpoint, expected in MATRIX.items():
        path = "/api/v1" + endpoint.split(" ", 1)[1].format(**values)
        row = []
        for actor, status in zip(ACTORS, expected, strict=True):
            response = clients[actor].get(path)
            row.append(response.status_code)
            if status >= 400:
                data = checked(response, "Error", status)
                assert data["error"]["code"] == {401: "UNAUTHENTICATED", 403: "FORBIDDEN",
                                                 404: "NOT_FOUND"}.get(status, data["error"]["code"])
            else:
                assert response.status_code == status, (endpoint, actor, response.get_json())
            response.close()
        observed[endpoint] = row
    record_testsuite_property("be5_access_matrix", json.dumps(observed))


def test_inaccessible_resources_are_indistinguishable_from_missing_ones(app, tmp_path, world):
    (owner, _), (other_talent, other_profile) = world["talents"]
    document_id = upload(app, owner, tmp_path)

    def body(response):
        data = checked(response, "Error", 404)
        data.pop("requestId")
        return data

    for path in ("{}", "{}/file", "{}/extraction"):
        assert (body(other_talent[0].get(f"{DOCUMENTS}/" + path.format(document_id)))
                == body(other_talent[0].get(f"{DOCUMENTS}/" + path.format("doc_missing"))))
    other_team = world["other_team"][0]
    missing = f"{OPPORTUNITIES}/opp_missing"
    for suffix in ("/talent-matches", f"/talent-matches/{other_profile['talentId']}", "/shortlist"):
        assert (body(other_team.get(world["matches"].rsplit("/", 1)[0] + suffix))
                == body(other_team.get(missing + suffix)))
    team = world["team"][0]
    # Opted-out, unconfirmed, inactive and missing talent all produce the same 404.
    share(world["talents"][1][0], VISIBLE, discoverable=False)
    assert (body(team.get(f"{world['matches']}/{other_profile['talentId']}"))
            == body(team.get(f"{world['matches']}/talent_missing")))


def test_writes_reuse_session_role_and_csrf_checks(app, world):
    (owner, csrf), profile = world["talents"][0]
    team, team_csrf = world["team"]
    shortlist_item = f"{world['shortlist']}/{profile['talentId']}"
    privacy = {"expectedRevision": 0, "discoverable": True, "visibleFields": []}
    for client, method, path, payload in ((owner, "put", PRIVACY, privacy),
                                          (team, "put", shortlist_item, None),
                                          (owner, "put", f"{SAVED}/{world['opportunity']['id']}", None)):
        assert_error(getattr(client, method)(path, json=payload), 403, "CSRF_INVALID")
        assert_error(getattr(app.test_client(), method)(path, json=payload), 401, "UNAUTHENTICATED")
    assert_error(owner.put(shortlist_item, headers=headers(csrf)), 403, "FORBIDDEN")
    assert_error(team.put(PRIVACY, json=privacy, headers=headers(team_csrf)), 403, "FORBIDDEN")
    assert_error(world["other_team"][0].put(shortlist_item, headers=headers(world["other_team"][1])),
                 404, "NOT_FOUND")


# --------------------------------------------------------------------------
# 2-3. Hidden content never affects team filtering, scores, ranks or evidence
# --------------------------------------------------------------------------

def test_hidden_content_changes_do_not_affect_team_results(app, world, encoder):
    team, team_csrf = world["team"]
    for _, profile in world["talents"]:
        checked(team.put(f"{world['shortlist']}/{profile['talentId']}", headers=headers(team_csrf)),
                "CollectionState")
    owner, owner_profile = world["talents"][0]
    before_owner = checked(owner[0].get(f"{MATCHES}/{world['opportunity']['id']}"), "OwnerMatch")

    encoder.calls.clear()
    before = team_view(team, world)
    before_inputs = deepcopy(encoder.calls)
    assert before["list"]["total"] == 2
    assert before["shortlist"]["total"] == 2
    for name in ("q-hidden", "q-sentinel", "q-resume", "interest"):
        assert before[name]["total"] == 0, name

    # Change ONLY hidden/owner-only content for both talent, then reconfirm each.
    for signed, profile in world["talents"]:
        current = checked(signed[0].get(PROFILE), "Profile")
        skill = current["content"]["skills"][0]["title"]
        saved = checked(signed[0].put(PROFILE, json={"expectedRevision": current["revision"],
                                                     "content": content_for(skill, hidden=True)},
                                      headers=headers(signed[1])), "Profile")
        assert saved["revision"] == profile["revision"] + 1
        checked(signed[0].post(PROFILE + "/confirmation", json={"expectedRevision": saved["revision"]},
                               headers=headers(signed[1])), "Profile")

    encoder.calls.clear()
    after = team_view(team, world)
    assert after == before
    assert encoder.calls == before_inputs
    assert_no_private(after)
    for batch in before_inputs:
        assert_no_private(batch)

    # Control: the owner's own matching DOES use the newly added private evidence.
    after_owner = checked(owner[0].get(f"{MATCHES}/{world['opportunity']['id']}"), "OwnerMatch")
    statuses = lambda match: [row["status"] for row in match["requirements"]]  # noqa: E731
    assert statuses(before_owner) == ["MATCHED", "UNKNOWN", "MATCHED", "UNKNOWN"]
    assert statuses(after_owner) == ["MATCHED", "MATCHED", "MATCHED", "MATCHED"]
    assert after_owner["summary"]["recommendationScore"] > before_owner["summary"]["recommendationScore"]


def test_scoring_inputs_are_built_from_the_team_projection(app, world, encoder, monkeypatch):
    (owner, _), profile = world["talents"][0]
    talent_id = profile["talentId"]
    team, team_csrf = world["team"]
    checked(team.put(f"{world['shortlist']}/{talent_id}", headers=headers(team_csrf)), "CollectionState")
    current = checked(owner.get(PROFILE), "Profile")
    saved = checked(owner.put(PROFILE, json={"expectedRevision": current["revision"],
                                             "content": content_for("Python", hidden=True)},
                              headers=headers(world["talents"][0][0][1])), "Profile")
    checked(owner.post(PROFILE + "/confirmation", json={"expectedRevision": saved["revision"]},
                       headers=headers(world["talents"][0][0][1])), "Profile")
    # Interests visible; experience, outputs, courses and resume remain hidden.
    share(world["talents"][0][0], [*VISIBLE, "researchInterests"])
    with app.extensions["database"].transaction(write=True) as db:
        db.add(Document(id="private_doc", talent_id=talent_id, kind="CV", file_name="secret-cv.pdf",
                        media_type="application/pdf", storage_key="secret_storage_key",
                        status="READY", size_bytes=1))
        db.flush()
        for model, field in ((ProfileOrigin, "skills"), (ProfileComponentOrigin, "researchInterestText")):
            origin = db.get(model, (talent_id, field))
            if origin is None:
                db.add(model(talent_id=talent_id, field=field, source_type="USER_REVIEWED_DOCUMENT",
                             document_id="private_doc"))
            else:
                origin.source_type, origin.document_id = "USER_REVIEWED_DOCUMENT", "private_doc"
        # Legacy/extra keys in stored JSON must not pass through the projection.
        row = db.get(ProfileSkillDetails, talent_id)
        row.skills = [{**skill, "documentId": "private_doc", "sourceType": "USER_REVIEWED_DOCUMENT"}
                      for skill in row.skills]

    snapshots, pairs = [], []
    evaluate, enrich = team_service.evaluate_opportunity, team_service.enrich_matches

    def spy_evaluate(opportunity, snapshot, evidence_factory):
        snapshots.append(deepcopy(snapshot))
        return evaluate(opportunity, snapshot, evidence_factory)

    def spy_enrich(batch):
        pairs.extend(deepcopy([profile for _, profile, _, _ in batch]))
        return enrich(batch)

    monkeypatch.setattr(team_service, "evaluate_opportunity", spy_evaluate)
    monkeypatch.setattr(team_service, "enrich_matches", spy_enrich)
    encoder.calls.clear()
    responses = [checked(team.get(world["matches"]), "TalentMatchPage"),
                 checked(team.get(f"{world['matches']}/{talent_id}"), "TeamMatch"),
                 checked(team.get(world["shortlist"]), "TalentMatchPage")]

    allowed = {"skills", "skillRecords", "tagLabels", "researchInterests", "researchInterestText",
               "customInterestTags", "education", "researchExperience", "researchOutputs"}
    # List scores both talent, detail one, shortlist only the shortlisted one.
    assert len(snapshots) == len(pairs) == 2 + 1 + 1
    for snapshot in [*snapshots, *pairs]:
        assert set(snapshot) == allowed
        assert snapshot["researchExperience"] == snapshot["researchOutputs"] == []
        for record in snapshot["skillRecords"]:
            assert set(record) == set(SKILL_KEYS)
        for tag in snapshot["customInterestTags"]:
            assert set(tag) <= set(PERSONAL_TAG_KEYS)
    owned = [s for s in snapshots if s["researchInterestText"]]
    assert owned and all(s["researchInterestText"].startswith("HIDDEN_INTEREST_SENTINEL") for s in owned)
    # The interest text/tag is now *visible*, so only resume/experience/output/course stay private.
    still_private = ("HIDDEN_EXPERIENCE_SENTINEL", "HIDDEN_ORG_SENTINEL", "HIDDEN_OUTPUT_SENTINEL",
                     "HIDDEN_COURSE_SENTINEL", RESUME, "private_doc", "secret-cv.pdf", "secret_storage_key")
    dumped = json.dumps([snapshots, pairs, encoder.calls, responses], ensure_ascii=False)
    for secret in still_private:
        assert secret not in dumped, secret
    for response in responses:
        for item in response.get("items", [response]):
            for skill in item["talent"]["fields"].get("skills", []):
                assert set(skill) == set(SKILL_KEYS)


# --------------------------------------------------------------------------
# 4. Revocation and field hiding apply to the next request, shortlists included
# --------------------------------------------------------------------------

def test_revocation_and_hiding_apply_to_next_request_including_shortlist(app, world):
    team, team_csrf = world["team"]
    signed, profile = world["talents"][0]
    talent_id = profile["talentId"]
    item = f"{world['shortlist']}/{talent_id}"
    detail = f"{world['matches']}/{talent_id}"
    checked(team.put(item, headers=headers(team_csrf)), "CollectionState")

    def shortlisted():
        return {row["talent"]["talentId"]: row for row in
                checked(team.get(world["shortlist"]), "TalentMatchPage")["items"]}

    visible = shortlisted()[talent_id]
    assert visible["summary"]["score"] > 0
    assert checked(team.get(detail), "TeamMatch")["requirements"][0]["evidence"]

    share(signed, ["displayName"])  # Hide skills and education.
    hidden = shortlisted()[talent_id]
    assert set(hidden["talent"]["fields"]) == {"displayName"}
    assert hidden["summary"]["score"] == 0
    listed = {row["talent"]["talentId"]: row for row in
              checked(team.get(world["matches"]), "TalentMatchPage")["items"]}
    assert hidden["summary"] == listed[talent_id]["summary"]
    assert hidden["summary"] == checked(team.get(detail), "TeamMatch")["summary"]
    assert all(not row["evidence"] for row in checked(team.get(detail), "TeamMatch")["requirements"])
    assert checked(team.get(f"{world['matches']}?skill=python"), "TalentMatchPage")["total"] == 0

    share(signed, VISIBLE, discoverable=False)
    assert talent_id not in shortlisted()
    assert talent_id not in [row["talent"]["talentId"] for row in
                             checked(team.get(world["matches"]), "TalentMatchPage")["items"]]
    for response in (team.get(detail), team.get(item), team.put(item, headers=headers(team_csrf))):
        assert_error(response, 404, "NOT_FOUND")
    # The ID-only relationship survives; re-consent shows CURRENT visibility only.
    share(signed, ["displayName"])
    assert set(shortlisted()[talent_id]["talent"]["fields"]) == {"displayName"}


# --------------------------------------------------------------------------
# 5. Edited, unconfirmed profiles cannot keep using the old confirmation
# --------------------------------------------------------------------------

def test_edit_before_reconfirmation_hides_old_content_and_owner_matching_rejects(app, world):
    team, team_csrf = world["team"]
    (client, csrf), profile = world["talents"][0]
    talent_id = profile["talentId"]
    checked(team.put(f"{world['shortlist']}/{talent_id}", headers=headers(team_csrf)), "CollectionState")
    assert checked(team.get(f"{world['matches']}?skill=python"), "TalentMatchPage")["total"] == 1

    edited = content_for("Rust")
    saved = checked(client.put(PROFILE, json={"expectedRevision": profile["revision"], "content": edited},
                               headers=headers(csrf)), "Profile")
    assert saved["confirmation"]["status"] == "UNCONFIRMED"
    for query in ("", "?skill=python", "?skill=rust"):
        ids = [row["talent"]["talentId"] for row in
               checked(team.get(world["matches"] + query), "TalentMatchPage")["items"]]
        assert talent_id not in ids
    assert talent_id not in [row["talent"]["talentId"] for row in
                             checked(team.get(world["shortlist"]), "TalentMatchPage")["items"]]
    assert_error(team.get(f"{world['matches']}/{talent_id}"), 404, "NOT_FOUND")
    for path in (RECOMMENDATIONS, f"{MATCHES}/{world['opportunity']['id']}"):
        assert_error(client.get(path), 409, "PROFILE_UNCONFIRMED")

    checked(client.post(PROFILE + "/confirmation", json={"expectedRevision": saved["revision"]},
                        headers=headers(csrf)), "Profile")
    assert checked(team.get(f"{world['matches']}?skill=python"), "TalentMatchPage")["total"] == 0
    detail = checked(team.get(f"{world['matches']}/{talent_id}"), "TeamMatch")
    assert [skill["title"] for skill in detail["talent"]["fields"]["skills"]] == ["Rust"]
    assert detail["requirements"][0]["status"] == "UNKNOWN"


# --------------------------------------------------------------------------
# 6. Documents, extraction, provenance and personal tags stay with the owner
# --------------------------------------------------------------------------

def test_documents_and_personal_tags_are_owner_only(app, tmp_path, world):
    (owner, owner_csrf), _ = world["talents"][0]
    (other, other_csrf), other_profile = world["talents"][1]
    team, team_csrf = world["team"]
    document_id = upload(app, (owner, owner_csrf), tmp_path)
    for path in ("", "/file", "/extraction"):
        assert_error(other.get(f"{DOCUMENTS}/{document_id}{path}"), 404, "NOT_FOUND")
        assert_error(team.get(f"{DOCUMENTS}/{document_id}{path}"), 403, "FORBIDDEN")
    apply = {"expectedProfileRevision": other_profile["revision"], "sections": {"skills": []}}
    assert_error(other.post(f"{DOCUMENTS}/{document_id}/apply", json=apply, headers=headers(other_csrf)),
                 404, "NOT_FOUND")
    assert document_id not in json.dumps(checked(other.get(DOCUMENTS), "DocumentPage"))

    current = checked(owner.get(PROFILE), "Profile")
    content = content_for("Python")
    content["customInterestTags"] = [{"label": "Owner private topic"}]
    owned = checked(owner.put(PROFILE, json={"expectedRevision": current["revision"], "content": content},
                              headers=headers(owner_csrf)), "Profile")
    personal_id = owned["content"]["customInterestTags"][0]["id"]

    other_current = checked(other.get(PROFILE), "Profile")
    stolen = content_for("SQL")
    stolen["customInterestTags"] = [{"id": personal_id, "label": "Owner private topic"}]
    assert_error(other.put(PROFILE, json={"expectedRevision": other_current["revision"], "content": stolen},
                           headers=headers(other_csrf)), 422, "VALIDATION_ERROR")
    assert checked(other.get(PROFILE), "Profile") == other_current
    stolen["customInterestTags"] = []
    stolen["researchInterests"] = [personal_id]
    assert_error(other.put(PROFILE, json={"expectedRevision": other_current["revision"], "content": stolen},
                           headers=headers(other_csrf)), 422, "VALIDATION_ERROR")
    # Teams can only filter by shared vocabulary; personal tag IDs are rejected.
    assert_error(team.get(f"{world['matches']}?interestTagId={personal_id}"), 422, "VALIDATION_ERROR")
    assert all(not tag["id"].startswith("personal_") for tag in
               team.get("/api/v1/tags").get_json()["items"])


# --------------------------------------------------------------------------
# 7. Logout, expiry, deactivation and account switching with independent clients
# --------------------------------------------------------------------------

def replay(app, cookie):
    client = app.test_client()
    client.set_cookie(COOKIE, cookie)
    return client


def test_logout_expiry_and_account_switching_with_independent_clients(app, world):
    url = world["matches"]
    first, first_csrf = client_for(app, "talent@example.test")
    second, _ = client_for(app, "talent@example.test")
    stolen = first.get_cookie(COOKIE).value

    assert first.post("/api/v1/auth/logout", headers=headers(first_csrf)).status_code == 204
    assert_error(first.get(PROFILE), 401, "UNAUTHENTICATED")
    assert_error(replay(app, stolen).get(PROFILE), 401, "UNAUTHENTICATED")
    checked(second.get(PROFILE), "Profile")  # Other sessions of the same account survive.

    team, _ = client_for(app, "team@example.test")
    team_cookie = team.get_cookie(COOKIE).value
    checked(team.get(url), "TalentMatchPage")
    with app.extensions["database"].transaction(write=True) as db:
        db.get(AuthSession, digest(team_cookie)).expires_at = utcnow() - timedelta(seconds=1)
    for client in (team, replay(app, team_cookie)):
        assert_error(client.get(url), 401, "UNAUTHENTICATED")
    checked(world["team"][0].get(url), "TalentMatchPage")  # Independent session unaffected.

    # Switch account in ONE client: talent -> team. The talent cookie is revoked.
    switching, _ = client_for(app, "talent@example.test")
    talent_cookie = switching.get_cookie(COOKIE).value
    sign_in(switching, "team@example.test")
    assert switching.get_cookie(COOKIE).value != talent_cookie
    assert_error(replay(app, talent_cookie).get(PROFILE), 401, "UNAUTHENTICATED")
    assert_error(switching.get(PROFILE), 403, "FORBIDDEN")
    assert_error(switching.get(RECOMMENDATIONS), 403, "FORBIDDEN")
    checked(switching.get(url), "TalentMatchPage")
    session = checked(switching.get("/api/v1/auth/session"), "Session")
    assert session["user"]["role"] == "RESEARCH_TEAM"
    # ...and back: team data is no longer reachable from this client.
    sign_in(switching, "talent@example.test")
    assert_error(switching.get(url), 403, "FORBIDDEN")
    checked(switching.get(PROFILE), "Profile")

    # Deactivating an account ends its sessions and removes it from team results.
    (owner, _), profile = world["talents"][0]
    with app.extensions["database"].transaction(write=True) as db:
        db.get(User, db.get(TalentProfile, profile["talentId"]).user_id).active = False
    assert_error(owner.get(PROFILE), 401, "UNAUTHENTICATED")
    ids = [row["talent"]["talentId"] for row in
           checked(world["team"][0].get(url), "TalentMatchPage")["items"]]
    assert profile["talentId"] not in ids
    assert_error(world["team"][0].get(f"{url}/{profile['talentId']}"), 404, "NOT_FOUND")
