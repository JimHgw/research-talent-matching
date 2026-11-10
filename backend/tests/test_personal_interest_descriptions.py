"""Personal-interest descriptions round-trip through saves, reviews and legacy upgrades."""

from copy import deepcopy

import pytest
from sqlalchemy import inspect, select

from backend.src.app import create_app
from backend.src.db.models import PersonalInterestTagDetails, TalentProfile, utcnow
from backend.tests.conftest import headers, sign_in
from backend.tests.test_us09_extraction import process, text_docx, upload
from backend.tests.test_us11 import apply, checked, profile, save, tag_count


@pytest.mark.parametrize("description", ["Predicting ecosystem changes.", "\U0001f9ea" * 5000],
                         ids=["plain", "unicode-limit"])
def test_description_save_reload_noop_edit_clear_and_restart(app, signed, description):
    client, csrf = signed
    before = profile(client)
    content = deepcopy(before["content"])
    content.update(displayName="Interest owner", customInterestTags=[
        {"label": "Ecological forecasting", "description": description}])
    saved = checked(save(signed, content, before["revision"]), schema="Profile")
    tag, = saved["content"]["customInterestTags"]
    assert tag["description"] == description
    assert profile(client) == saved
    confirmed = checked(client.post("/api/v1/me/profile/confirmation", headers=headers(csrf),
                                    json={"expectedRevision": saved["revision"]}))
    assert checked(save(signed, confirmed["content"], confirmed["revision"])) == confirmed

    content = deepcopy(confirmed["content"])
    content["customInterestTags"][0]["description"] = "Reviewed ecological research."
    edited = checked(save(signed, content, confirmed["revision"]), schema="Profile")
    assert edited["revision"] == confirmed["revision"] + 1
    assert edited["confirmation"]["status"] == "UNCONFIRMED"
    assert {"field": "customInterestTags", "sourceType": "MANUAL", "documentId": None} in edited["origins"]
    restarted = create_app(dict(app.config))
    try:
        reader = restarted.test_client()
        sign_in(reader)
        assert profile(reader) == edited
    finally:
        restarted.extensions["database"].engine.dispose()

    content["customInterestTags"][0]["description"] = ""
    cleared = checked(save(signed, content, edited["revision"]), schema="Profile")
    assert cleared["content"]["customInterestTags"] == [{**tag, "description": ""}]
    assert profile(client) == cleared


def test_legacy_label_only_entries_and_description_omission_remain_compatible(signed):
    client, _ = signed
    content = profile(client)["content"]
    content["customInterestTags"] = [{"label": "Urban resilience"}]
    legacy = checked(save(signed, content, 0), schema="Profile")
    tag, = legacy["content"]["customInterestTags"]
    assert set(tag) == {"id", "label"}
    content = deepcopy(legacy["content"])
    content["customInterestTags"][0]["description"] = "Climate adaptation research."
    described = checked(save(signed, content, legacy["revision"]))
    content = deepcopy(described["content"])
    del content["customInterestTags"][0]["description"]
    assert checked(save(signed, content, described["revision"])) == described
    content["customInterestTags"][0]["label"] = "Resilient cities"
    renamed = checked(save(signed, content, described["revision"]))
    assert renamed["content"]["customInterestTags"] == [
        {**tag, "label": "Resilient cities", "description": "Climate adaptation research."}]


def test_review_import_keeps_description_and_omitted_components(signed, app, tmp_path):
    client, csrf = signed
    app.config["DOCUMENT_STORAGE_DIR"] = str(tmp_path / "documents")
    content = profile(client)["content"]
    content.update(researchInterests=["interest_ml"], researchInterestText="Preserve this interest text.")
    before = checked(save(signed, content, 0))
    document_id = upload(client, csrf, text_docx("Research interests\nUrban resilience"), "interests.docx")
    process(app)
    saved = checked(apply(signed, document_id, {"customInterestTags": [
        {"label": "Urban resilience", "description": "Reviewed climate adaptation interests."}]}, before["revision"]),
        schema="Profile")
    tag, = saved["content"]["customInterestTags"]
    assert tag["description"] == "Reviewed climate adaptation interests."
    assert profile(client) == saved
    assert saved["content"]["researchInterests"] == before["content"]["researchInterests"]
    assert saved["content"]["researchInterestText"] == before["content"]["researchInterestText"]
    assert {"field": "customInterestTags", "sourceType": "USER_REVIEWED_DOCUMENT", "documentId": document_id} in saved["origins"]
    invalid_sections = {"customInterestTags": [{**tag, "description": "Must roll back."}],
                        "researchInterests": ["missing_interest"]}
    checked(apply(signed, document_id, invalid_sections, saved["revision"]), 422)
    assert profile(client) == saved


def test_shared_label_resolution_does_not_discard_personal_description(signed):
    client, _ = signed
    content = profile(client)["content"]
    content["customInterestTags"] = [{"label": "Machine learning", "description": "Applied to ecology."}]
    saved = checked(save(signed, content, 0), schema="Profile")
    tag, = saved["content"]["customInterestTags"]
    assert tag["description"] == "Applied to ecology."
    assert saved["content"]["researchInterests"] == ["interest_ml"]
    assert profile(client) == saved
    content = deepcopy(saved["content"])
    del content["customInterestTags"][0]["description"]
    assert checked(save(signed, content, saved["revision"])) == saved


def test_duplicate_labels_merge_an_omitted_description_but_reject_conflicting_descriptions(signed, app):
    client, _ = signed
    content = profile(client)["content"]
    content["customInterestTags"] = [{"label": "Urban resilience"},
                                     {"label": "  URBAN resilience ", "description": "Climate adaptation."}]
    saved = checked(save(signed, content, 0))
    tag, = saved["content"]["customInterestTags"]
    assert tag["description"] == "Climate adaptation."
    assert tag_count(app) == 1
    content["customInterestTags"][0]["description"] = "Conflicting text."
    checked(save(signed, content, saved["revision"]), 422)
    assert profile(client) == saved
    assert tag_count(app) == 1


@pytest.mark.parametrize("description", [None, 42, "x" * 5001], ids=["null", "number", "too-long"])
def test_invalid_descriptions_are_rejected_without_partial_writes(signed, app, description):
    client, _ = signed
    before = profile(client)
    content = deepcopy(before["content"])
    content["customInterestTags"] = [{"label": "Valid", "description": "Valid description."},
                                     {"label": "Invalid", "description": description}]
    checked(save(signed, content, before["revision"]), 422)
    assert profile(client) == before
    assert tag_count(app) == 0
    with app.extensions["database"].transaction() as db:
        assert list(db.scalars(select(PersonalInterestTagDetails))) == []


def test_description_changes_check_revision_and_tag_ownership(app, signed):
    client, _ = signed
    content = profile(client)["content"]
    content["customInterestTags"] = [{"label": "Urban resilience", "description": "Owner description."}]
    saved = checked(save(signed, content, 0))
    content = deepcopy(saved["content"])
    content["customInterestTags"][0]["description"] = "Must not overwrite."
    checked(save(signed, content, 0), 409)
    other = app.test_client()
    other_csrf = sign_in(other, "other@example.test")
    other_content = profile(other)["content"]
    other_content["customInterestTags"] = content["customInterestTags"]
    checked(save((other, other_csrf), other_content, 0), 422)
    assert profile(client) == saved
    assert profile(other)["revision"] == 0


def test_existing_catalogue_upgrades_without_changing_profile_or_confirmation(app, signed):
    client, _ = signed
    content = profile(client)["content"]
    content["customInterestTags"] = [{"label": "Legacy topic"}]
    saved = checked(save(signed, content, 0))
    database = app.extensions["database"]
    with database.transaction(write=True) as db:
        owner = db.get(TalentProfile, saved["talentId"])
        owner.confirmation_status, owner.confirmed_revision, owner.confirmed_at = "CONFIRMED", owner.revision, utcnow()
    before = profile(client)
    columns = inspect(database.engine).get_columns("personal_interest_tags")
    PersonalInterestTagDetails.__table__.drop(database.engine)
    for _ in range(2):
        assert app.test_cli_runner().invoke(args=["init-db"]).exit_code == 0
    after = inspect(database.engine).get_columns("personal_interest_tags")
    assert [(col["name"], str(col["type"]), col["nullable"]) for col in after] == [
        (col["name"], str(col["type"]), col["nullable"]) for col in columns]
    assert profile(client) == before
    content = deepcopy(before["content"])
    content["customInterestTags"][0]["description"] = "Added after upgrading."
    updated = checked(save(signed, content, before["revision"]), schema="Profile")
    assert updated["content"]["customInterestTags"][0]["id"] == saved["content"]["customInterestTags"][0]["id"]
    assert updated["confirmation"]["status"] == "UNCONFIRMED"
