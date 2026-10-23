"""Skill titles/evidence across disciplines, legacy reads and privacy-safe matching."""

from copy import deepcopy

import pytest
from sqlalchemy import select

from backend.src.app import create_app
from backend.src.db.models import (Document, DocumentExtraction, ProfileOrigin, ProfileSkill,
                                   ProfileSkillDetails, TalentProfile, utcnow)
from backend.src.features.documents.suggestions import build_extraction_result
from backend.src.shared.validation import validator
from backend.tests.conftest import headers, sign_in
from backend.tests.test_us04 import make_opportunity, research_team
from backend.tests.test_us09_extraction import process, text_docx, text_pdf, upload
from backend.tests.test_us11 import checked, profile, save, apply


def skill(title, evidence="Evidence from a project.", id="free_skill_1"):
    return {"id": id, "title": title, "evidenceText": evidence}


def test_extraction_does_not_need_a_skill_vocabulary_for_either_discipline():
    source = """Skills
Financial modelling: Built a cash-flow forecast.
CRISPR: Designed an experimental protocol.
Excel; COBOL; 访谈分析
"""
    result = build_extraction_result("doc_free", source, [])
    validator("Extraction").validate(result)
    items = result["suggestedSections"]["skills"]
    assert [item["title"] for item in items] == ["Financial modelling", "CRISPR", "Excel", "COBOL", "访谈分析"]
    assert items[0]["evidenceText"] == "Built a cash-flow forecast."
    assert all(set(item) == {"id", "title", "evidenceText"} for item in items)
    assert result == build_extraction_result("doc_free", source, [{"id": "unused", "label": "Unused", "kind": "SKILL"}])


def test_labelled_skill_blocks_keep_the_title_and_evidence_separate():
    result = build_extraction_result("doc_blocks", """Skills
Title: Financial modelling
Supporting evidence: Forecasted revenue and costs.

Title: Qualitative coding
Supporting evidence: Coded interview transcripts.
""", [])
    assert [(x["title"], x["evidenceText"]) for x in result["suggestedSections"]["skills"]] == [
        ("Financial modelling", "Forecasted revenue and costs."),
        ("Qualitative coding", "Coded interview transcripts.")]


@pytest.mark.parametrize("discipline,title", [("STEM", "CRISPR experimental design"), ("BUSINESS", "Financial modelling")])
def test_free_skill_save_reload_noop_and_edit_require_reconfirmation(app, signed, discipline, title):
    client, csrf = signed
    content = profile(client)["content"]
    content.update(displayName="Skill owner", disciplineGroup=discipline, skills=[skill(title)])
    saved = checked(save(signed, content, 0), schema="Profile")
    assert saved["content"]["skills"] == [skill(title)]
    confirmed = checked(client.post("/api/v1/me/profile/confirmation", headers=headers(csrf),
                                    json={"expectedRevision": saved["revision"]}))
    assert checked(save(signed, confirmed["content"], confirmed["revision"])) == confirmed
    content["skills"][0]["evidenceText"] = "Updated project evidence."
    edited = checked(save(signed, content, confirmed["revision"]))
    assert edited["confirmation"]["status"] == "UNCONFIRMED"
    restarted = create_app(dict(app.config))
    try:
        reader = restarted.test_client()
        sign_in(reader)
        assert profile(reader) == edited
    finally:
        restarted.extensions["database"].engine.dispose()


@pytest.mark.parametrize("format", ["pdf", "docx"])
def test_actual_document_free_skill_review_edit_partial_import(app, signed, tmp_path, format):
    client, csrf = signed
    app.config["DOCUMENT_STORAGE_DIR"] = str(tmp_path / "documents")
    source = "Skills\nFinancial modelling: Built a valuation model.\nCRISPR: Analysed laboratory results."
    document_id = upload(client, csrf, text_pdf(source) if format == "pdf" else text_docx(source), "skills." + format)
    before = profile(client)
    process(app)
    extracted = checked(client.get(f"/api/v1/me/documents/{document_id}/extraction"), schema="Extraction")
    items = extracted["suggestedSections"]["skills"]
    items[0]["title"] = "DCF valuation"
    items[0]["evidenceText"] = "Reviewed valuation evidence."
    saved = checked(apply(signed, document_id, {"skills": items[:1]}, before["revision"]), schema="Profile")
    assert saved["content"]["skills"] == items[:1]
    assert saved["content"]["resumeDescription"] == before["content"]["resumeDescription"]
    assert {"field": "skills", "sourceType": "USER_REVIEWED_DOCUMENT", "documentId": document_id} in saved["origins"]
    assert saved["confirmation"]["status"] == "UNCONFIRMED"


def test_legacy_skills_upgrade_without_loss_or_silent_profile_changes(app, signed):
    client, _ = signed
    owner = profile(client)["talentId"]
    database = app.extensions["database"]
    ProfileSkillDetails.__table__.drop(database.engine)
    with database.transaction(write=True) as db:
        row = db.get(TalentProfile, owner)
        row.confirmation_status, row.confirmed_revision, row.confirmed_at = "CONFIRMED", row.revision, utcnow()
        db.add_all([ProfileSkill(talent_id=owner, tag_id="skill_python", claim="HAS", evidence_text="Old evidence.", position=0),
                    ProfileSkill(talent_id=owner, tag_id="skill_sql", claim="DOES_NOT_HAVE", evidence_text="Not used yet.", position=1)])
    assert app.test_cli_runner().invoke(args=["init-db"]).exit_code == 0
    upgraded = profile(client)
    assert [x["title"] for x in upgraded["content"]["skills"]] == ["Python", "No SQL"]
    assert [x["evidenceText"] for x in upgraded["content"]["skills"]] == ["Old evidence.", "Not used yet."]
    assert upgraded["revision"] == 0 and upgraded["confirmation"]["status"] == "CONFIRMED"
    assert profile(client) == upgraded
    content = deepcopy(upgraded["content"])
    content["skills"] = []
    cleared = checked(save(signed, content, 0))
    assert profile(client)["content"]["skills"] == []
    assert cleared["confirmation"]["status"] == "UNCONFIRMED"
    with database.transaction() as db:
        assert db.get(ProfileSkillDetails, owner).skills == []
        assert len(list(db.scalars(select(ProfileSkill).where(ProfileSkill.talent_id == owner)))) == 2


def test_old_ready_extractions_are_adapted_without_overwriting_original_json(app, signed):
    client, _ = signed
    owner = profile(client)["talentId"]
    old = {"documentId": "doc_old", "status": "READY", "reviewRequired": True,
           "suggestedSections": {"skills": [{"tagId": "skill_python", "claim": "HAS", "evidenceText": "Original PDF evidence."}]},
           "uncertainFields": [], "warnings": ["Review all suggestions before saving."]}
    with app.extensions["database"].transaction(write=True) as db:
        db.add(Document(id="doc_old", talent_id=owner, kind="CV", file_name="old.pdf", media_type="application/pdf",
                        storage_key="old-skills", status="READY", size_bytes=10))
        db.flush()
        db.add(DocumentExtraction(document_id="doc_old", result=old))
    result = checked(client.get("/api/v1/me/documents/doc_old/extraction"), schema="Extraction")
    item, = result["suggestedSections"]["skills"]
    assert item["title"] == "Python" and item["evidenceText"] == "Original PDF evidence."
    assert "tagId" not in item and "claim" not in item
    assert checked(apply(signed, "doc_old", {"skills": [item]}, 0))["content"]["skills"] == [item]
    with app.extensions["database"].transaction() as db:
        assert db.get(DocumentExtraction, "doc_old").result == old


@pytest.mark.parametrize("title", ["", " \n ", "\u200b", "x" * 351])
def test_invalid_titles_do_not_partially_save(app, signed, title):
    client, _ = signed
    before = profile(client)
    content = deepcopy(before["content"])
    content["skills"] = [skill("Valid first item"), skill(title, id="second")]
    checked(save(signed, content, before["revision"]), 422)
    assert profile(client) == before
    with app.extensions["database"].transaction() as db:
        assert db.get(ProfileSkillDetails, before["talentId"]) is None


def test_free_skill_matching_uses_titles_and_record_ids_and_respects_privacy(app, signed, research_team):
    client, csrf = signed
    content = profile(client)["content"]
    content.update(displayName="Free skill owner", disciplineGroup="BUSINESS", skills=[
        skill("Ｐｙｔｈｏｎ", id="my_python_record"), skill("SQLAlchemy", id="not_sql"), skill("No R", id="explicit_r_gap")])
    saved = checked(save(signed, content, 0))
    checked(client.post("/api/v1/me/profile/confirmation", headers=headers(csrf), json={"expectedRevision": saved["revision"]}))
    opportunity = make_opportunity(research_team, requirements=[
        {"id": "req_" + name, "label": name, "kind": "SKILL", "importance": "REQUIRED", "tagIds": ["skill_" + name]}
        for name in ("python", "sql", "r")])
    own = checked(client.get(f"/api/v1/me/opportunity-matches/{opportunity['id']}"))
    assert [r["status"] for r in own["requirements"]] == ["MATCHED", "UNKNOWN", "GAP"]
    assert own["requirements"][0]["evidence"][0]["recordId"] == "my_python_record"
    checked(client.put("/api/v1/me/privacy", headers=headers(csrf), json={"expectedRevision": 0, "discoverable": True, "visibleFields": ["skills"]}))
    team, _ = research_team
    endpoint = f"/api/v1/opportunities/{opportunity['id']}/talent-matches/{saved['talentId']}"
    shared = checked(team.get(endpoint), schema="TeamMatch")
    assert shared["talent"]["fields"]["skills"] == content["skills"]
    assert shared["requirements"][0]["evidence"][0]["recordId"] == "my_python_record"
    checked(client.put("/api/v1/me/privacy", headers=headers(csrf), json={"expectedRevision": 1, "discoverable": True, "visibleFields": []}))
    hidden = checked(team.get(endpoint), schema="TeamMatch")
    assert all(r["status"] == "UNKNOWN" for r in hidden["requirements"])
    assert "skills" not in hidden["talent"]["fields"]
    assert "my_python_record" not in str(hidden) and "Evidence from a project" not in str(hidden)
