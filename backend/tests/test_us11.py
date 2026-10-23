"""US-11: source-grounded tags and free text through the real document workflow."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from threading import Barrier

import pytest
from sqlalchemy import func, inspect, select

from backend.src.app import create_app
from backend.src.db.models import (Base, ProfileComponentOrigin, PersonalInterestTag,
                                   ProfileTextDetails, ProfilePersonalInterest)
from backend.src.features.documents.suggestions import build_extraction_result
from backend.src.shared.validation import validator
from backend.src.shared.paths import ROOT
from backend.tests.conftest import headers, sign_in
from backend.tests.test_us09_extraction import TAGS, text_docx, text_pdf, upload, process
from backend.tests.test_us04 import make_opportunity, research_team


SOURCE = """Technical skills
Experienced in Python and SQL for data analysis.
Research interests
I want to apply Machine learning to ecological forecasting.
Climate-resilient urban systems; Machine learning
Research experience
Title: Research Assistant
Organisation: Synthetic lab
Description: Evaluated forecasting methods against historical observations.
Research outputs
Type: PROJECT
Title: Forecast benchmark
Description: Compared predictive models and documented the results.
"""


def checked(response, status=200, schema=None):
    assert response.status_code == status, response.json
    if schema:
        validator(schema).validate(response.json)
    return response.json


def profile(client):
    return checked(client.get("/api/v1/me/profile"), schema="Profile")


def save(signed, content, revision):
    client, csrf = signed
    return client.put("/api/v1/me/profile", json={"expectedRevision": revision, "content": content}, headers=headers(csrf))


def apply(signed, document_id, sections, revision):
    client, csrf = signed
    return client.post(f"/api/v1/me/documents/{document_id}/apply", headers=headers(csrf),
                       json={"expectedProfileRevision": revision, "sections": sections})


def tag_count(app):
    with app.extensions["database"].transaction() as db:
        return db.scalar(select(func.count()).select_from(PersonalInterestTag))


def test_tags_in_paragraphs_keep_their_source_and_all_free_descriptions():
    result = build_extraction_result("doc_resume", SOURCE, TAGS)
    validator("Extraction").validate(result)
    sections = result["suggestedSections"]
    assert sections["resumeDescription"] == SOURCE.strip()
    assert [item["title"] for item in sections["skills"]] == ["Experienced in Python and SQL for data analysis."]
    assert all(item["evidenceText"] == "Experienced in Python and SQL for data analysis." for item in sections["skills"])
    assert sections["researchInterests"] == ["interest_ml"]
    assert sections["researchInterestText"] == ("I want to apply Machine learning to ecological forecasting.\n"
                                               "Climate-resilient urban systems; Machine learning")
    assert sections["customInterestTags"] == [{"label": "Climate-resilient urban systems"}]
    assert sections["researchExperience"][0]["description"] == "Evaluated forecasting methods against historical observations."
    assert sections["researchOutputs"][0]["description"] == "Compared predictive models and documented the results."
    assert result["reviewRequired"] is True


def test_text_without_any_vocabulary_match_stays_reviewable():
    result = build_extraction_result("doc_text", "Research interests\nI study ecological forecasting and urban resilience.", TAGS)
    assert result["suggestedSections"]["researchInterestText"] == "I study ecological forecasting and urban resilience."
    assert "researchInterests" not in result["suggestedSections"]
    assert "customInterestTags" not in result["suggestedSections"]
    validator("Extraction").validate(result)


def test_unified_description_retains_unstructured_text_and_reports_truncation():
    source = "Researcher name\nContact: owner@example.test\nUnusual section\n  Built   a useful prototype.\n"
    result = build_extraction_result("doc_unstructured", source, TAGS)
    assert result["suggestedSections"] == {"resumeDescription": "Researcher name\nContact: owner@example.test\nUnusual section\nBuilt a useful prototype."}
    result = build_extraction_result("doc_long_resume", "A" * 21000, TAGS)
    assert len(result["suggestedSections"]["resumeDescription"]) == 20000
    assert any(item["field"] == "resumeDescription" and "shortened" in item["reason"] for item in result["uncertainFields"])
    validator("Extraction").validate(result)


def test_word_boundaries_negations_intentions_and_unrelated_sections():
    result = build_extraction_result("doc_claims", "Skills: No Python; SQL\nWork experience\nPython\nResearch interests\nNo Machine learning", TAGS)
    assert [row["title"] for row in result["suggestedSections"]["skills"]] == ["No Python", "SQL"]
    assert "researchInterests" not in result["suggestedSections"]
    assert "customInterestTags" not in result["suggestedSections"]
    assert "skills" not in build_extraction_result("doc_learning", "Skills: I want to learn Python", TAGS)["suggestedSections"]
    assert [row["title"] for row in build_extraction_result("doc_substring", "Skills: Pythonic; SQLAlchemy", TAGS)["suggestedSections"]["skills"]] == ["Pythonic", "SQLAlchemy"]


def test_chinese_headings_and_long_interest_text_are_preserved_and_flagged():
    result = build_extraction_result("doc_cn", "技能：Python、SQL\n研究兴趣：Machine learning；城市韧性", TAGS)
    assert len(result["suggestedSections"]["skills"]) == 2
    assert result["suggestedSections"]["customInterestTags"] == [{"label": "城市韧性"}]
    result = build_extraction_result("doc_long", "Research interests\n" + "x" * 6000, TAGS)
    assert len(result["suggestedSections"]["researchInterestText"]) == 5000
    assert any(item["field"] == "researchInterestText" and "shortened" in item["reason"] for item in result["uncertainFields"])
    validator("Extraction").validate(result)


@pytest.mark.parametrize("format", ["pdf", "docx"])
def test_real_upload_worker_review_import_reload_and_confirmation(app, signed, tmp_path, format):
    client, csrf = signed
    app.config["DOCUMENT_STORAGE_DIR"] = str(tmp_path / "documents")
    before = profile(client)
    initial = deepcopy(before["content"])
    initial["displayName"] = "Resume owner"
    before = checked(save(signed, initial, before["revision"]))
    content = text_pdf(SOURCE) if format == "pdf" else text_docx(SOURCE)
    document_id = upload(client, csrf, content, "resume." + format)
    process(app)
    sections = checked(client.get(f"/api/v1/me/documents/{document_id}/extraction"), schema="Extraction")["suggestedSections"]
    assert profile(client) == before
    assert tag_count(app) == 0
    saved = checked(apply(signed, document_id, sections, before["revision"]), schema="Profile")
    assert saved["content"]["researchInterestText"] == sections["researchInterestText"]
    assert saved["content"]["resumeDescription"] == sections["resumeDescription"]
    assert saved["content"]["customInterestTags"][0]["label"] == "Climate-resilient urban systems"
    assert saved["content"]["customInterestTags"][0]["id"].startswith("personal_")
    assert saved["confirmation"]["status"] == "UNCONFIRMED"
    for field in ("researchInterestText", "customInterestTags", "resumeDescription"):
        assert {"field": field, "sourceType": "USER_REVIEWED_DOCUMENT", "documentId": document_id} in saved["origins"]
    checked(client.get("/api/v1/me/recommendations"), 409)
    restarted = create_app(dict(app.config))
    try:
        other = restarted.test_client()
        other_csrf = sign_in(other)
        assert profile(other) == saved
        confirmed = checked(other.post("/api/v1/me/profile/confirmation", headers=headers(other_csrf),
                                       json={"expectedRevision": saved["revision"]}), schema="Profile")
        assert confirmed["confirmation"]["status"] == "CONFIRMED"
    finally:
        restarted.extensions["database"].engine.dispose()


def test_partial_review_accepts_rejects_and_clears_each_component_independently(app, signed, tmp_path):
    client, csrf = signed
    app.config["DOCUMENT_STORAGE_DIR"] = str(tmp_path / "documents")
    document_id = upload(client, csrf, text_docx(SOURCE), "resume.docx")
    process(app)
    first = checked(apply(signed, document_id, {"researchInterestText": "Reviewed description",
                    "customInterestTags": [{"label": "Urban resilience"}]}, 0))
    personal = first["content"]["customInterestTags"]
    assert tag_count(app) == 1
    second = checked(apply(signed, document_id, {"researchInterests": ["interest_ml"]}, first["revision"]))
    assert second["content"]["customInterestTags"] == personal
    assert second["content"]["researchInterestText"] == "Reviewed description"
    third = checked(apply(signed, document_id, {"customInterestTags": []}, second["revision"]))
    assert third["content"]["customInterestTags"] == []
    assert third["content"]["researchInterestText"] == "Reviewed description"
    assert third["content"]["researchInterests"] == ["interest_ml"]
    cleared = checked(apply(signed, document_id, {"researchInterestText": ""}, third["revision"]))
    assert cleared["content"]["researchInterestText"] == ""
    assert all(item["label"] != "Climate-resilient urban systems" for item in checked(client.get("/api/v1/tags"))["items"])


def test_normalised_duplicate_shared_resolution_noop_and_legacy_omission(app, signed):
    client, csrf = signed
    content = profile(client)["content"]
    content["displayName"] = "Talent"
    content["researchInterestText"] = "Source-grounded interests"
    content["customInterestTags"] = [{"label": "  Urban   resilience "}, {"label": "URBAN RESILIENCE"},
                                      {"label": "Ｍａｃｈｉｎｅ learning"}]
    first = checked(save(signed, content, 0), schema="Profile")
    assert first["content"]["researchInterests"] == ["interest_ml"]
    assert len(first["content"]["customInterestTags"]) == tag_count(app) == 1
    confirmed = checked(client.post("/api/v1/me/profile/confirmation", headers=headers(csrf),
                                   json={"expectedRevision": first["revision"]}))
    assert checked(save(signed, first["content"], first["revision"])) == confirmed
    legacy = {key: value for key, value in first["content"].items() if key not in ("researchInterestText", "customInterestTags", "resumeDescription")}
    legacy["displayName"] = "Updated name"
    updated = checked(save(signed, legacy, first["revision"]))
    assert updated["content"]["researchInterestText"] == first["content"]["researchInterestText"]
    assert updated["content"]["customInterestTags"] == first["content"]["customInterestTags"]
    assert updated["confirmation"]["status"] == "UNCONFIRMED"


def test_stale_invalid_and_cross_owner_saves_create_no_personal_rows(app, signed):
    client, _ = signed
    content = profile(client)["content"]
    content["customInterestTags"] = [{"label": "Owner private label"}]
    first = checked(save(signed, content, 0))
    stale = deepcopy(content)
    stale["customInterestTags"] = [{"label": "Must not be created"}]
    checked(save(signed, stale, 0), 409)
    invalid = deepcopy(stale)
    invalid["researchInterests"] = ["missing"]
    checked(save(signed, invalid, first["revision"]), 422)
    other = app.test_client()
    other_csrf = sign_in(other, "other@example.test")
    cross = profile(other)["content"]
    cross["customInterestTags"] = first["content"]["customInterestTags"]
    checked(save((other, other_csrf), cross, 0), 422)
    assert tag_count(app) == 1
    assert profile(client) == first
    assert profile(other)["revision"] == 0


@pytest.mark.parametrize("label", [" ", "\u200b", "x" * 101])
def test_invalid_personal_labels_are_atomic(app, signed, label):
    client, _ = signed
    before = profile(client)
    content = deepcopy(before["content"])
    content["customInterestTags"] = [{"label": "Valid first proposal"}, {"label": label}]
    result = checked(save(signed, content, before["revision"]), 422)
    assert result["error"]["fieldErrors"]
    assert profile(client) == before
    assert tag_count(app) == 0


def test_concurrent_duplicate_save_has_one_revision_and_one_personal_tag(app, signed):
    client, _ = signed
    content = profile(client)["content"]
    content["customInterestTags"] = [{"label": "Concurrent label"}]
    sessions = []
    for _ in range(2):
        other = app.test_client()
        sessions.append((other, sign_in(other)))
    barrier = Barrier(2)
    def write(session):
        barrier.wait(timeout=10)
        return save(session, deepcopy(content), 0).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(write, sessions))
    assert sorted(statuses) == [200, 409]
    assert tag_count(app) == 1


@pytest.mark.parametrize("field,value", [
    ("researchInterestText", "Interested in ecological forecasting."),
    ("resumeDescription", "Researcher with an independently reviewed resume description."),
    ("customInterestTags", [{"label": "Ecological forecasting"}]),
    ("researchInterests", ["interest_ml"]),
])
def test_text_and_tags_can_be_used_independently(signed, field, value):
    client, csrf = signed
    content = profile(client)["content"]
    content.update(displayName="Talent", **{field: value})
    saved = checked(save(signed, content, 0))
    confirmed = checked(client.post("/api/v1/me/profile/confirmation", headers=headers(csrf),
                                   json={"expectedRevision": saved["revision"]}))
    assert confirmed["confirmation"]["status"] == "CONFIRMED"


def test_personal_tag_reuse_rename_and_conversion_to_a_shared_tag(app, signed):
    client, _ = signed
    content = profile(client)["content"]
    content["customInterestTags"] = [{"label": "Urban resilience"}]
    first = checked(save(signed, content, 0))
    tag_id = first["content"]["customInterestTags"][0]["id"]
    content = deepcopy(first["content"])
    content["customInterestTags"] = []
    cleared = checked(save(signed, content, first["revision"]))
    content["customInterestTags"] = [{"label": "  URBAN resilience "}]
    reused = checked(save(signed, content, cleared["revision"]))
    assert reused["content"]["customInterestTags"][0]["id"] == tag_id
    content["customInterestTags"] = [{"id": tag_id, "label": "Ecological forecasting"}]
    renamed = checked(save(signed, content, reused["revision"]))
    assert renamed["content"]["customInterestTags"] == [{"id": tag_id, "label": "Ecological forecasting"}]
    content["customInterestTags"] = [{"id": tag_id, "label": "Machine learning"}]
    shared = checked(save(signed, content, renamed["revision"]))
    assert shared["content"]["customInterestTags"] == []
    assert shared["content"]["researchInterests"] == ["interest_ml"]
    assert tag_count(app) == 1


def test_combined_interest_limit_rolls_back_all_proposed_tags(app, signed):
    client, _ = signed
    before = profile(client)
    content = deepcopy(before["content"])
    content["researchInterests"] = ["interest_ml"]
    content["customInterestTags"] = [{"label": f"Personal topic {i}"} for i in range(100)]
    checked(save(signed, content, before["revision"]), 422)
    assert tag_count(app) == 0
    assert profile(client) == before


def test_alias_and_id_cannot_rename_the_same_selected_tag_twice(app, signed):
    client, _ = signed
    content = profile(client)["content"]
    content["customInterestTags"] = [{"label": "Original label"}]
    before = checked(save(signed, content, 0))
    tag_id = before["content"]["customInterestTags"][0]["id"]
    content["customInterestTags"] = [{"label": "Original label"}, {"id": tag_id, "label": "Conflicting rename"}]
    checked(save(signed, content, before["revision"]), 422)
    assert tag_count(app) == 1
    assert profile(client) == before


def test_failed_or_stale_import_creates_no_tags_and_preserves_component_provenance(app, signed, tmp_path):
    client, csrf = signed
    app.config["DOCUMENT_STORAGE_DIR"] = str(tmp_path / "documents")
    document_id = upload(client, csrf, text_docx(SOURCE), "review.docx")
    process(app)
    before = profile(client)
    sections = {"resumeDescription": "Accepted only if the whole request succeeds",
                "customInterestTags": [{"label": "Must roll back"}],
                "skills": [{"tagId": "missing", "claim": "HAS", "evidenceText": "invalid"}]}
    checked(apply(signed, document_id, sections, before["revision"]), 422)
    assert tag_count(app) == 0
    assert profile(client) == before
    checked(apply(signed, document_id, {"customInterestTags": [{"label": "Stale"}]}, before["revision"] + 1), 409)
    assert tag_count(app) == 0
    saved = checked(apply(signed, document_id, {"resumeDescription": "Reviewed resume",
                    "researchInterestText": "Reviewed interests"}, before["revision"]))
    content = deepcopy(saved["content"])
    content["researchInterestText"] = "Manually changed interests"
    edited = checked(save(signed, content, saved["revision"]))
    assert {"field": "researchInterestText", "sourceType": "MANUAL", "documentId": None} in edited["origins"]
    assert {"field": "resumeDescription", "sourceType": "USER_REVIEWED_DOCUMENT", "documentId": document_id} in edited["origins"]


def test_visibility_group_shares_interests_but_never_the_whole_resume(app, signed, research_team):
    client, csrf = signed
    team, _ = research_team
    content = profile(client)["content"]
    content.update(displayName="Talent", resumeDescription="Private contact: private@example.test",
                   researchInterestText="Public reviewed interest description", researchInterests=["interest_ml"],
                   customInterestTags=[{"label": "Urban resilience"}])
    saved = checked(save(signed, content, 0))
    opportunity = make_opportunity(research_team, [{"id": "interest", "kind": "INTEREST", "label": "ML",
                         "importance": "REQUIRED", "tagIds": ["interest_ml"]}])
    url = f"/api/v1/opportunities/{opportunity['id']}/talent-matches"
    def share(fields, consent=True):
        current = checked(client.get("/api/v1/me/privacy"))
        return checked(client.put("/api/v1/me/privacy", headers=headers(csrf), json={
            "expectedRevision": current["revision"], "discoverable": consent, "visibleFields": fields}))
    share(["researchInterests"])
    assert checked(team.get(url))["total"] == 0  # Import/manual edits require explicit confirmation.
    checked(client.post("/api/v1/me/profile/confirmation", headers=headers(csrf),
                        json={"expectedRevision": saved["revision"]}))
    visible = checked(team.get(f"{url}/{saved['talentId']}"), schema="TeamMatch")
    assert set(visible["talent"]["fields"]) == {"researchInterests", "researchInterestText", "customInterestTags"}
    assert visible["talent"]["fields"]["customInterestTags"] == saved["content"]["customInterestTags"]
    assert "private@example.test" not in json.dumps(visible)
    assert "resumeDescription" not in json.dumps(visible)
    assert "documentId" not in json.dumps(visible)
    share([])
    hidden = checked(team.get(f"{url}/{saved['talentId']}"))
    assert hidden["talent"]["fields"] == {}
    assert hidden["summary"]["score"] == 0
    assert hidden["requirements"][0]["status"] == "UNKNOWN"
    share([], False)
    assert checked(team.get(url))["total"] == 0
    checked(team.get(f"{url}/{saved['talentId']}"), 404)
    assert profile(client)["content"]["resumeDescription"] == "Private contact: private@example.test"


def test_additive_upgrade_preserves_old_tables_and_profiles(tmp_path):
    from backend.src.db.database import Database
    from backend.src.db.models import TalentProfile, User
    database = Database(f"sqlite:///{(tmp_path / 'legacy.db').as_posix()}")
    added = {model.__tablename__ for model in (ProfileTextDetails, PersonalInterestTag,
                                              ProfilePersonalInterest, ProfileComponentOrigin)}
    try:
        Base.metadata.create_all(database.engine, tables=[table for table in Base.metadata.sorted_tables if table.name not in added])
        with database.transaction(write=True) as db:
            db.add(User(id="legacy", email="legacy@example.test", display_name="Legacy", role="TALENT", password_hash="preserved"))
            db.flush()
            db.add(TalentProfile(talent_id="legacy_talent", user_id="legacy", display_name="Preserved", revision=7))
        before = inspect(database.engine).get_columns("talent_profiles")
        database.initialise()
        database.initialise()
        after = inspect(database.engine).get_columns("talent_profiles")
        assert [(c['name'],str(c['type']),c['nullable']) for c in after] == [(c['name'],str(c['type']),c['nullable']) for c in before]
        assert added <= set(inspect(database.engine).get_table_names())
        with database.transaction() as db:
            assert db.get(TalentProfile, "legacy_talent").revision == 7
            assert db.get(User, "legacy").password_hash == "preserved"
    finally:
        database.engine.dispose()
