"""BE-1 executable fixture and profile error contracts."""

from copy import deepcopy
import json

import pytest

from backend.src.db.models import (
    Document,
    Opportunity,
    PrivacySettings,
    TalentProfile,
)
from backend.src.shared.paths import ROOT
from backend.src.shared.validation import validator
from conftest import headers

from test_us01 import checked, sample, save
from test_us09 import ready_document

from test_us02 import create as create_opportunity
from test_us02 import publish as publish_opportunity
from test_us02 import save as save_opportunity
from test_us02 import team
EXAMPLE_DIR = ROOT / "docs/api/examples"
EXAMPLES = json.loads(
    (EXAMPLE_DIR / "index.json").read_text(encoding="utf-8")
)
PROFILE_URL = "/api/v1/me/profile"


def load_example(filename):
    return json.loads(
        (EXAMPLE_DIR / filename).read_text(encoding="utf-8")
    )


@pytest.mark.parametrize(
    "example",
    EXAMPLES,
    ids=lambda item: item["file"],
)
def test_indexed_example_matches_schema(example):
    payload = load_example(example["file"])
    validator(example["schema"]).validate(payload)


def test_skill_validation_error_matches_current_example(signed):
    client, csrf = signed
    before = checked(client.get(PROFILE_URL), 200, "Profile")

    content = sample()
    content["skills"][0]["title"] = ""

    response = save(
        client, csrf, content, before["revision"]
    )
    payload = checked(response, 422)

    assert payload["error"] == load_example(
        "error-validation.json"
    )["error"]
    assert payload["error"]["fieldErrors"][0]["field"] == (
        "content.skills[0].title"
    )
    assert checked(
        client.get(PROFILE_URL), 200, "Profile"
    ) == before


@pytest.mark.parametrize("operation", ["save", "confirmation"])
def test_profile_conflict_reports_database_revision(
    app, signed, operation
):
    client, csrf = signed

    first = checked(
        save(client, csrf, sample()), 200, "Profile"
    )

    updated_content = deepcopy(first["content"])
    updated_content["displayName"] = "BE-1 current profile"
    latest = checked(
        save(
            client,
            csrf,
            updated_content,
            first["revision"],
        ),
        200,
        "Profile",
    )
    assert latest["revision"] == first["revision"] + 1

    if operation == "save":
        stale_content = deepcopy(latest["content"])
        stale_content["displayName"] = "BE-1 stale overwrite"
        response = save(
            client,
            csrf,
            stale_content,
            first["revision"],
        )
    else:
        response = client.post(
            PROFILE_URL + "/confirmation",
            json={"expectedRevision": first["revision"]},
            headers=headers(csrf),
        )

    payload = checked(response, 409)
    assert payload["error"]["code"] == "REVISION_CONFLICT"

    with app.extensions["database"].transaction() as db:
        stored = db.get(TalentProfile, latest["talentId"])
        assert stored is not None
        assert stored.revision == latest["revision"]
        assert (
            payload["error"]["currentRevision"]
            == stored.revision
        )
        assert (
            stored.display_name
            == latest["content"]["displayName"]
        )
        assert (
            stored.confirmation_status
            == latest["confirmation"]["status"]
        )
        assert (
            stored.confirmed_revision
            == latest["confirmation"]["confirmedRevision"]
        )
        assert stored.confirmed_at is None

    assert checked(
        client.get(PROFILE_URL), 200, "Profile"
    ) == latest


def test_privacy_conflict_uses_its_own_database_revision(app, signed):
    client, csrf = signed
    privacy_url = "/api/v1/me/privacy"

    saved = checked(save(client, csrf, sample()), 200, "Profile")
    profile = checked(
        client.post(
            PROFILE_URL + "/confirmation",
            json={"expectedRevision": saved["revision"]},
            headers=headers(csrf),
        ),
        200,
        "Profile",
    )

    latest = checked(client.get(privacy_url), 200, "Privacy")
    for fields in ([], ["skills"]):
        latest = checked(
            client.put(
                privacy_url,
                json={
                    "expectedRevision": latest["revision"],
                    "discoverable": True,
                    "visibleFields": fields,
                },
                headers=headers(csrf),
            ),
            200,
            "Privacy",
        )

    # Keep the two counters different to detect a wrong revision source.
    assert latest["revision"] != profile["revision"]

    payload = checked(
        client.put(
            privacy_url,
            json={
                "expectedRevision": latest["revision"] - 1,
                "discoverable": False,
                "visibleFields": [],
            },
            headers=headers(csrf),
        ),
        409,
    )
    assert payload["error"]["code"] == "REVISION_CONFLICT"

    with app.extensions["database"].transaction() as db:
        settings = db.get(PrivacySettings, profile["talentId"])
        assert settings is not None
        assert settings.revision == latest["revision"]
        assert payload["error"]["currentRevision"] == settings.revision

    assert checked(client.get(privacy_url), 200, "Privacy") == latest
    assert checked(client.get(PROFILE_URL), 200, "Profile") == profile


@pytest.mark.parametrize(
    "state,status,code",
    [
        ("QUEUED", 409, "EXTRACTION_NOT_READY"),
        ("PROCESSING", 409, "EXTRACTION_NOT_READY"),
        ("FAILED", 422, "EXTRACTION_FAILED"),
    ],
)
def test_apply_preserves_extraction_state_errors(
    app, signed, ready_document, state, status, code
):
    client, csrf = signed
    before = checked(client.get(PROFILE_URL), 200, "Profile")

    # Inject the state to exercise the HTTP gate even with a stored result.
    with app.extensions["database"].transaction(write=True) as db:
        document = db.get(Document, ready_document)
        assert document is not None
        document.status = state
        if state == "FAILED":
            document.error = {
                "code": "EXTRACTION_FAILED",
                "message": "The document could not be processed.",
                "fieldErrors": [],
            }
        else:
            document.error = None

    payload = checked(
        client.post(
            f"/api/v1/me/documents/{ready_document}/apply",
            json={
                "expectedProfileRevision": before["revision"],
                "sections": {"skills": []},
            },
            headers=headers(csrf),
        ),
        status,
    )

    assert payload["error"]["code"] == code
    assert payload["error"]["fieldErrors"] == []
    assert "currentRevision" not in payload["error"]
    assert checked(client.get(PROFILE_URL), 200, "Profile") == before


def test_apply_conflict_matches_database_and_preserves_confirmation(
    app, signed, ready_document
):
    client, csrf = signed
    saved = checked(save(client, csrf, sample()), 200, "Profile")
    before = checked(
        client.post(
            PROFILE_URL + "/confirmation",
            json={"expectedRevision": saved["revision"]},
            headers=headers(csrf),
        ),
        200,
        "Profile",
    )

    payload = checked(
        client.post(
            f"/api/v1/me/documents/{ready_document}/apply",
            json={
                "expectedProfileRevision": before["revision"] - 1,
                "sections": {"skills": []},
            },
            headers=headers(csrf),
        ),
        409,
    )
    assert payload["error"]["code"] == "REVISION_CONFLICT"

    with app.extensions["database"].transaction() as db:
        stored = db.get(TalentProfile, before["talentId"])
        assert stored is not None
        assert stored.revision == before["revision"]
        assert payload["error"]["currentRevision"] == stored.revision
        assert stored.confirmation_status == "CONFIRMED"
        assert stored.confirmed_revision == before["revision"]

    assert checked(client.get(PROFILE_URL), 200, "Profile") == before

@pytest.mark.parametrize("operation", ["save", "publish"])
def test_opportunity_conflict_reports_database_revision(
    app, team, operation
):
    client, _ = team
    draft = create_opportunity(team)

    updated_content = deepcopy(draft["content"])
    updated_content["title"] = "BE-1 current opportunity"
    latest = checked(
        save_opportunity(team, draft, value=updated_content),
        200,
        "Opportunity",
    )
    assert latest["revision"] == draft["revision"] + 1

    if operation == "save":
        stale_content = deepcopy(latest["content"])
        stale_content["title"] = "BE-1 stale overwrite"
        response = save_opportunity(
            team,
            latest,
            value=stale_content,
            revision=draft["revision"],
        )
    else:
        response = publish_opportunity(
            team,
            latest,
            revision=draft["revision"],
        )

    payload = checked(response, 409)
    assert payload["error"]["code"] == "REVISION_CONFLICT"

    with app.extensions["database"].transaction() as db:
        stored = db.get(Opportunity, latest["id"])
        assert stored is not None
        assert stored.revision == latest["revision"]
        assert payload["error"]["currentRevision"] == stored.revision
        assert stored.title == latest["content"]["title"]
        assert stored.status == "DRAFT"

    assert checked(
        client.get(f"/api/v1/opportunities/{latest['id']}"),
        200,
        "Opportunity",
    ) == latest
