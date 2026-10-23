"""Acceptance coverage for talent privacy and field visibility (US-07)."""

import pytest

from backend.src.db.models import Document, ProfileOrigin
from conftest import headers
from test_us04 import (
    OPPORTUNITIES,
    PROFILE,
    assert_error,
    checked,
    confirm_profile,
    make_opportunity,
    research_team,
)


PRIVACY = "/api/v1/me/privacy"


def update_privacy(signed, fields, discoverable):
    """Update the current talent user's privacy settings."""
    client, csrf = signed
    fields = [field for field in fields if field not in ("researchInterestText", "customInterestTags", "resumeDescription")]

    current = checked(
        client.get(PRIVACY),
        "Privacy",
    )

    return checked(
        client.put(
            PRIVACY,
            json={
                "expectedRevision": current["revision"],
                "discoverable": discoverable,
                "visibleFields": fields,
            },
            headers=headers(csrf),
        ),
        "Privacy",
    )


@pytest.fixture
def privacy_context(signed, research_team):
    """Confirmed talent profile plus a published research opportunity."""
    profile = confirm_profile(signed)
    opportunity = make_opportunity(research_team)

    url = (
        f"{OPPORTUNITIES}/"
        f"{opportunity['id']}/talent-matches"
    )

    return signed, research_team, profile, opportunity, url


def test_profile_is_private_by_default(signed):
    """AC1: Talent profiles must be private by default."""
    client, _ = signed

    privacy = checked(
        client.get(PRIVACY),
        "Privacy",
    )

    assert privacy["revision"] == 0
    assert privacy["discoverable"] is False
    assert privacy["visibleFields"] == []


def test_user_can_enable_disable_discovery_and_choose_visible_fields(signed):
    """AC2/AC3: Users control discovery and visible structured fields."""
    confirm_profile(signed)

    enabled = update_privacy(
        signed,
        ["displayName", "skills", "researchInterests"],
        True,
    )

    assert enabled["discoverable"] is True
    assert enabled["visibleFields"] == [
        "displayName",
        "researchInterests",
        "skills",
    ]

    disabled = update_privacy(
        signed,
        ["displayName"],
        False,
    )

    assert disabled["discoverable"] is False
    assert disabled["visibleFields"] == [
        "displayName",
    ]

    reread = checked(
        signed[0].get(PRIVACY),
        "Privacy",
    )

    assert reread == disabled


def test_discovery_disabled_excludes_talent_from_team_results(
    privacy_context,
):
    """AC4: Opted-out talent must disappear from research-team discovery."""
    signed, (team, _), profile, _, url = privacy_context

    update_privacy(
        signed,
        ["displayName", "skills"],
        True,
    )

    visible = checked(
        team.get(url),
        "TalentMatchPage",
    )

    assert visible["total"] == 1
    assert (
        visible["items"][0]["talent"]["talentId"]
        == profile["talentId"]
    )

    update_privacy(
        signed,
        ["displayName", "skills"],
        False,
    )

    hidden = checked(
        team.get(url),
        "TalentMatchPage",
    )

    assert hidden["total"] == 0
    assert hidden["items"] == []

    assert_error(
        team.get(
            f"{url}/{profile['talentId']}"
        ),
        404,
        "NOT_FOUND",
    )


def test_private_fields_are_not_visible_or_used_by_research_teams(
    privacy_context,
):
    """AC5: Hidden profile fields must not appear or affect team matching."""
    signed, (team, _), profile, _, url = privacy_context

    update_privacy(
        signed,
        ["displayName"],
        True,
    )

    detail = checked(
        team.get(
            f"{url}/{profile['talentId']}"
        ),
        "TeamMatch",
    )

    assert set(detail["talent"]["fields"]) == {
        "displayName",
    }

    assert detail["talent"]["fields"]["displayName"] == (
        profile["content"]["displayName"]
    )

    assert detail["summary"]["score"] == 0
    assert detail["summary"]["unknownWeightPercent"] == 100
    assert detail["summary"]["requiredGapCount"] == 0

    for result in detail["requirements"]:
        assert result["status"] == "UNKNOWN"
        assert result["evidence"] == []


def test_document_metadata_never_leaks_to_team_results(
    app,
    privacy_context,
):
    """AC6 partial coverage: team responses never expose document metadata."""
    signed, (team, _), profile, _, url = privacy_context

    with app.extensions["database"].transaction(
        write=True
    ) as db:
        db.add(
            Document(
                id="us07_private_cv",
                talent_id=profile["talentId"],
                kind="CV",
                file_name="private-cv.pdf",
                media_type="application/pdf",
                storage_key="private-storage-key",
                status="READY",
                size_bytes=1,
            )
        )

        db.flush()

        origin = db.get(
            ProfileOrigin,
            (
                profile["talentId"],
                "skills",
            ),
        )

        origin.source_type = (
            "USER_REVIEWED_DOCUMENT"
        )
        origin.document_id = "us07_private_cv"

    update_privacy(
        signed,
        list(profile["content"]),
        True,
    )

    page = checked(
        team.get(url),
        "TalentMatchPage",
    )

    detail = checked(
        team.get(
            f"{url}/{profile['talentId']}"
        ),
        "TeamMatch",
    )

    forbidden_keys = {
        "email",
        "origins",
        "documentId",
        "sourceType",
        "confirmedRevision",
        "fileName",
        "storageKey",
        "downloadUrl",
    }

    def assert_no_private_document_data(value):
        if isinstance(value, dict):
            assert not (
                set(value)
                & forbidden_keys
            )

            for item in value.values():
                assert_no_private_document_data(
                    item
                )

        elif isinstance(value, list):
            for item in value:
                assert_no_private_document_data(
                    item
                )

    assert_no_private_document_data(page)
    assert_no_private_document_data(detail)


@pytest.mark.parametrize(
    "fields",
    [
        ["email"],
        ["documentId"],
        ["skills", "skills"],
    ],
)
def test_privacy_rejects_unsupported_or_duplicate_visible_fields(
    signed,
    fields,
):
    """Only supported structured profile fields may be shared."""
    client, csrf = signed

    response = client.put(
        PRIVACY,
        json={
            "expectedRevision": 0,
            "discoverable": True,
            "visibleFields": fields,
        },
        headers=headers(csrf),
    )

    assert_error(
        response,
        422,
        "VALIDATION_ERROR",
    )


def test_privacy_settings_are_talent_only_and_require_csrf(
    app,
    signed,
    research_team,
):
    """Privacy settings cannot be read or changed by unauthorised users."""
    team, _ = research_team

    assert_error(
        app.test_client().get(PRIVACY),
        401,
        "UNAUTHENTICATED",
    )

    assert_error(
        team.get(PRIVACY),
        403,
        "FORBIDDEN",
    )

    client, _ = signed

    response = client.put(
        PRIVACY,
        json={
            "expectedRevision": 0,
            "discoverable": True,
            "visibleFields": [
                "skills",
            ],
        },
    )

    assert response.status_code == 403


def test_privacy_changes_do_not_modify_profile_content(signed):
    """Changing visibility must not alter the talent user's profile data."""
    profile = confirm_profile(signed)

    update_privacy(
        signed,
        ["displayName", "skills"],
        True,
    )

    after = checked(
        signed[0].get(PROFILE),
        "Profile",
    )

    assert after == profile
