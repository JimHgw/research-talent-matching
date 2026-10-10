"""Evaluation of Sprint 1 tag-based matching quality (US-06).

The cases in this module use synthetic/de-identified data and manually
labelled expected results.  The goal is to compare the current
tag-coverage-v1 algorithm against those labels in a reproducible way.
"""

import pytest

from backend.src.features.matching.engine import evaluate_opportunity


def make_skill(label, claim="HAS", evidence_text="Synthetic confirmed evidence."):
    return {
        "label": label,
        "claim": claim,
        "evidenceText": evidence_text,
    }


def make_profile(skills=None, interests=None):
    return {
        "revision": 1,
        "skills": skills or {},
        "researchInterests": interests or {},
        "origins": {
            "skills": {
                "sourceType": "MANUAL",
                "documentId": None,
            },
            "researchInterests": {
                "sourceType": "MANUAL",
                "documentId": None,
            },
        },
    }


def make_requirement(
    requirement_id,
    kind,
    label,
    importance,
    tag_ids,
):
    return {
        "id": requirement_id,
        "kind": kind,
        "label": label,
        "importance": importance,
        "tagIds": tag_ids,
    }


def make_opportunity(requirements):
    return {
        "content": {
            "requirements": requirements,
        }
    }


EVALUATION_CASES = [
    {
        "id": "perfect_match",
        "category": "normal",
        "profile": make_profile(
            skills={
                "skill_python": make_skill("Python"),
                "skill_sql": make_skill("SQL"),
            },
            interests={
                "interest_ml": "Machine learning",
            },
        ),
        "opportunity": make_opportunity(
            [
                make_requirement(
                    "req_python",
                    "SKILL",
                    "Python",
                    "REQUIRED",
                    ["skill_python"],
                ),
                make_requirement(
                    "req_sql",
                    "SKILL",
                    "SQL",
                    "PREFERRED",
                    ["skill_sql"],
                ),
                make_requirement(
                    "req_ml",
                    "INTEREST",
                    "Machine learning",
                    "PREFERRED",
                    ["interest_ml"],
                ),
            ]
        ),
        "expected_statuses": [
            "MATCHED",
            "MATCHED",
            "MATCHED",
        ],
        "expected_summary": {
            "score": 100.0,
            "unknownWeightPercent": 0.0,
            "requiredGapCount": 0,
            "evaluationStatus": "EVALUATED",
        },
    },
    {
        "id": "partial_multi_tag_requirement",
        "category": "partial",
        "profile": make_profile(
            skills={
                "skill_python": make_skill("Python"),
            },
            interests={
                "interest_ml": "Machine learning",
            },
        ),
        "opportunity": make_opportunity(
            [
                make_requirement(
                    "req_programming",
                    "SKILL",
                    "Python and SQL",
                    "REQUIRED",
                    ["skill_python", "skill_sql"],
                ),
                make_requirement(
                    "req_ml",
                    "INTEREST",
                    "Machine learning",
                    "PREFERRED",
                    ["interest_ml"],
                ),
            ]
        ),
        "expected_statuses": [
            "PARTIAL",
            "MATCHED",
        ],
        "expected_summary": {
            "score": 66.67,
            "unknownWeightPercent": 0.0,
            "requiredGapCount": 0,
            "evaluationStatus": "EVALUATED",
        },
    },
    {
        "id": "explicit_negative_gap",
        "category": "gap",
        "profile": make_profile(
            skills={
                "skill_python": make_skill("Python"),
                "skill_interviews": make_skill(
                    "Interviewing",
                    claim="DOES_NOT_HAVE",
                    evidence_text="Synthetic explicit negative claim.",
                ),
            },
            interests={
                "interest_ml": "Machine learning",
            },
        ),
        "opportunity": make_opportunity(
            [
                make_requirement(
                    "req_methods",
                    "SKILL",
                    "Python and interviewing",
                    "REQUIRED",
                    ["skill_python", "skill_interviews"],
                ),
                make_requirement(
                    "req_ml",
                    "INTEREST",
                    "Machine learning",
                    "PREFERRED",
                    ["interest_ml"],
                ),
            ]
        ),
        "expected_statuses": [
            "GAP",
            "MATCHED",
        ],
        "expected_summary": {
            "score": 33.33,
            "unknownWeightPercent": 0.0,
            "requiredGapCount": 1,
            "evaluationStatus": "EVALUATED",
        },
    },
    {
        "id": "missing_information",
        "category": "missing_information",
        "profile": make_profile(),
        "opportunity": make_opportunity(
            [
                make_requirement(
                    "req_python",
                    "SKILL",
                    "Python",
                    "REQUIRED",
                    ["skill_python"],
                ),
                make_requirement(
                    "req_ml",
                    "INTEREST",
                    "Machine learning",
                    "PREFERRED",
                    ["interest_ml"],
                ),
            ]
        ),
        "expected_statuses": [
            "UNKNOWN",
            "UNKNOWN",
        ],
        "expected_summary": {
            "score": 0.0,
            "unknownWeightPercent": 100.0,
            "requiredGapCount": 0,
            "evaluationStatus": "EVALUATED",
        },
    },
    {
        "id": "unmatched_tags",
        "category": "unmatched_tags",
        "profile": make_profile(
            skills={
                "skill_java": make_skill("Java"),
            },
            interests={
                "interest_cv": "Computer vision",
            },
        ),
        "opportunity": make_opportunity(
            [
                make_requirement(
                    "req_python",
                    "SKILL",
                    "Python",
                    "REQUIRED",
                    ["skill_python"],
                ),
                make_requirement(
                    "req_nlp",
                    "INTEREST",
                    "Natural language processing",
                    "PREFERRED",
                    ["interest_nlp"],
                ),
            ]
        ),
        "expected_statuses": [
            "UNKNOWN",
            "UNKNOWN",
        ],
        "expected_summary": {
            "score": 0.0,
            "unknownWeightPercent": 100.0,
            "requiredGapCount": 0,
            "evaluationStatus": "EVALUATED",
        },
    },
    {
        "id": "incomplete_profile",
        "category": "incomplete_profile",
        "profile": make_profile(
            skills={
                "skill_python": make_skill("Python"),
            },
        ),
        "opportunity": make_opportunity(
            [
                make_requirement(
                    "req_programming",
                    "SKILL",
                    "Python and SQL",
                    "REQUIRED",
                    ["skill_python", "skill_sql"],
                ),
                make_requirement(
                    "req_nlp",
                    "INTEREST",
                    "Natural language processing",
                    "PREFERRED",
                    ["interest_nlp"],
                ),
            ]
        ),
        "expected_statuses": [
            "PARTIAL",
            "UNKNOWN",
        ],
        "expected_summary": {
            "score": 33.33,
            "unknownWeightPercent": 33.33,
            "requiredGapCount": 0,
            "evaluationStatus": "EVALUATED",
        },
    },
    {
        "id": "no_matching_criteria",
        "category": "insufficient_criteria",
        "profile": make_profile(
            skills={
                "skill_python": make_skill("Python"),
            },
        ),
        "opportunity": make_opportunity([]),
        "expected_statuses": [],
        "expected_summary": {
            "score": None,
            "unknownWeightPercent": None,
            "requiredGapCount": 0,
            "evaluationStatus": "INSUFFICIENT_CRITERIA",
        },
    },
]


@pytest.mark.parametrize(
    "case",
    EVALUATION_CASES,
    ids=lambda case: case["id"],
)
def test_manually_labelled_matching_results(case):
    """Compare algorithm output with manually labelled expected results."""
    results, summary = evaluate_opportunity(
        case["opportunity"],
        case["profile"],
    )

    actual_statuses = [
        result["status"]
        for result in results
    ]

    assert actual_statuses == case["expected_statuses"]

    for key, expected_value in case["expected_summary"].items():
        assert summary[key] == expected_value

    assert summary["algorithmVersion"] == "tag-coverage-v1"


def test_evaluation_dataset_covers_required_scenarios():
    """Ensure the US-06 dataset keeps the required edge cases."""
    categories = {
        case["category"]
        for case in EVALUATION_CASES
    }

    assert {
        "normal",
        "partial",
        "gap",
        "missing_information",
        "unmatched_tags",
        "incomplete_profile",
        "insufficient_criteria",
    } <= categories


def test_matching_evaluation_metrics():
    """Calculate reproducible quality measures over the labelled dataset."""
    total_requirements = 0
    correct_requirements = 0

    total_summaries = 0
    correct_summaries = 0

    incorrect_cases = []

    for case in EVALUATION_CASES:
        results, summary = evaluate_opportunity(
            case["opportunity"],
            case["profile"],
        )

        actual_statuses = [
            result["status"]
            for result in results
        ]

        expected_statuses = case["expected_statuses"]

        total_requirements += len(expected_statuses)

        correct_requirements += sum(
            actual == expected
            for actual, expected in zip(
                actual_statuses,
                expected_statuses,
            )
        )

        expected_summary = case["expected_summary"]

        summary_matches = all(
            summary[key] == expected_value
            for key, expected_value in expected_summary.items()
        )

        total_summaries += 1
        correct_summaries += int(summary_matches)

        if (
            actual_statuses != expected_statuses
            or not summary_matches
        ):
            incorrect_cases.append(case["id"])

    status_accuracy = (
        correct_requirements / total_requirements
        if total_requirements
        else 1.0
    )

    summary_exact_match_accuracy = (
        correct_summaries / total_summaries
        if total_summaries
        else 1.0
    )

    print(
        f"US-06 requirement-status accuracy: "
        f"{status_accuracy:.2%}"
    )

    print(
        f"US-06 summary exact-match accuracy: "
        f"{summary_exact_match_accuracy:.2%}"
    )

    print(
        f"US-06 incorrect labelled cases: "
        f"{incorrect_cases}"
    )

    assert status_accuracy == 1.0
    assert summary_exact_match_accuracy == 1.0
    assert incorrect_cases == []