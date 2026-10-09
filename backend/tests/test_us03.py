import json
import pytest

from backend.src.shared.paths import ROOT
from backend.src.shared.validation import validator
from conftest import headers, sign_in


def test_confirm_profile_and_repeat(signed):
    client, csrf = signed

    # Read the current profile and load valid example content.
    current = client.get("/api/v1/me/profile").get_json()
    content = json.loads(
        (ROOT / "docs/api/examples/profile-write.json").read_text(
            encoding="utf-8"
        )
    )["content"]

    # Save the content before confirming it.
    response = client.put(
        "/api/v1/me/profile",
        json={
            "expectedRevision": current["revision"],
            "content": content,
        },
        headers=headers(csrf),
    )
    assert response.status_code == 200, response.get_json()
    saved = response.get_json()
    assert saved["confirmation"]["status"] == "UNCONFIRMED"

    # Confirm the saved revision.
    response = client.post(
        "/api/v1/me/profile/confirmation",
        json={"expectedRevision": saved["revision"]},
        headers=headers(csrf),
    )
    assert response.status_code == 200, response.get_json()
    confirmed = response.get_json()
    validator("Profile").validate(confirmed)

    assert confirmed["content"] == saved["content"]
    assert confirmed["revision"] == saved["revision"]
    assert confirmed["confirmation"]["status"] == "CONFIRMED"
    assert confirmed["confirmation"]["confirmedRevision"] == saved["revision"]
    assert confirmed["confirmation"]["confirmedAt"] is not None

    # Check that confirmation was persisted.
    response = client.get("/api/v1/me/profile")
    assert response.status_code == 200, response.get_json()
    assert response.get_json() == confirmed

    # Repeating confirmation must preserve the result and timestamp.
    response = client.post(
        "/api/v1/me/profile/confirmation",
        json={"expectedRevision": saved["revision"]},
        headers=headers(csrf),
    )
    assert response.status_code == 200, response.get_json()
    assert response.get_json() == confirmed

def test_confirm_rejects_empty_sections(signed):
    client, csrf = signed

    # Prepare a profile with name but do not have academic/research entries.
    current = client.get("/api/v1/me/profile").get_json()
    content = {
        "displayName": "Test Talent",
        "disciplineGroup": None,
        "education": [],
        "courses": [],
        "researchExperience": [],
        "researchOutputs": [],
        "skills": [],
        "researchInterests": [],
    }

    # Saving incomplete content is allowed.
    response = client.put(
        "/api/v1/me/profile",
        json={
            "expectedRevision": current["revision"],
            "content": content,
        },
        headers=headers(csrf),
    )
    assert response.status_code == 200, response.get_json()
    saved = response.get_json()

    response = client.post(
        "/api/v1/me/profile/confirmation",
        json={
            "expectedRevision": saved["revision"]
        },
        headers=headers(csrf),
    )
    assert response.status_code == 422, response.get_json()

    error = response.get_json()
    validator("Error").validate(error)
    assert error["error"]["code"] == "VALIDATION_ERROR"
    assert error["error"]["fieldErrors"][0]["field"] == "content"

    # Leave the profile unchanged.
    response = client.get("/api/v1/me/profile")
    assert response.status_code == 200, response.get_json()
    assert response.get_json() == saved

@pytest.mark.parametrize("display_name", ["", "   "])
def test_confirm_rejects_blank_name(signed, display_name):
    client, csrf = signed

    current = client.get("/api/v1/me/profile").get_json()
    content = json.loads(
        (ROOT / "docs/api/examples/profile-write.json").read_text(
            encoding="utf-8"
        )
    )["content"]
    content["displayName"] = display_name

    # Saving an incomplete profile is allowed.
    response = client.put(
        "/api/v1/me/profile",
        json={
            "expectedRevision": current["revision"],
            "content": content,
        },
        headers=headers(csrf),
    )
    assert response.status_code == 200, response.get_json()
    saved = response.get_json()

    # A blank name must prevent confirmation
    response = client.post(
        "/api/v1/me/profile/confirmation",
        json={"expectedRevision": saved["revision"]},
        headers=headers(csrf),
    )
    assert response.status_code == 422, response.get_json()

    # Check the error
    error = response.get_json()
    validator("Error").validate(error)
    assert error["error"]["code"] == "VALIDATION_ERROR"
    assert error["error"]["fieldErrors"][0]["field"] == "content.displayName"

    # Leave the saved profile unchanged.
    response = client.get("/api/v1/me/profile")
    assert response.status_code == 200, response.get_json()
    assert response.get_json() == saved

def test_confirm_rejects_stale_revision(signed):
    client, csrf = signed

    # Remeber the old version
    current = client.get("/api/v1/me/profile").get_json()
    content = json.loads(
        (ROOT / "docs/api/examples/profile-write.json").read_text(
            encoding="utf-8"
        )
    )["content"]

    # Saving changed content creates a new revision.
    response = client.put(
        "/api/v1/me/profile",
        json = {
            "expectedRevision": current["revision"],
            "content": content,
        },
        headers=headers(csrf),
    )
    assert response.status_code == 200, response.get_json()
    saved = response.get_json()
    assert saved["revision"] == current["revision"] + 1

    # Deliberately confirm using the old revision
    response = client.post(
        "/api/v1/me/profile/confirmation",
        json={"expectedRevision": current["revision"]},
        headers=headers(csrf),
    )

    assert response.status_code == 409, response.get_json()
    error = response.get_json()
    validator("Error").validate(error)
    assert error["error"]["code"] == "REVISION_CONFLICT"
    assert error["error"]["currentRevision"] == saved["revision"]

    # The rejected request must not change or confirm the profile.
    response = client.get("/api/v1/me/profile")
    assert response.status_code == 200, response.get_json()
    assert response.get_json() == saved

def test_edit_confirmed_profile_requires_reconfirmation(signed):
    client, csrf = signed

    # save a valid profile
    current = client.get("/api/v1/me/profile").get_json()
    content = json.loads(
        (ROOT / "docs/api/examples/profile-write.json").read_text(
            encoding="utf-8"
        )
    )["content"]

    response = client.put(
        "/api/v1/me/profile",
        json = {
             "expectedRevision": current["revision"],
            "content": content,
        },
        headers=headers(csrf),
    )

    assert response.status_code == 200, response.get_json()
    saved = response.get_json()

    # Confirm the saved revision.
    response = client.post(
        "/api/v1/me/profile/confirmation",
        json={"expectedRevision": saved["revision"]},
        headers=headers(csrf),
    )
    assert response.status_code == 200, response.get_json()
    confirmed = response.get_json()
    assert confirmed["confirmation"]["status"] == "CONFIRMED"

    # Change the name and save again.
    content["displayName"] = "Updated Talent"

    response = client.put(
        "/api/v1/me/profile",
        json={
            "expectedRevision": confirmed["revision"],
            "content": content,
        },
        headers=headers(csrf),
    )
    assert response.status_code == 200, response.get_json()
    updated = response.get_json()

    assert updated["revision"] == confirmed["revision"] + 1
    assert updated["content"] == content
    assert updated["confirmation"]["status"] == "UNCONFIRMED"
    assert updated["confirmation"]["confirmedRevision"] is None
    assert updated["confirmation"]["confirmedAt"] is None

    # Check that clearing confirmation was persisted.
    response = client.get("/api/v1/me/profile")
    assert response.status_code == 200, response.get_json()
    assert response.get_json() == updated

    # 4. Confirm the new revision.
    response = client.post(
        "/api/v1/me/profile/confirmation",
        json={"expectedRevision": updated["revision"]},
        headers=headers(csrf),
    )
    assert response.status_code == 200, response.get_json()
    reconfirmed = response.get_json()

    assert reconfirmed["revision"] == updated["revision"]
    assert reconfirmed["confirmation"]["status"] == "CONFIRMED"
    assert reconfirmed["confirmation"]["confirmedRevision"] == updated["revision"]
    assert reconfirmed["confirmation"]["confirmedAt"] is not None

def test_confirm_requires_login(client):
    response = client.post(
        "/api/v1/me/profile/confirmation",
        json={"expectedRevision": 0},
    )

    assert response.status_code == 401, response.get_json()
    error = response.get_json()
    validator("Error").validate(error)
    assert error["error"]["code"] == "UNAUTHENTICATED"

def test_confirm_rejects_team_account(client):
    # Sign in using the research team account.
    csrf = sign_in(client, email="team@example.test")

    response = client.post(
        "/api/v1/me/profile/confirmation",
        json={"expectedRevision": 0},
        headers=headers(csrf),
    )

    assert response.status_code == 403, response.get_json()
    error = response.get_json()
    validator("Error").validate(error)
    assert error["error"]["code"] == "FORBIDDEN"

def test_confirm_rejects_invalid_csrf(signed):
    client, csrf = signed

    # Keep the valid Origin, but replace the CSRF token.
    request_headers = headers(csrf)
    request_headers["X-CSRF-Token"] = "invalid-test-token"

    response = client.post(
        "/api/v1/me/profile/confirmation",
        json={"expectedRevision": 0},
        headers=request_headers,
    )

    assert response.status_code == 403, response.get_json()
    error = response.get_json()
    validator("Error").validate(error)
    assert error["error"]["code"] == "CSRF_INVALID"