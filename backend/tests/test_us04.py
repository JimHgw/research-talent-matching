from copy import deepcopy
import json

import pytest

from backend.src.features.matching.engine import summarize
from backend.src.shared.paths import ROOT
from backend.src.shared.validation import validator
from conftest import headers, sign_in

PROFILE = "/api/v1/me/profile"
RECOMMENDATIONS = "/api/v1/me/recommendations"
MATCHES = "/api/v1/me/opportunity-matches"
OPPORTUNITIES = "/api/v1/opportunities"


def example(name):
    return json.loads(
        (ROOT / "docs/api/examples" / name).read_text(encoding="utf-8")
    )


def checked(response, schema, status=200):
    data = response.get_json()
    assert response.status_code == status, data
    validator(schema).validate(data)
    return data


def assert_error(response, status, code):
    data = checked(response, "Error", status)
    assert data["error"]["code"] == code


def confirm_profile(signed, content=None):
    client, csrf = signed
    current = checked(client.get(PROFILE), "Profile")
    saved = checked(client.put(
        PROFILE,
        json={
            "expectedRevision": current["revision"],
            "content": content if content is not None else example("profile-write.json")["content"],
        },
        headers=headers(csrf),
    ), "Profile")
    return checked(client.post(
        PROFILE + "/confirmation",
        json={"expectedRevision": saved["revision"]},
        headers=headers(csrf),
    ), "Profile")


@pytest.fixture
def confirmed(signed):
    return signed, confirm_profile(signed)


@pytest.fixture
def research_team(app):
    client = app.test_client()
    return client, sign_in(client, "team@example.test")


def make_opportunity(team, requirements=None, publish=True):
    client, csrf = team
    content = example("opportunity-create.json")
    if requirements is not None:
        content["requirements"] = deepcopy(requirements)
    opportunity = checked(client.post(
        OPPORTUNITIES, json=content, headers=headers(csrf),
    ), "Opportunity", 201)
    if publish:
        opportunity = checked(client.post(
            f"{OPPORTUNITIES}/{opportunity['id']}/publish",
            json={"expectedRevision": opportunity["revision"]},
            headers=headers(csrf),
        ), "Opportunity")
    return opportunity


def test_four_statuses_and_supporting_evidence(confirmed, research_team):
    (client, _), profile = confirmed
    opportunity = make_opportunity(research_team)
    detail = checked(client.get(f"{MATCHES}/{opportunity['id']}"), "OwnerMatch")
    assert detail["profileRevision"] == profile["revision"]
    assert detail["summary"]["score"] == 50.0
    assert detail["summary"]["unknownWeightPercent"] == 16.67
    assert detail["summary"]["requiredGapCount"] == 0
    assert detail["summary"]["evaluationStatus"] == "EVALUATED"
    results = {item["requirement"]["id"]: item for item in detail["requirements"]}
    expected = {
        "req_python": ("MATCHED", "ALL_TAGS_SUPPORTED", ["skill_python"]),
        "req_analysis": ("PARTIAL", "SOME_TAGS_SUPPORTED", ["skill_python"]),
        "req_interviews": ("GAP", "EXPLICIT_NEGATIVE_CLAIM", ["skill_interviews"]),
        "req_r": ("UNKNOWN", "INSUFFICIENT_EVIDENCE", []),
    }
    assert set(results) == set(expected)
    for requirement_id, (status, reason_code, evidence_ids) in expected.items():
        item = results[requirement_id]

        assert item["status"] == status
        assert item["reasonCode"] == reason_code

        assert [
            evidence["recordId"]
            for evidence in item["evidence"]
        ] == evidence_ids

        for evidence in item["evidence"]:
            assert evidence["confirmedRevision"] == profile["revision"]
def test_ranking_pagination_and_draft_exclusion(confirmed, research_team):
    (client, _), _ = confirmed
    requirements = example("opportunity-create.json")["requirements"]

    high = [
        make_opportunity(research_team, [requirements[0]])
        for _ in range(2)
    ]

    middle = make_opportunity(research_team)
    gap = make_opportunity(research_team, [requirements[2]])
    unknown = make_opportunity(research_team, [requirements[3]])

    draft = make_opportunity(research_team, publish=False)

    expected_ids = sorted(item["id"] for item in high) + [
        middle["id"],
        gap["id"],
        unknown["id"],
    ]

    items = []

    for number in range(1, 4):
        page = checked(
            client.get(
                f"{RECOMMENDATIONS}?page={number}&pageSize=2"
            ),
            "RecommendationPage",
        )

        assert page["page"] == number
        assert page["pageSize"] == 2
        assert page["total"] == 5

        items.extend(page["items"])

    actual_ids = [item["opportunity"]["id"] for item in items]

    assert actual_ids == expected_ids
    assert draft["id"] not in actual_ids
    assert [item["rank"] for item in items] == [1, 2, 3, 4, 5]

    assert [
        item["summary"]["score"] for item in items
    ] == [100, 100, 50, 0, 0]

    assert [
        item["summary"]["unknownWeightPercent"] for item in items
    ] == [0, 0, 16.67, 0, 100]

    page = checked(
        client.get(f"{RECOMMENDATIONS}?page=4&pageSize=2"),
        "RecommendationPage",
    )

    assert page["items"] == []
    assert page["total"] == 5
def test_profile_edit_requires_reconfirmation(confirmed, research_team):
    signed, profile = confirmed
    client, csrf = signed

    opportunity = make_opportunity(research_team)
    detail_url = f"{MATCHES}/{opportunity['id']}"

    content = deepcopy(profile["content"])
    content["skills"].append({
        "id": "skill_sql",
        "title": "SQL",
        "evidenceText": "Confirmed SQL experience.",
    })

    saved = checked(
        client.put(
            PROFILE,
            json={
                "expectedRevision": profile["revision"],
                "content": content,
            },
            headers=headers(csrf),
        ),
        "Profile",
    )

    assert saved["revision"] == profile["revision"] + 1

    for url in (RECOMMENDATIONS, detail_url):
        assert_error(
            client.get(url),
            409,
            "PROFILE_UNCONFIRMED",
        )

    checked(
        client.post(
            PROFILE + "/confirmation",
            json={"expectedRevision": saved["revision"]},
            headers=headers(csrf),
        ),
        "Profile",
    )

    detail = checked(client.get(detail_url), "OwnerMatch")

    assert detail["profileRevision"] == saved["revision"]
    assert detail["summary"]["score"] == 66.67

    results = {
        item["requirement"]["id"]: item
        for item in detail["requirements"]
    }
    assert results["req_analysis"]["status"] == "MATCHED"

    page = checked(client.get(RECOMMENDATIONS), "RecommendationPage")
    assert page["items"][0]["summary"] == detail["summary"]
@pytest.mark.parametrize(
    "path",
    [RECOMMENDATIONS, MATCHES + "/opp_missing"],
)
def test_matching_requires_login_and_talent_role(
    client, research_team, path
):
    assert_error(client.get(path), 401, "UNAUTHENTICATED")

    assert_error(
        research_team[0].get(path),
        403,
        "FORBIDDEN",
    )


def test_draft_and_missing_detail_are_not_found(confirmed, research_team):
    (client, _), _ = confirmed
    draft = make_opportunity(research_team, publish=False)

    for opportunity_id in (draft["id"], "opp_missing"):
        assert_error(
            client.get(f"{MATCHES}/{opportunity_id}"),
            404,
            "NOT_FOUND",
        )


@pytest.mark.parametrize(
    "query",
    [
        "page=0",
        "page=-1",
        "page=abc",
        "page=1&page=2",
        "pageSize=0",
        "pageSize=101",
        "pageSize=1.5",
    ],
)
def test_invalid_recommendation_pagination(confirmed, query):
    (client, _), _ = confirmed

    checked(
        client.get(RECOMMENDATIONS + "?" + query),
        "Error",
        422,
    )
def test_no_requirements_returns_insufficient_criteria():
    assert summarize([]) == {
        "score": None,
        "unknownWeightPercent": None,
        "requiredGapCount": 0,
        "evaluationStatus": "INSUFFICIENT_CRITERIA",
        "algorithmVersion": "tag-coverage-v1",
    }
