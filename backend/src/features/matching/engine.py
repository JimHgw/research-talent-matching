from decimal import Decimal, ROUND_HALF_UP

from ...db.skills import matching_skills


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


def team_evidence(profile, field, tag_id, value_summary):
    # Construct the smaller audience-specific shape; never load owner provenance.
    return {"field": field, "recordId": tag_id, "valueSummary": value_summary}


def evaluate_requirement(requirement, profile, evidence_factory=owner_evidence):
    positive = []
    negative = []

    if requirement["kind"] == "SKILL":
        titles = requirement.get("skillTitles")
        criteria = titles if titles is not None else requirement["tagIds"]
        skills = (matching_skills(profile.get("skillRecords", []), {title: title for title in titles})
                  if titles is not None else profile["skills"])
        for tag_id in criteria:
            skill = skills.get(tag_id)

            if skill is None:
                continue

            label = skill["label"]

            if skill["claim"] == "HAS":
                summary = (
                    f"Confirmed skill claim: {label}. "
                    + skill["evidenceText"]
                ).strip()

                positive.append(
                    evidence_factory(profile, "skills", skill.get("id", tag_id), summary)
                )

            elif skill["claim"] == "DOES_NOT_HAVE":
                summary = (
                    f"Explicitly reports not having skill: {label}. "
                    + skill["evidenceText"]
                ).strip()

                negative.append(
                    evidence_factory(profile, "skills", skill.get("id", tag_id), summary)
                )

    else:
        for tag_id in requirement["tagIds"]:
            label = profile["researchInterests"].get(tag_id)

            if label is not None:
                positive.append(
                    evidence_factory(
                        profile,
                        "researchInterests",
                        tag_id,
                        f"Confirmed research interest: {label}.",
                    )
                )

    if negative:
        status = "GAP"
        evidence = negative
    elif positive and len(positive) == len(requirement.get("skillTitles", requirement["tagIds"])):
        status = "MATCHED"
        evidence = positive
    elif positive:
        status = "PARTIAL"
        evidence = positive
    else:
        status = "UNKNOWN"
        evidence = []

    reason_code, reason = REASONS[status]
    if "skillTitles" in requirement:
        reason_code, reason = {
            "MATCHED": ("ALL_SKILLS_SUPPORTED", "All requested skills have confirmed supporting evidence."),
            "PARTIAL": ("SOME_SKILLS_SUPPORTED", "Some requested skills have confirmed evidence; the remaining skills have insufficient evidence."),
            "GAP": REASONS["GAP"],
            "UNKNOWN": REASONS["UNKNOWN"],
        }[status]

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

def evaluate_opportunity(opportunity, profile, evidence_factory=owner_evidence):
    results = [
        evaluate_requirement(requirement, profile, evidence_factory)
        for requirement in opportunity["content"]["requirements"]
    ]

    summary = summarize(results)
    if any("skillTitles" in result["requirement"] for result in results):
        summary["algorithmVersion"] = "skill-title-interest-tags-v2"
    return results, summary
