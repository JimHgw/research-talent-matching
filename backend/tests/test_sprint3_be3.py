"""BE-3 profile operations without Flask application/request contexts."""

from copy import deepcopy
import json

from flask import has_app_context, has_request_context
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import object_session

from backend.src.db.models import Base, Document, DocumentExtraction, PersonalInterestTag, User
from backend.src.features.documents.service import apply_reviewed_extraction
from backend.src.features.profile import repository, service
from backend.src.features.profile.serialization import serialize_profile
from backend.src.shared.paths import ROOT
from backend.src.shared.validation import ApiError, validator

OWNER = "talent@example.test"
OTHER = "other@example.test"
DOCUMENT_ID = "doc_be3_direct"


@pytest.fixture
def direct_database(app):
    assert not has_app_context()
    assert not has_request_context()
    return app.extensions["database"]


def user_for(db, email=OWNER):
    return db.scalar(select(User).where(User.email == email))


def read_profile(database, email=OWNER):
    with database.transaction() as db:
        profile = repository.own_profile(db, user_for(db, email))
        result = deepcopy(serialize_profile(profile, repository.load_profile_details(db, profile)))
    validator("Profile").validate(result)
    return result


def snapshot(database):
    with database.transaction() as db:
        return {
            table.name: [dict(row) for row in db.execute(
                select(table).order_by(*table.primary_key.columns)
            ).mappings()]
            for table in Base.metadata.sorted_tables
        }


def save(database, content, revision, email=OWNER, write=True):
    assert not has_app_context()
    assert not has_request_context()
    with database.transaction(write=write) as db:
        return service.save_profile(
            db, user_for(db, email), expected_revision=revision, content=content
        )


def confirm(database, revision, email=OWNER, write=True):
    assert not has_app_context()
    assert not has_request_context()
    with database.transaction(write=write) as db:
        return service.confirm_profile(db, user_for(db, email), expected_revision=revision)


def valid_content(database):
    content = deepcopy(read_profile(database)["content"])
    content.update(
        displayName="BE-3 service owner",
        skills=[{"id": "skill_be3", "title": "Python", "evidenceText": "Reviewed evidence."}],
    )
    return content


def seed_confirmed(database):
    saved = save(database, valid_content(database), 0)
    return confirm(database, saved["revision"])


def ready_document(database):
    extraction = json.loads((ROOT / "docs/api/examples/extraction-ready.json").read_text(encoding="utf-8"))
    extraction["documentId"] = DOCUMENT_ID
    with database.transaction(write=True) as db:
        profile = repository.own_profile(db, user_for(db))
        db.add(Document(
            id=DOCUMENT_ID, talent_id=profile.talent_id, kind="CV", file_name="synthetic.pdf",
            media_type="application/pdf", storage_key="be3-direct-test", size_bytes=128,
            status="READY", error=None,
        ))
        db.flush()
        db.add(DocumentExtraction(document_id=DOCUMENT_ID, result=extraction))


def test_save_confirm_noop_repeat_and_edit_are_stable(direct_database):
    database = direct_database
    content = valid_content(database)
    original = deepcopy(content)
    saved = save(database, content, 0)
    assert content == original
    assert saved["revision"] == 1
    assert saved["confirmation"] == {
        "status": "UNCONFIRMED", "confirmedRevision": None, "confirmedAt": None,
    }
    assert read_profile(database) == saved
    assert {"field": "skills", "sourceType": "MANUAL", "documentId": None} in saved["origins"]

    confirmed = confirm(database, saved["revision"])
    assert confirmed["revision"] == saved["revision"]
    assert confirmed["confirmation"]["confirmedRevision"] == confirmed["revision"]
    assert confirmed["confirmation"]["confirmedAt"] is not None
    before = snapshot(database)
    assert save(database, deepcopy(confirmed["content"]), confirmed["revision"]) == confirmed
    assert confirm(database, confirmed["revision"]) == confirmed
    assert snapshot(database) == before

    edited_content = deepcopy(confirmed["content"])
    edited_content["displayName"] = "Edited owner"
    edited = save(database, edited_content, confirmed["revision"])
    assert edited["revision"] == confirmed["revision"] + 1
    assert edited["confirmation"] == saved["confirmation"]
    assert edited["origins"] == confirmed["origins"]
    assert read_profile(database) == edited
    again = confirm(database, edited["revision"])
    assert again["revision"] == edited["revision"]
    assert again["confirmation"]["confirmedRevision"] == edited["revision"]


@pytest.mark.parametrize("operation", ["save", "confirm"])
def test_stale_operations_preserve_all_database_state(direct_database, operation):
    database = direct_database
    current = seed_confirmed(database)
    content = deepcopy(current["content"])
    content["customInterestTags"] = [{"label": "Must never be created", "description": "Stale"}]
    before = snapshot(database)
    with pytest.raises(ApiError) as raised:
        if operation == "save":
            save(database, content, current["revision"] - 1)
        else:
            confirm(database, current["revision"] - 1)
    assert raised.value.status == 409
    assert raised.value.code == "REVISION_CONFLICT"
    assert raised.value.revision == current["revision"]
    assert snapshot(database) == before


@pytest.mark.parametrize("case,field", [
    ("blank", "content.displayName"), ("whitespace", "content.displayName"), ("empty", "content"),
])
def test_confirmation_requires_a_name_and_confirmable_content(direct_database, case, field):
    database = direct_database
    content = valid_content(database)
    if case == "empty":
        content["skills"] = []
    else:
        content["displayName"] = "" if case == "blank" else "   "
    saved = save(database, content, 0)
    before = snapshot(database)
    with pytest.raises(ApiError) as raised:
        confirm(database, saved["revision"])
    assert raised.value.status == 422
    assert raised.value.code == "VALIDATION_ERROR"
    assert raised.value.fields[0]["field"] == field
    assert snapshot(database) == before


@pytest.mark.parametrize("field,empty", [
    ("researchInterestText", ""), ("resumeDescription", ""), ("customInterestTags", []),
])
def test_legacy_omission_preserves_components_and_explicit_empty_clears(direct_database, field, empty):
    database = direct_database
    content = valid_content(database)
    content.update(
        researchInterestText="Keep the reviewed interest text.",
        resumeDescription="Keep the private resume.",
        customInterestTags=[{"label": "BE3 private topic", "description": "Owner detail."}],
    )
    first = save(database, content, 0)
    confirmed = confirm(database, first["revision"])
    legacy = deepcopy(confirmed["content"])
    for name in ("researchInterestText", "resumeDescription", "customInterestTags"):
        del legacy[name]
    legacy["displayName"] = "Legacy editor"
    original = deepcopy(legacy)
    preserved = save(database, legacy, confirmed["revision"])
    assert legacy == original
    for name in ("researchInterestText", "resumeDescription", "customInterestTags"):
        assert preserved["content"][name] == confirmed["content"][name]
    assert preserved["origins"] == confirmed["origins"]

    cleared_content = deepcopy(preserved["content"])
    cleared_content[field] = deepcopy(empty)
    cleared = save(database, cleared_content, preserved["revision"])
    assert cleared["revision"] == preserved["revision"] + 1
    assert cleared["content"][field] == empty
    for name, value in preserved["content"].items():
        if name != field:
            assert cleared["content"][name] == value
    assert read_profile(database) == cleared


def test_personal_tags_normalize_deduplicate_and_resolve_shared_labels(direct_database):
    database = direct_database
    content = valid_content(database)
    content["customInterestTags"] = [
        {"label": "  Urban   resilience "},
        {"label": "URBAN resilience", "description": "Climate adaptation."},
        {"label": "\uff2d\uff41\uff43\uff48\uff49\uff4e\uff45 learning"},
    ]
    original = deepcopy(content)
    shared_before = snapshot(database)["tags"]
    saved = save(database, content, 0)
    assert content == original
    assert saved["content"]["researchInterests"] == ["interest_ml"]
    personal, = saved["content"]["customInterestTags"]
    assert personal["label"] == "Urban resilience"
    assert personal["description"] == "Climate adaptation."
    assert personal["id"].startswith("personal_")
    confirmed = confirm(database, saved["revision"])
    before = snapshot(database)
    assert save(database, content, confirmed["revision"]) == confirmed
    assert snapshot(database) == before
    assert snapshot(database)["tags"] == shared_before


def test_other_owners_personal_tag_cannot_be_selected_or_changed(direct_database):
    database = direct_database
    content = valid_content(database)
    content["customInterestTags"] = [{"label": "Owner label", "description": "Owner description."}]
    saved = save(database, content, 0)
    other = read_profile(database, OTHER)
    submitted = deepcopy(other["content"])
    submitted["customInterestTags"] = [
        {**saved["content"]["customInterestTags"][0], "description": "Attempted replacement."}
    ]
    before = snapshot(database)
    with pytest.raises(ApiError) as raised:
        save(database, submitted, other["revision"], email=OTHER)
    assert raised.value.status == 422
    assert raised.value.fields[0]["field"] == "content.customInterestTags.0.id"
    assert snapshot(database) == before


@pytest.mark.parametrize("case", ["unknown-shared", "duplicate-record", "combined-limit", "invalid-label"])
def test_invalid_content_creates_no_tags_and_changes_no_records(direct_database, case):
    database = direct_database
    current = seed_confirmed(database)
    content = deepcopy(current["content"])
    content["customInterestTags"] = [{"label": "Valid first proposal"}]
    if case == "unknown-shared":
        content["researchInterests"] = ["missing_interest"]
    elif case == "duplicate-record":
        sample = json.loads((ROOT / "docs/api/examples/profile-write.json").read_text(encoding="utf-8"))
        row = sample["content"]["education"][0]
        content["education"] = [deepcopy(row), deepcopy(row)]
    elif case == "combined-limit":
        content["researchInterests"] = ["interest_ml"]
        content["customInterestTags"] = [{"label": f"BE3 limit topic {i}"} for i in range(100)]
    else:
        content["customInterestTags"].append({"label": "\u200b"})
    before = snapshot(database)
    with pytest.raises(ApiError) as raised:
        save(database, content, current["revision"])
    assert raised.value.status == 422
    assert raised.value.code == "VALIDATION_ERROR"
    assert snapshot(database) == before


@pytest.mark.parametrize("operation", ["save", "confirm", "import"])
def test_direct_operations_require_the_callers_write_lock(direct_database, operation):
    database = direct_database
    content = valid_content(database)
    if operation == "import":
        ready_document(database)
    before = snapshot(database)
    with pytest.raises(RuntimeError, match="write=True"):
        if operation == "save":
            save(database, content, 0, write=False)
        elif operation == "confirm":
            confirm(database, 0, write=False)
        else:
            with database.transaction() as db:
                apply_reviewed_extraction(
                    db, user_for(db), DOCUMENT_ID,
                    expected_profile_revision=0, sections={"skills": []},
                )
    assert snapshot(database) == before


@pytest.mark.parametrize("stage", ["tag-resolution", "content-write", "serialization"])
def test_save_failure_after_flushed_writes_rolls_back_everything(direct_database, monkeypatch, stage):
    database = direct_database
    current = seed_confirmed(database)
    content = deepcopy(current["content"])
    content.update(
        displayName="Must roll back",
        resumeDescription="Must roll back this text.",
        customInterestTags=[{"label": "BE3 rollback tag", "description": "Must roll back."}],
    )
    before = snapshot(database)
    fired = []

    def fail(db):
        db.flush()
        assert db.scalar(select(func.count()).select_from(PersonalInterestTag)) == 1
        fired.append(True)
        raise RuntimeError("BE3 failure after flushed writes")

    if stage == "serialization":
        original = service.serialize_profile

        def wrapped(profile, details):
            if profile.revision == current["revision"] + 1:
                fail(object_session(profile))
            return original(profile, details)
        monkeypatch.setattr(service, "serialize_profile", wrapped)
    else:
        name = "resolve_profile_personal_tags" if stage == "tag-resolution" else "save_profile_content"
        original = getattr(repository, name)

        def wrapped(*args, **kwargs):
            original(*args, **kwargs)
            fail(args[0])
        monkeypatch.setattr(repository, name, wrapped)
    with pytest.raises(RuntimeError, match="BE3 failure after flushed writes"):
        save(database, content, current["revision"])
    assert fired == [True]
    assert snapshot(database) == before


def test_confirmation_serialization_failure_rolls_back_the_flushed_confirmation(direct_database, monkeypatch):
    database = direct_database
    saved = save(database, valid_content(database), 0)
    before = snapshot(database)
    original = service.serialize_profile
    fired = []

    def wrapped(profile, details):
        if profile.confirmation_status == "CONFIRMED":
            assert profile.confirmed_revision == saved["revision"]
            object_session(profile).flush()
            fired.append(True)
            raise RuntimeError("BE3 failed confirmation serialization")
        return original(profile, details)
    monkeypatch.setattr(service, "serialize_profile", wrapped)
    with pytest.raises(RuntimeError, match="BE3 failed confirmation serialization"):
        confirm(database, saved["revision"])
    assert fired == [True]
    assert snapshot(database) == before


def test_manual_noop_and_identical_import_have_different_revision_rules(direct_database):
    database = direct_database
    current = seed_confirmed(database)
    ready_document(database)
    assert save(database, deepcopy(current["content"]), current["revision"]) == current
    sections = {"skills": deepcopy(current["content"]["skills"])}

    def apply(revision):
        assert not has_app_context()
        assert not has_request_context()
        with database.transaction(write=True) as db:
            return apply_reviewed_extraction(
                db, user_for(db), DOCUMENT_ID,
                expected_profile_revision=revision, sections=sections,
            )
    first = apply(current["revision"])
    assert first["revision"] == current["revision"] + 1
    assert first["confirmation"]["status"] == "UNCONFIRMED"
    assert first["content"] == current["content"]
    before = snapshot(database)
    with pytest.raises(ApiError) as raised:
        apply(current["revision"])
    assert raised.value.code == "REVISION_CONFLICT"
    assert raised.value.revision == first["revision"]
    assert snapshot(database) == before
    second = apply(first["revision"])
    assert second["revision"] == first["revision"] + 1
    assert second["content"] == first["content"]
    assert save(database, deepcopy(second["content"]), second["revision"]) == second

