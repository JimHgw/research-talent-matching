from decimal import Decimal, ROUND_HALF_UP


REASONS = {
    "MATCHED": (
        "ALL_TAGS_SUPPORTED",
        "All requested tags have confirmed supporting evidence.",
    ),
    "PARTIAL": (
        "SOME_TAGS_SUPPORTED",
        "Some requested tags have confirmed evidence; "
        "the remaining tags have insufficient evidence.",
    ),
    "GAP": (
        "EXPLICIT_NEGATIVE_CLAIM",
        "A requested skill has an explicit confirmed negative claim.",
    ),
    "UNKNOWN": (
        "INSUFFICIENT_EVIDENCE",
        "There is insufficient confirmed evidence for this requirement.",
    ),
}

WEIGHTS = {
    "REQUIRED": 2,
    "PREFERRED": 1,
}

VALUES = {
    "MATCHED": Decimal("1"),
    "PARTIAL": Decimal("0.5"),
    "GAP": Decimal("0"),
    "UNKNOWN": Decimal("0"),
}


def owner_evidence(profile, field, tag_id, value_summary):
    origin = profile["origins"].get(field, {
        "sourceType": "MANUAL",
        "documentId": None,
    })

    return {
        "field": field,
        "recordId": tag_id,
        "valueSummary": value_summary,
        "confirmedRevision": profile["revision"],
        "sourceType": origin["sourceType"],
        "documentId": origin["documentId"],
    }


def evaluate_requirement(requirement, profile):
    positive = []
    negative = []

    if requirement["kind"] == "SKILL":
        for tag_id in requirement["tagIds"]:
            skill = profile["skills"].get(tag_id)

            if skill is None:
                continue

            label = skill["label"]

            if skill["claim"] == "HAS":
                summary = (
                    f"Confirmed skill claim: {label}. "
                    + skill["evidenceText"]
                ).strip()

                positive.append(
                    owner_evidence(profile, "skills", tag_id, summary)
                )

            elif skill["claim"] == "DOES_NOT_HAVE":
                summary = (
                    f"Explicitly reports not having skill: {label}. "
                    + skill["evidenceText"]
                ).strip()

                negative.append(
                    owner_evidence(profile, "skills", tag_id, summary)
                )

    else:
        for tag_id in requirement["tagIds"]:
            label = profile["researchInterests"].get(tag_id)

            if label is not None:
                positive.append(
                    owner_evidence(
                        profile,
                        "researchInterests",
                        tag_id,
                        f"Confirmed research interest: {label}.",
                    )
                )

    if negative:
        status = "GAP"
        evidence = negative
    elif positive and len(positive) == len(requirement["tagIds"]):
        status = "MATCHED"
        evidence = positive
    elif positive:
        status = "PARTIAL"
        evidence = positive
    else:
        status = "UNKNOWN"
        evidence = []

    reason_code, reason = REASONS[status]

    return {
        "requirement": requirement,
        "status": status,
        "reasonCode": reason_code,
        "reason": reason,
        "evidence": evidence,
    }


def percentage(numerator, denominator):
    value = Decimal(100) * numerator / Decimal(denominator)

    return float(
        value.quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )
    )


def summarize(results):
    total_weight = sum(
        WEIGHTS[item["requirement"]["importance"]]
        for item in results
    )

    required_gaps = sum(
        item["requirement"]["importance"] == "REQUIRED"
        and item["status"] == "GAP"
        for item in results
    )

    if total_weight == 0:
        return {
            "score": None,
            "unknownWeightPercent": None,
            "requiredGapCount": required_gaps,
            "evaluationStatus": "INSUFFICIENT_CRITERIA",
            "algorithmVersion": "tag-coverage-v1",
        }

    earned = sum(
        (
            WEIGHTS[item["requirement"]["importance"]]
            * VALUES[item["status"]]
            for item in results
        ),
        Decimal("0"),
    )

    unknown_weight = sum(
        WEIGHTS[item["requirement"]["importance"]]
        for item in results
        if item["status"] == "UNKNOWN"
    )

    return {
        "score": percentage(earned, total_weight),
        "unknownWeightPercent": percentage(
            Decimal(unknown_weight), total_weight
        ),
        "requiredGapCount": required_gaps,
        "evaluationStatus": "EVALUATED",
        "algorithmVersion": "tag-coverage-v1",
    }

def evaluate_opportunity(opportunity, profile):
    results = [
        evaluate_requirement(requirement, profile)
        for requirement in opportunity["content"]["requirements"]
    ]

    return results, summarize(results)