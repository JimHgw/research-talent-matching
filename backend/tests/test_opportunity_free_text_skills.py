"""Real HTTP/DB coverage for tag-independent opportunity skills."""

from copy import deepcopy

import pytest
from sqlalchemy import delete, func, select

from backend.src.db.models import OpportunitySkillDetails, RequirementTag, Tag, TagDisciplineGroup
from conftest import headers
from test_us04 import (OPPORTUNITIES, checked, confirm_profile, example,
                       make_opportunity, research_team)
from test_us05 import share


def requirement(titles, id="req_free"):
    return {"id": id, "kind": "SKILL", "label": "Research skills", "importance": "REQUIRED",
            "skillTitles": titles, "tagIds": []}


def test_arbitrary_skill_names_persist_publish_and_match_both_directions(app, signed, research_team):
    with app.extensions["database"].transaction(write=True) as db:
        skill_ids = select(Tag.id).where(Tag.kind == "SKILL")
        db.execute(delete(TagDisciplineGroup).where(TagDisciplineGroup.tag_id.in_(skill_ids)))
        db.execute(delete(Tag).where(Tag.kind == "SKILL"))
    content = example("profile-write.json")["content"]
    content["skills"] = [
        {"id": "record_crispr", "title": "ＣＲＩＳＰＲ experimental design", "evidenceText": "Designed a gene-editing experiment."},
        {"id": "record_modelling", "title": "Financial modelling", "evidenceText": "Built cash-flow forecasts."},
        {"id": "record_r_gap", "title": "No R", "evidenceText": "No experience with R."},
    ]
    profile = confirm_profile(signed, content)
    opportunity = make_opportunity(research_team, requirements=[
        requirement(["crispr experimental design"]),
        requirement(["Financial modelling", "SQL"], "req_partial"),
        requirement(["R"], "req_gap"), requirement(["Python"], "req_unknown")])
    client, _ = signed
    detail = checked(client.get(f"/api/v1/me/opportunity-matches/{opportunity['id']}"), "OwnerMatch")
    assert [r["status"] for r in detail["requirements"]] == ["MATCHED", "PARTIAL", "GAP", "UNKNOWN"]
    assert detail["requirements"][0]["evidence"][0]["recordId"] == "record_crispr"
    assert detail["summary"]["algorithmVersion"] == "skill-title-interest-tags-v2"
    assert detail["summary"]["score"] == 37.5
    readback = checked(client.get(f"{OPPORTUNITIES}/{opportunity['id']}"), "Opportunity")
    assert readback["content"] == opportunity["content"]
    with app.extensions["database"].transaction() as db:
        assert db.scalar(select(func.count()).select_from(RequirementTag).where(RequirementTag.opportunity_id == opportunity["id"])) == 0
        assert db.scalar(select(func.count()).select_from(OpportunitySkillDetails).where(OpportunitySkillDetails.opportunity_id == opportunity["id"])) == 4
    share(signed, ["skills"])
    team, _ = research_team
    url = f"{OPPORTUNITIES}/{opportunity['id']}/talent-matches/{profile['talentId']}"
    visible = checked(team.get(url), "TeamMatch")
    assert [r["status"] for r in visible["requirements"]] == ["MATCHED", "PARTIAL", "GAP", "UNKNOWN"]
    share(signed, [])
    hidden = checked(team.get(url), "TeamMatch")
    assert all(r["status"] == "UNKNOWN" and not r["evidence"] for r in hidden["requirements"])
    assert "record_crispr" not in str(hidden)


@pytest.mark.parametrize("patch", [
    {"skillTitles": []}, {"skillTitles": ["  "]}, {"skillTitles": ["Python", "ＰＹＴＨＯＮ"]},
    {"skillTitles": ["A\u200bB"]}, {"skillTitles": ["x" * 351]},
    {"skillTitles": [str(i) for i in range(21)]}, {"tagIds": ["skill_python"]}, {"kind": "INTEREST"},
])
def test_invalid_or_mixed_skill_criteria_are_atomic(app, research_team, patch):
    opportunity = make_opportunity(research_team, [requirement(["Uncatalogued skill"])])
    team, csrf = research_team
    content = deepcopy(opportunity["content"])
    content["requirements"][0].update(patch)
    response = team.put(f"{OPPORTUNITIES}/{opportunity['id']}", headers=headers(csrf),
                        json={"expectedRevision": opportunity["revision"], "content": content})
    checked(response, "Error", 422)
    assert checked(team.get(f"{OPPORTUNITIES}/{opportunity['id']}"), "Opportunity") == opportunity


def test_skill_requirement_replacement_and_stale_edits_preserve_records(research_team):
    opportunity = make_opportunity(research_team, [requirement(["Python", "SQL"])])
    team, csrf = research_team
    url = f"{OPPORTUNITIES}/{opportunity['id']}"
    content = deepcopy(opportunity["content"])
    content["requirements"] = [requirement(["Financial modelling"])]
    updated = checked(team.put(url, headers=headers(csrf), json={"expectedRevision": opportunity["revision"], "content": content}), "Opportunity")
    assert updated["revision"] == opportunity["revision"] + 1
    assert checked(team.put(url, headers=headers(csrf), json={"expectedRevision": updated["revision"], "content": content}), "Opportunity") == updated
    checked(team.put(url, headers=headers(csrf), json={"expectedRevision": opportunity["revision"], "content": opportunity["content"]}), "Error", 409)
    content["requirements"] = [{"id": "interest", "kind": "INTEREST", "label": "ML", "importance": "PREFERRED", "tagIds": ["interest_ml"]}]
    converted = checked(team.put(url, headers=headers(csrf), json={"expectedRevision": updated["revision"], "content": content}), "Opportunity")
    assert converted["content"] == content


def test_additive_upgrade_preserves_legacy_opportunities(app, research_team):
    legacy = make_opportunity(research_team)
    database = app.extensions["database"]
    # Simulate the old installation's missing companion table in this test DB.
    OpportunitySkillDetails.__table__.drop(database.engine)
    database.initialise()
    team, csrf = research_team
    url = f"{OPPORTUNITIES}/{legacy['id']}"
    assert checked(team.get(url), "Opportunity") == legacy
    content = deepcopy(legacy["content"])
    content["requirements"][0] = requirement(["Custom laboratory method"], content["requirements"][0]["id"])
    saved = checked(team.put(url, headers=headers(csrf), json={
        "expectedRevision": legacy["revision"], "content": content}), "Opportunity")
    assert saved["content"] == content
    assert saved["revision"] == legacy["revision"] + 1
