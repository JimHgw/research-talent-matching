"""US-14: real API composition, privacy, ranking, expiry and additive upgrades."""

from copy import deepcopy
from datetime import datetime

import pytest
from sqlalchemy import inspect

from backend.src.db.models import Opportunity
from backend.src.db.opportunity_upgrade import upgrade_opportunity_search
from backend.src.shared.universities import GO8
from conftest import headers, sign_in
from test_us04 import (PROFILE, RECOMMENDATIONS, OPPORTUNITIES, checked, confirm_profile,
                       example, research_team)
from test_us05 import share


def opportunity(team, **changes):
    client, csrf = team
    value = {**example("opportunity-create.json"), **changes}
    draft = checked(client.post(OPPORTUNITIES, json=value, headers=headers(csrf)), "Opportunity", 201)
    return checked(client.post(f"{OPPORTUNITIES}/{draft['id']}/publish", json={
        "expectedRevision": draft["revision"]}, headers=headers(csrf)), "Opportunity")


def page(client, path=OPPORTUNITIES, **query):
    schema = "RecommendationPage" if path == RECOMMENDATIONS else "TalentMatchPage" if path.endswith("talent-matches") else "OpportunityPage"
    return checked(client.get(path, query_string=query), schema)


def error_field(response, field):
    data = checked(response, "Error", 422)
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert data["error"]["fieldErrors"][0]["field"] == field


def test_opportunity_filters_compose_before_total_and_recommendation_ranking(signed, research_team):
    confirm_profile(signed)
    common = dict(university="  UNSW  Sydney ", discipline="Computer Science", researchArea="Data systems",
                  opportunityType="PHD", deadlineAt="2099-11-01T10:00:00+10:00")
    first = opportunity(research_team, **common, title="AI for Café research")
    second = opportunity(research_team, **{**common, "university": "USYD", "opportunityType": "MASTERS"})
    opportunity(research_team, **{**common, "researchArea": "Health"})
    opportunity(research_team, **{**common, "disciplineGroup": "BUSINESS"})
    opportunity(research_team, **{**common, "deadlineAt": None})
    opportunity(research_team, **{**common, "deadlineAt": "2099-11-02T00:00:00Z"})
    query = dict(university=["ｕｎｓｗ sydney", "usyd"], disciplineGroup="STEM", discipline="computer science",
                 researchArea="data systems", opportunityType=["PHD", "MASTERS"],
                 deadlineFrom="2099-11-01T00:00:00Z", deadlineTo="2099-11-02T00:00:00Z", pageSize=1)
    for path, key in ((OPPORTUNITIES, None), (RECOMMENDATIONS, "opportunity")):
        responses = [page(signed[0], path, **query, page=n) for n in (1, 2, 3)]
        assert [r["total"] for r in responses] == [2, 2, 2]
        items = [item for r in responses for item in r["items"]]
        assert {item[key]["id"] if key else item["id"] for item in items} == {first["id"], second["id"]}
        if key:
            assert [item["rank"] for item in items] == [1, 2]
        assert not responses[-1]["items"]
        literal = page(signed[0], path, q="cafe\u0301")
        assert literal["total"] == 1
        assert page(signed[0], path, q="%_'")["total"] == 0
        assert page(signed[0], path)["total"] == 6
        assert page(signed[0], path, page="9" * 100)["items"] == []


@pytest.mark.parametrize("query,field", [
    ("q=", "q"), ("q=%20%20", "q"), ("q=a&q=b", "q"), ("q=" + "a" * 201, "q"),
    ("university=", "university"), ("disciplineGroup=ARTS", "disciplineGroup"),
    ("opportunityType=phd", "opportunityType"), ("unknown=a", "unknown"),
    ("deadlineFrom=2099-01-01", "deadlineFrom"),
    ("deadlineFrom=2099-01-01T00:00:00", "deadlineFrom"),
    ("deadlineFrom=2099-02-30T00:00:00Z", "deadlineFrom"),
    ("deadlineFrom=2099-01-01T00:00:00Z&deadlineFrom=2099-01-02T00:00:00Z", "deadlineFrom"),
    ("deadlineFrom=2099-01-01T00:00:00Z&deadlineTo=2099-01-01T00:00:00Z", "deadlineTo"),
    ("deadlineFrom=2099-01-02T00:00:00Z&deadlineTo=2099-01-01T00:00:00Z", "deadlineTo"),
])
def test_strict_opportunity_queries(signed, query, field):
    confirm_profile(signed)
    for path in (OPPORTUNITIES, RECOMMENDATIONS):
        error_field(signed[0].get(path + "?" + query), field)


def test_private_drafts_owner_scope_and_expiry_boundary(app, signed, research_team, monkeypatch):
    confirm_profile(signed)
    active = opportunity(research_team, title="Active")
    expired = opportunity(research_team, title="Boundary", deadlineAt="2099-01-01T00:00:00Z")
    draft = checked(research_team[0].post(OPPORTUNITIES, json=example("opportunity-create.json"),
                                        headers=headers(research_team[1])), "Opportunity", 201)
    now = datetime(2099, 1, 1)
    # Freeze only opportunity availability. Session expiry is a separate clock.
    monkeypatch.setattr("backend.src.features.opportunities.availability.utcnow", lambda: now)
    monkeypatch.setattr("backend.src.features.opportunities.service.utcnow", lambda: now)
    assert [i["id"] for i in page(signed[0])["items"]] == [active["id"]]
    assert page(signed[0], RECOMMENDATIONS)["total"] == 1
    owned = page(research_team[0], scope="mine")
    assert owned["total"] == 3
    assert {i["availabilityStatus"] for i in owned["items"]} == {"DRAFT", "ACTIVE", "EXPIRED"}
    assert checked(signed[0].get(f"{OPPORTUNITIES}/{expired['id']}"), "Opportunity")["availabilityStatus"] == "EXPIRED"
    assert checked(signed[0].get(f"{OPPORTUNITIES}/{draft['id']}"), "Error", 404)
    assert checked(signed[0].get(f"/api/v1/me/opportunity-matches/{expired['id']}"), "Error", 409)["error"]["code"] == "OPPORTUNITY_EXPIRED"
    url = f"{OPPORTUNITIES}/{expired['id']}/talent-matches"
    assert checked(research_team[0].get(url), "Error", 409)["error"]["code"] == "OPPORTUNITY_EXPIRED"
    other = app.test_client()
    sign_in(other, "other@example.test")
    checked(other.get(OPPORTUNITIES + "?scope=mine"), "Error", 403)


def test_deadline_edits_preserve_expiry_and_legacy_optional_fields(app, research_team, monkeypatch):
    item = opportunity(research_team, opportunityType="PHD", deadlineAt="2099-01-01T00:00:00Z")
    now = datetime(2099, 1, 1)
    monkeypatch.setattr("backend.src.features.opportunities.service.utcnow", lambda: now)
    monkeypatch.setattr("backend.src.features.opportunities.availability.utcnow", lambda: now)
    client, csrf = research_team
    url = f"{OPPORTUNITIES}/{item['id']}"
    legacy = example("opportunity-create.json")
    saved = checked(client.put(url, json={"expectedRevision": item["revision"], "content": legacy}, headers=headers(csrf)), "Opportunity")
    assert saved["content"]["opportunityType"] == "PHD"
    assert saved["content"]["deadlineAt"].startswith("2099-01-01")
    future = {**saved["content"], "deadlineAt": "2099-02-01T00:00:00Z"}
    saved = checked(client.put(url, json={"expectedRevision": saved["revision"], "content": future}, headers=headers(csrf)), "Opportunity")
    assert saved["availabilityStatus"] == "EXPIRED"
    assert checked(client.post(url + "/publish", json={"expectedRevision": saved["revision"]}, headers=headers(csrf)), "Opportunity")["availabilityStatus"] == "EXPIRED"
    checked(client.put(url, json={"expectedRevision": 1, "content": future, "reopen": True}, headers=headers(csrf)), "Error", 409)
    reopened = checked(client.put(url, json={"expectedRevision": saved["revision"], "content": future, "reopen": True}, headers=headers(csrf)), "Opportunity")
    assert reopened["availabilityStatus"] == "ACTIVE" and reopened["revision"] == saved["revision"] + 1
    assert checked(client.put(url, json={"expectedRevision": reopened["revision"], "content": future, "reopen": True}, headers=headers(csrf)), "Opportunity") == reopened


def test_talent_filters_use_only_positive_visible_confirmed_fields(app, signed, research_team):
    content = deepcopy(example("profile-write.json")["content"])
    content.update(researchInterestText="Rare disease imaging", customInterestTags=[{"label": "Retinal diagnostics"}],
                   resumeDescription="PRIVATE-RESUME-NEEDLE")
    profile = confirm_profile(signed, content)
    share(signed, ["skills", "researchInterests"])
    other = app.test_client()
    other_signed = other, sign_in(other, "other@example.test")
    second = confirm_profile(other_signed, {**content, "displayName": "Other scientist"})
    share(other_signed, ["skills", "researchInterests"])
    item = opportunity(research_team)
    client = research_team[0]
    url = f"{OPPORTUNITIES}/{item['id']}/talent-matches"
    query = dict(skillTagId=["skill_python", "skill_sql"], interestTagId="interest_ml", q="retinal")
    result = page(client, url, **query, pageSize=1, page=2)
    assert result["total"] == 2 and result["items"][0]["rank"] == 2
    assert page(client, url, skillTagId="skill_interviews")["total"] == 0
    assert page(client, url, q="PRIVATE-RESUME-NEEDLE")["total"] == 0
    for text in ("rare DISEASE", "retinal", "Machine learning"):
        assert page(client, url, q=text)["total"] == 2
    share(signed, [])
    share(other_signed, [])
    hidden_before = page(client, url)
    assert hidden_before["total"] == 2
    assert page(client, url, **query)["total"] == 0
    for query_string, field in (("skillTagId=missing", "skillTagId"), ("skillTagId=interest_ml", "skillTagId"),
                                ("interestTagId=skill_python", "interestTagId"), ("q=x&q=y", "q"),
                                ("resumeDescription=x", "resumeDescription")):
        error_field(client.get(url + "?" + query_string), field)
    content["researchInterestText"] = "Hidden changed text"
    confirm_profile(signed, content)
    assert page(client, url) == hidden_before
    assert page(client, url, q="Hidden changed text")["total"] == 0
    share(signed, ["researchInterests"], discoverable=False)
    assert page(client, url)["total"] == 1
    checked(client.get(f"{url}/{profile['talentId']}"), "Error", 404)
    # An edit invalidates confirmation before the next query.
    changed = {**content, "displayName": "Unconfirmed edit"}
    checked(other.put(PROFILE, json={"expectedRevision": second["revision"], "content": changed}, headers=headers(other_signed[1])), "Profile")
    assert page(client, url)["total"] == 0


def test_additive_upgrade_preserves_old_opportunities_and_is_repeatable(app, research_team):
    item = opportunity(research_team)
    database = app.extensions["database"]
    # Drop just the new nullable columns to reproduce the exact old table shape.
    with database.engine.begin() as connection:
        # BE-8's active-page index depends on expired_at; legacy tables had neither.
        for index in Opportunity.__table__.indexes:
            if index.name == "ix_opportunities_active_page":
                index.drop(connection, checkfirst=True)
        for name in ("opportunity_type", "deadline_at", "expired_at"):
            connection.exec_driver_sql(f"ALTER TABLE opportunities DROP COLUMN {name}")
    assert upgrade_opportunity_search(database)
    assert not upgrade_opportunity_search(database)
    assert {c["name"] for c in inspect(database.engine).get_columns("opportunities")} >= {"deadline_at", "opportunity_type", "expired_at"}
    with database.transaction() as db:
        row = db.get(Opportunity, item["id"])
        assert row.revision == item["revision"] and row.deadline_at is None and row.expired_at is None
    assert page(research_team[0], scope="mine")["items"] == [item]


def test_free_text_skill_and_school_filters_are_tag_independent_and_private(signed, research_team):
    content = deepcopy(example("profile-write.json")["content"])
    content["education"][0]["institution"] = "  The University of New South Wales  "
    content["skills"] = [
        {"id": "sensor", "title": "Quantum sensor calibration", "evidenceText": "Built interferometers in a laboratory."},
        {"id": "denial", "title": "No Audio DSP", "evidenceText": ""},
        {"id": "contradiction", "title": "Audio DSP", "evidenceText": ""},
        {"id": "aspiration", "title": "Haskell", "evidenceText": "I want to learn Haskell."},
    ]
    confirm_profile(signed, content)
    share(signed, ["skills", "education"])
    item = opportunity(research_team)
    client = research_team[0]
    url = f"{OPPORTUNITIES}/{item['id']}/talent-matches"
    result = page(client, url, skill="ＳＥＮＳＯＲ", university="UNSW")
    assert result["total"] == 1 and result["items"][0]["rank"] == 1
    assert page(client, url, skill="interferometers", university="UNSW Sydney")["total"] == 1
    assert page(client, url, skill="audio dsp")["total"] == 0
    assert page(client, url, skill="haskell")["total"] == 0
    assert page(client, url, university="UQ")["total"] == 0
    assert page(client, url, skill="University")["total"] == 0
    share(signed, ["skills"])
    assert page(client, url, university="UNSW")["total"] == 0
    assert page(client, url, skill="sensor")["total"] == 1
    share(signed, ["education"])
    assert page(client, url, skill="sensor")["total"] == 0
    assert page(client, url, university="UNSW")["total"] == 1
    share(signed, [])
    before = page(client, url)
    content["education"][0]["institution"] = "University of Queensland"
    content["skills"][0]["title"] = "Different hidden skill"
    confirm_profile(signed, content)
    assert page(client, url) == before
    assert page(client, url, university="UQ")["total"] == 0


@pytest.mark.parametrize("code", GO8)
def test_each_go8_school_recognises_existing_institution_names(signed, research_team, code):
    content = deepcopy(example("profile-write.json")["content"])
    content["education"][0]["institution"] = GO8[code][1] if len(GO8[code]) > 1 else GO8[code][0]
    confirm_profile(signed, content)
    share(signed, ["education"])
    item = opportunity(research_team)
    url = f"{OPPORTUNITIES}/{item['id']}/talent-matches"
    assert page(research_team[0], url, university=code)["total"] == 1


@pytest.mark.parametrize("query,field", [
    ("skill=", "skill"), ("skill=%20", "skill"), ("skill=a&skill=b", "skill"),
    ("skill=" + "a" * 201, "skill"), ("university=", "university"),
    ("university=MIT", "university"), ("university=UNSW&university=missing", "university"),
    ("university=UNSW&university=USYD", "university"),
    ("university=UNSW&university=UNSW", "university"),
])
def test_invalid_new_talent_filters_are_rejected(research_team, query, field):
    item = opportunity(research_team)
    url = f"{OPPORTUNITIES}/{item['id']}/talent-matches"
    error_field(research_team[0].get(url + "?" + query), field)
