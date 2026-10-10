import pytest

from backend.src.features.matching.engine import (
    evaluate_requirement,
    summarize,
)


@pytest.fixture
def matching_profile():
    return {
        "revision": 3,
        "origins": {},
        "skills": {
            "skill_python": {
                "label": "Python",
                "claim": "HAS",
                "evidenceText": "Used Python to clean research datasets.",
            },
            "skill_interviews": {
                "label": "Research interviews",
                "claim": "DOES_NOT_HAVE",
                "evidenceText": "I have not conducted research interviews.",
            },
        },
        "researchInterests": {
            "interest_ml": "Machine learning",
        },
    }


def requirement(tag_ids, kind="SKILL"):
    return {
        "id": "req_test",
        "label": "Test requirement",
        "kind": kind,
        "importance": "REQUIRED",
        "tagIds": tag_ids,
    }


@pytest.mark.parametrize(
    "tag_ids,status,evidence_ids",
    [
        (["skill_python"], "MATCHED", ["skill_python"]),
        (
            ["skill_python", "skill_sql"],
            "PARTIAL",
            ["skill_python"],
        ),
        (
            ["skill_interviews"],
            "GAP",
            ["skill_interviews"],
        ),
        (
            ["skill_python", "skill_interviews"],
            "GAP",
            ["skill_interviews"],
        ),
        (["skill_r"], "UNKNOWN", []),
        (["skill_sql", "skill_r"], "UNKNOWN", []),
    ],
)
def test_requirement_status_and_evidence(
    matching_profile, tag_ids, status, evidence_ids
):
    result = evaluate_requirement(
        requirement(tag_ids),
        matching_profile,
    )

    assert result["status"] == status
    assert result["reason"].strip()

    assert [
        evidence["recordId"]
        for evidence in result["evidence"]
    ] == evidence_ids

    for evidence in result["evidence"]:
        assert evidence["field"] == "skills"
        assert evidence["confirmedRevision"] == 3
        assert evidence["sourceType"] == "MANUAL"
        assert evidence["documentId"] is None


def test_evidence_contains_actual_profile_text(matching_profile):
    result = evaluate_requirement(
        requirement(["skill_python"]),
        matching_profile,
    )

    actual_text = matching_profile["skills"]["skill_python"]["evidenceText"]

    assert actual_text in result["evidence"][0]["valueSummary"]


def test_interest_uses_interest_evidence(matching_profile):
    result = evaluate_requirement(
        requirement(["interest_ml"], kind="INTEREST"),
        matching_profile,
    )

    assert result["status"] == "MATCHED"

    evidence = result["evidence"][0]
    assert evidence["field"] == "researchInterests"
    assert evidence["recordId"] == "interest_ml"
    assert evidence["confirmedRevision"] == 3


def test_required_negative_claim_is_counted_as_gap(matching_profile):
    result = evaluate_requirement(
        requirement(["skill_interviews"]),
        matching_profile,
    )

    summary = summarize([result])

    assert summary["score"] == 0
    assert summary["unknownWeightPercent"] == 0
    assert summary["requiredGapCount"] == 1


def test_no_requirements_have_no_score():
    summary = summarize([])

    assert summary["score"] is None
    assert summary["unknownWeightPercent"] is None
    assert summary["evaluationStatus"] == "INSUFFICIENT_CRITERIA"