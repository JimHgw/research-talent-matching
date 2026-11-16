"""BE-2 service acceptance without HTTP requests."""

from copy import deepcopy
import json

from flask import has_request_context
import pytest
from sqlalchemy import func, select

from backend.src.db.interests import set_profile_text
from backend.src.db.models import (
    Document,
    DocumentExtraction,
    PersonalInterestTag,
    PersonalInterestTagDetails,
    ProfileComponentOrigin,
    ProfileOrigin,
    ProfilePersonalInterest,
    User,
    utcnow,
)
from backend.src.db.skills import replace_skills
from backend.src.features.documents import repository
from backend.src.features.documents.service import apply_reviewed_extraction
from backend.src.features.profile.repository import (
    load_profile_details,
    own_profile,
)
from backend.src.features.profile.serialization import serialize_profile
from backend.src.shared.paths import ROOT
from backend.src.shared.validation import ApiError, validator


OWNER = "talent@example.test"
DOCUMENT_ID = "doc_be2_direct"
REVISION = 3


def user_for(db, email=OWNER):
    return db.scalar(select(User).where(User.email == email))


def snapshot(database):
    with database.transaction() as db:
        profile = own_profile(db, user_for(db))
        result = deepcopy(
            serialize_profile(profile, load_profile_details(db, profile))
        )
        counts = tuple(
            db.scalar(select(func.count()).select_from(model))
            for model in (
                PersonalInterestTag,
                PersonalInterestTagDetails,
                ProfilePersonalInterest,
            )
        )
        return result, counts


def invoke(database, sections, revision=REVISION, email=OWNER):
    assert not has_request_context()
    with database.transaction(write=True) as db:
        return apply_reviewed_extraction(
            db,
            user_for(db, email),
            DOCUMENT_ID,
            expected_profile_revision=revision,
            sections=sections,
        )


@pytest.fixture
def direct_database(app):
    database = app.extensions["database"]
    with database.transaction(write=True) as db:
        profile = own_profile(db, user_for(db))
        profile.display_name = "BE-2 direct service test"
        profile.revision = REVISION
        profile.confirmation_status = "CONFIRMED"
        profile.confirmed_revision = REVISION
        profile.confirmed_at = utcnow()

        replace_skills(
            db,
            profile.talent_id,
            [{
                "id": "skill_original",
                "title": "Python",
                "evidenceText": "Original saved evidence.",
            }],
        )

        for field, text in (
            ("researchInterestText", "Saved research interests"),
            ("resumeDescription", "Saved private resume"),
        ):
            set_profile_text(db, profile.talent_id, field, text)
            db.add(
                ProfileComponentOrigin(
                    talent_id=profile.talent_id,
                    field=field,
                    source_type="MANUAL",
                    document_id=None,
                )
            )

        for field in ("skills", "education"):
            db.add(
                ProfileOrigin(
                    talent_id=profile.talent_id,
                    field=field,
                    source_type="MANUAL",
                    document_id=None,
                )
            )

        db.add(
            Document(
                id=DOCUMENT_ID,
                talent_id=profile.talent_id,
                kind="CV",
                file_name="synthetic.pdf",
                media_type="application/pdf",
                storage_key="be2-direct-test",
                size_bytes=128,
                status="READY",
                error=None,
            )
        )
        db.flush()

        extraction = json.loads(
            (ROOT / "docs/api/examples/extraction-ready.json").read_text(
                encoding="utf-8"
            )
        )
        extraction["documentId"] = DOCUMENT_ID
        db.add(
            DocumentExtraction(
                document_id=DOCUMENT_ID,
                result=extraction,
            )
        )

    assert not has_request_context()
    return database


def test_direct_partial_import_and_old_revision_replay(direct_database):
    before, _ = snapshot(direct_database)
    sections = {
        "skills": [{
            "id": "skill_reviewed",
            "title": "SQL",
            "evidenceText": "User-corrected evidence.",
        }]
    }
    original = deepcopy(sections)

    result = invoke(direct_database, sections)

    validator("Profile").validate(result)
    assert sections == original
    assert result["revision"] == REVISION + 1
    assert result["confirmation"] == {
        "status": "UNCONFIRMED",
        "confirmedRevision": None,
        "confirmedAt": None,
    }
    assert result["content"]["skills"] == sections["skills"]

    for field, value in before["content"].items():
        if field != "skills":
            assert result["content"][field] == value

    assert [
        origin for origin in result["origins"]
        if origin["field"] != "skills"
    ] == [
        origin for origin in before["origins"]
        if origin["field"] != "skills"
    ]
    assert next(
        origin for origin in result["origins"]
        if origin["field"] == "skills"
    ) == {
        "field": "skills",
        "sourceType": "USER_REVIEWED_DOCUMENT",
        "documentId": DOCUMENT_ID,
    }

    saved = snapshot(direct_database)
    assert saved[0] == result

    with pytest.raises(ApiError) as raised:
        invoke(direct_database, sections)
    assert raised.value.code == "REVISION_CONFLICT"
    assert raised.value.revision == REVISION + 1
    assert snapshot(direct_database) == saved

    # Identical content imported with the current revision still increments it.
    repeated = invoke(
        direct_database, sections, revision=result["revision"]
    )
    assert repeated["revision"] == result["revision"] + 1
    assert repeated["content"] == result["content"]
    assert repeated["confirmation"] == result["confirmation"]
    assert snapshot(direct_database)[0] == repeated


@pytest.mark.parametrize(
    "field,value",
    [
        ("skills", []),
        ("researchInterestText", ""),
        ("resumeDescription", ""),
    ],
)
def test_direct_explicit_clearing(direct_database, field, value):
    before, _ = snapshot(direct_database)

    result = invoke(direct_database, {field: value})

    validator("Profile").validate(result)
    assert result["content"][field] == value
    assert result["revision"] == REVISION + 1
    for other, original in before["content"].items():
        if other != field:
            assert result["content"][other] == original


@pytest.mark.parametrize(
    "state,status,code",
    [
        ("QUEUED", 409, "EXTRACTION_NOT_READY"),
        ("PROCESSING", 409, "EXTRACTION_NOT_READY"),
        ("FAILED", 422, "EXTRACTION_FAILED"),
    ],
)
def test_direct_extraction_state_errors(
    direct_database, state, status, code
):
    with direct_database.transaction(write=True) as db:
        document = db.get(Document, DOCUMENT_ID)
        document.status = state
        document.error = (
            {
                "code": "EXTRACTION_FAILED",
                "message": "Synthetic extraction failure.",
                "fieldErrors": [],
            }
            if state == "FAILED"
            else None
        )

    before = snapshot(direct_database)
    with pytest.raises(ApiError) as raised:
        invoke(direct_database, {"skills": []})

    assert (raised.value.status, raised.value.code) == (status, code)
    assert snapshot(direct_database) == before


def test_direct_other_owner_is_hidden_before_payload_validation(
    direct_database,
):
    before = snapshot(direct_database)

    with pytest.raises(ApiError) as raised:
        invoke(direct_database, {}, email="other@example.test")

    assert (raised.value.status, raised.value.code) == (404, "NOT_FOUND")
    assert snapshot(direct_database) == before


def test_direct_stale_import_preserves_confirmed_profile_and_catalogue(
    direct_database,
):
    before = snapshot(direct_database)

    with pytest.raises(ApiError) as raised:
        invoke(
            direct_database,
            {
                "customInterestTags": [{
                    "label": "BE2 stale private topic",
                }]
            },
            revision=REVISION - 1,
        )

    assert (raised.value.status, raised.value.code) == (
        409,
        "REVISION_CONFLICT",
    )
    assert raised.value.revision == before[0]["revision"]
    assert snapshot(direct_database) == before


def test_direct_personal_tags_are_canonical_without_mutating_input(
    direct_database,
):
    sections = {
        "customInterestTags": [{
            "label": "  BE2   private topic  ",
            "description": "Reviewed detail",
        }]
    }
    original = deepcopy(sections)

    result = invoke(direct_database, sections)

    validator("Profile").validate(result)
    tag = result["content"]["customInterestTags"][0]
    assert tag["label"] == "BE2 private topic"
    assert tag["description"] == "Reviewed detail"
    assert tag["id"].startswith("personal_")
    assert sections == original
    assert snapshot(direct_database)[0] == result


@pytest.mark.parametrize(
    "operation",
    [
        "resolve_reviewed_personal_tags",
        "save_reviewed_sections",
    ],
)
def test_direct_failure_rolls_back_flushed_writes(
    direct_database, monkeypatch, operation
):
    before = snapshot(direct_database)
    original_operation = getattr(repository, operation)

    def fail_after_write(*args, **kwargs):
        original_operation(*args, **kwargs)
        db = args[0]
        db.flush()

        # Confirm that a real catalogue write occurred before failure.
        assert db.scalar(
            select(func.count()).select_from(PersonalInterestTag)
        ) == 1

        raise RuntimeError("BE2 injected failure after flushed writes")

    monkeypatch.setattr(repository, operation, fail_after_write)

    with pytest.raises(RuntimeError, match="BE2 injected failure"):
        invoke(
            direct_database,
            {
                "skills": [{
                    "id": "skill_new",
                    "title": "SQL",
                    "evidenceText": "Reviewed",
                }],
                "resumeDescription": "Imported text that must roll back",
                "customInterestTags": [{
                    "label": "BE2 rollback private topic",
                    "description": "Must roll back",
                }],
            },
        )

    assert snapshot(direct_database) == before
