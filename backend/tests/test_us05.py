"""Real SQLite/API coverage for consent-filtered team discovery (US-05)."""

from copy import deepcopy

import pytest

from backend.src.db.models import Document, Opportunity, ProfileOrigin
from backend.src.features.auth.routes import provision_user
from conftest import PASSWORD, headers, sign_in
from test_us04 import (PROFILE, OPPORTUNITIES, assert_error, checked, confirm_profile,
                       example, make_opportunity, research_team)

PRIVACY = "/api/v1/me/privacy"


def share(signed, fields, discoverable=True):
    client, csrf = signed
    fields = [field for field in fields if field not in ("researchInterestText", "customInterestTags", "resumeDescription")]
    current = checked(client.get(PRIVACY), "Privacy")
    return checked(client.put(PRIVACY, json={
        "expectedRevision": current["revision"],
        "discoverable": discoverable, "visibleFields": fields,
    }, headers=headers(csrf)), "Privacy")


@pytest.fixture
def discovery(signed, research_team):
    profile = confirm_profile(signed)
    share(signed, list(profile["content"]))
    opportunity = make_opportunity(research_team)
    url = f"{OPPORTUNITIES}/{opportunity['id']}/talent-matches"
    return signed, research_team, profile, opportunity, url


def test_visible_content_four_statuses_and_no_owner_metadata(app, discovery):
    _, (team, _), profile, opportunity, url = discovery
    with app.extensions["database"].transaction(write=True) as db:
        db.add(Document(id="private_doc", talent_id=profile["talentId"], kind="CV",
                        file_name="private-cv.pdf", media_type="application/pdf",
                        storage_key="private_storage", status="READY", size_bytes=1))
        db.flush()
        origin = db.get(ProfileOrigin, (profile["talentId"], "skills"))
        origin.source_type = "USER_REVIEWED_DOCUMENT"
        origin.document_id = "private_doc"
    response = team.get(url)
    assert response.headers["Cache-Control"] == "no-store"
    page = checked(response, "TalentMatchPage")
    assert page["total"] == 1
    detail = checked(team.get(f"{url}/{profile['talentId']}"), "TeamMatch")
    assert detail["talent"]["fields"] == {key: value for key, value in profile["content"].items() if key != "resumeDescription"}
    assert detail["opportunityRevision"] == opportunity["revision"]
    assert detail["summary"] == page["items"][0]["summary"]
    assert detail["summary"]["score"] == 50
    assert detail["summary"]["unknownWeightPercent"] == 16.67
    assert [r["status"] for r in detail["requirements"]] == ["MATCHED", "PARTIAL", "GAP", "UNKNOWN"]
    assert detail["requirements"][-1]["evidence"] == []
    for result in detail["requirements"]:
        for evidence in result["evidence"]:
            assert set(evidence) == {"field", "recordId", "valueSummary"}
            assert evidence["field"] in detail["talent"]["fields"]

    def check_keys(value):
        if isinstance(value, dict):
            assert not set(value) & {"email", "origins", "documentId", "sourceType",
                                      "confirmedRevision", "fileName", "storageKey", "downloadUrl"}
            for item in value.values():
                check_keys(item)
        elif isinstance(value, list):
            for item in value:
                check_keys(item)
    check_keys(page)
    check_keys(detail)


@pytest.mark.parametrize("fields", [[], ["displayName"], ["education", "researchExperience"]])
def test_hidden_claims_never_influence_scores_or_explanations(discovery, fields):
    signed, (team, _), profile, opportunity, url = discovery
    share(signed, fields)
    detail = checked(team.get(f"{url}/{profile['talentId']}"), "TeamMatch")
    assert set(detail["talent"]["fields"]) == set(fields)
    assert detail["summary"]["score"] == 0
    assert detail["summary"]["unknownWeightPercent"] == 100
    assert detail["summary"]["requiredGapCount"] == 0
    for result in detail["requirements"]:
        assert result["status"] == "UNKNOWN"
        assert result["evidence"] == []
        assert result["reason"] == "There is insufficient shared evidence for this requirement."
    page = checked(team.get(url), "TalentMatchPage")
    assert page["total"] == 1
    assert page["items"][0]["summary"] == detail["summary"]
    # The owner's private evidence remains usable for their own recommendations.
    own = checked(signed[0].get(f"/api/v1/me/opportunity-matches/{opportunity['id']}"), "OwnerMatch")
    assert own["summary"]["score"] == 50


def test_interest_visibility_and_negative_claim_priority(discovery):
    signed, (team, csrf), profile, opportunity, url = discovery
    content = deepcopy(opportunity["content"])
    content["requirements"] = [
        {"id": "interest", "kind": "INTEREST", "label": "Machine learning",
         "importance": "REQUIRED", "tagIds": ["interest_ml"]},
        {"id": "mixed", "kind": "SKILL", "label": "Python and interviews",
         "importance": "REQUIRED", "tagIds": ["skill_python", "skill_interviews"]},
    ]
    checked(team.put(f"{OPPORTUNITIES}/{opportunity['id']}", json={
        "expectedRevision": opportunity["revision"], "content": content,
    }, headers=headers(csrf)), "Opportunity")
    detail = checked(team.get(f"{url}/{profile['talentId']}"), "TeamMatch")
    assert [r["status"] for r in detail["requirements"]] == ["MATCHED", "GAP"]
    assert detail["requirements"][0]["evidence"][0]["recordId"] == "interest_ml"
    assert [e["recordId"] for e in detail["requirements"][1]["evidence"]] == ["skill_interviews"]
    assert detail["summary"]["requiredGapCount"] == 1
    share(signed, ["researchInterests"])
    hidden = checked(team.get(f"{url}/{profile['talentId']}"), "TeamMatch")
    assert [r["status"] for r in hidden["requirements"]] == ["MATCHED", "UNKNOWN"]
    assert hidden["summary"]["requiredGapCount"] == 0
    assert hidden["summary"]["unknownWeightPercent"] == 50


def test_revocation_profile_edits_and_opportunity_edits_are_immediate(discovery):
    signed, (team, team_csrf), profile, opportunity, url = discovery
    detail_url = f"{url}/{profile['talentId']}"
    share(signed, ["skills"], discoverable=False)
    assert checked(team.get(url), "TalentMatchPage")["total"] == 0
    assert_error(team.get(detail_url), 404, "NOT_FOUND")
    share(signed, ["skills"])
    assert checked(team.get(url), "TalentMatchPage")["total"] == 1
    edited = deepcopy(profile["content"])
    edited["skills"] = []
    saved = checked(signed[0].put(PROFILE, json={"expectedRevision": profile["revision"],
                                               "content": edited}, headers=headers(signed[1])), "Profile")
    assert checked(team.get(url), "TalentMatchPage")["total"] == 0
    assert_error(team.get(detail_url), 404, "NOT_FOUND")
    checked(signed[0].post(PROFILE + "/confirmation", json={"expectedRevision": saved["revision"]},
                           headers=headers(signed[1])), "Profile")
    assert checked(team.get(detail_url), "TeamMatch")["summary"]["unknownWeightPercent"] == 100
    share(signed, ["researchInterests"])
    changed = deepcopy(opportunity["content"])
    changed["requirements"] = [{"id": "ml", "kind": "INTEREST", "label": "ML",
                                "importance": "REQUIRED", "tagIds": ["interest_ml"]}]
    updated = checked(team.put(f"{OPPORTUNITIES}/{opportunity['id']}", json={
        "expectedRevision": opportunity["revision"], "content": changed,
    }, headers=headers(team_csrf)), "Opportunity")
    detail = checked(team.get(detail_url), "TeamMatch")
    assert detail["opportunityRevision"] == updated["revision"]
    assert detail["summary"]["score"] == 100


def test_ranking_global_pages_and_total_after_permission_filtering(app, research_team):
    team, _ = research_team
    opportunity = make_opportunity(research_team, [example("opportunity-create.json")["requirements"][0]])
    url = f"{OPPORTUNITIES}/{opportunity['id']}/talent-matches"
    expected = []
    for i, claim in enumerate(["HAS", "HAS", "DOES_NOT_HAVE", None, "HAS", "HAS"]):
        email = f"candidate{i}@example.test"
        with app.app_context():
            provision_user(email, PASSWORD, f"Candidate {i}", "TALENT")
        client = app.test_client()
        signed = client, sign_in(client, email)
        content = example("profile-write.json")["content"]
        content["skills"] = ([{"id": "skill_python", "title": ("No " if claim == "DOES_NOT_HAVE" else "") + "Python", "evidenceText": ""}]
                             if claim else [])
        profile = confirm_profile(signed, content)
        share(signed, ["skills"], discoverable=i != 4)
        if i == 5:
            content["displayName"] = "Changed since confirmation"
            checked(client.put(PROFILE, json={"expectedRevision": profile["revision"], "content": content},
                               headers=headers(signed[1])), "Profile")
        if i < 4:
            expected.append(profile["talentId"])
    expected[:2] = sorted(expected[:2])
    items = []
    for page_number in (1, 2, 3):
        page = checked(team.get(f"{url}?page={page_number}&pageSize=2"), "TalentMatchPage")
        assert page["total"] == 4
        assert page["page"] == page_number
        items.extend(page["items"])
        if page_number == 3:
            assert page["items"] == []
    assert [i["talent"]["talentId"] for i in items] == expected
    assert [i["rank"] for i in items] == [1, 2, 3, 4]
    assert [i["summary"]["score"] for i in items] == [100, 100, 0, 0]
    assert [i["summary"]["unknownWeightPercent"] for i in items] == [0, 0, 0, 100]


def test_authorization_and_unavailable_ids(app, client, discovery):
    signed, team, profile, _, url = discovery
    with app.app_context():
        provision_user("team2@example.test", PASSWORD, "Other team", "RESEARCH_TEAM")
    other = app.test_client()
    sign_in(other, "team2@example.test")
    for path in (url, f"{url}/{profile['talentId']}"):
        assert_error(app.test_client().get(path), 401, "UNAUTHENTICATED")
        assert_error(signed[0].get(path), 403, "FORBIDDEN")
        assert_error(other.get(path), 404, "NOT_FOUND")
    draft = make_opportunity(team, publish=False)
    for opportunity_id in (draft["id"], "missing"):
        path = f"{OPPORTUNITIES}/{opportunity_id}/talent-matches"
        assert_error(team[0].get(path), 404, "NOT_FOUND")
        assert_error(team[0].get(f"{path}/{profile['talentId']}"), 404, "NOT_FOUND")
    other_talent = app.test_client()
    sign_in(other_talent, "other@example.test")
    unconfirmed = checked(other_talent.get(PROFILE), "Profile")
    for talent_id in (unconfirmed["talentId"], "missing"):
        assert_error(team[0].get(f"{url}/{talent_id}"), 404, "NOT_FOUND")
    assert_error(team[0].get(url + "/invalid!"), 422, "VALIDATION_ERROR")
    assert_error(team[0].get(f"{OPPORTUNITIES}/invalid!/talent-matches"), 422, "VALIDATION_ERROR")


@pytest.mark.parametrize("query", ["page=0", "page=-1", "page=abc", "page=1&page=2",
                                   "pageSize=0", "pageSize=101", "pageSize=1.5"])
def test_invalid_pagination(research_team, query):
    opportunity = make_opportunity(research_team)
    url = f"{OPPORTUNITIES}/{opportunity['id']}/talent-matches?{query}"
    assert_error(research_team[0].get(url), 422, "VALIDATION_ERROR")


def test_empty_results_and_legacy_zero_requirements(app, signed, research_team):
    opportunity = make_opportunity(research_team, [], publish=False)
    with app.extensions["database"].transaction(write=True) as db:
        db.get(Opportunity, opportunity["id"]).status = "PUBLISHED"
    url = f"{OPPORTUNITIES}/{opportunity['id']}/talent-matches"
    assert checked(research_team[0].get(url), "TalentMatchPage")["items"] == []
    profile = confirm_profile(signed)
    share(signed, [])
    detail = checked(research_team[0].get(f"{url}/{profile['talentId']}"), "TeamMatch")
    assert detail["summary"]["score"] is None
    assert detail["summary"]["unknownWeightPercent"] is None
    assert detail["summary"]["evaluationStatus"] == "INSUFFICIENT_CRITERIA"
    assert detail["requirements"] == []


def test_privacy_defaults_noops_conflicts_and_confirmation(signed):
    client, csrf = signed
    initial = checked(client.get(PRIVACY), "Privacy")
    assert initial["revision"] == 0
    assert initial["discoverable"] is False
    assert initial["visibleFields"] == []
    assert share(signed, [], False) == initial
    profile = confirm_profile(signed)
    saved = share(signed, ["skills", "displayName"])
    assert saved["revision"] == 1
    assert share(signed, ["displayName", "skills"]) == saved
    response = client.put(PRIVACY, json={"expectedRevision": 0, "discoverable": False,
                                       "visibleFields": []}, headers=headers(csrf))
    assert_error(response, 409, "REVISION_CONFLICT")
    assert response.get_json()["error"]["currentRevision"] == 1
    assert checked(client.get(PRIVACY), "Privacy") == saved
    assert checked(client.get(PROFILE), "Profile") == profile


@pytest.mark.parametrize("fields", [["email"], ["documentId"], ["skills", "skills"]])
def test_privacy_rejects_non_whitelisted_and_duplicate_fields(signed, fields):
    client, csrf = signed
    assert_error(client.put(PRIVACY, json={"expectedRevision": 0, "discoverable": True,
                                         "visibleFields": fields}, headers=headers(csrf)),
                 422, "VALIDATION_ERROR")


def test_privacy_is_owner_only_and_mutations_require_csrf(app, signed, research_team):
    for method in ("get", "put"):
        assert_error(getattr(app.test_client(), method)(PRIVACY), 401, "UNAUTHENTICATED")
        assert_error(getattr(research_team[0], method)(PRIVACY), 403, "FORBIDDEN")
    client, csrf = signed
    payload = {"expectedRevision": 0, "discoverable": True, "visibleFields": ["skills"]}
    assert client.put(PRIVACY, json=payload).status_code == 403
    assert client.put(PRIVACY, json=payload, headers={**headers(csrf), "Origin": "https://other.test"}).status_code == 403
    share(signed, ["skills"])
    other = app.test_client()
    sign_in(other, "other@example.test")
    assert checked(other.get(PRIVACY), "Privacy")["discoverable"] is False
