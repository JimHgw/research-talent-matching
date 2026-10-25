from ...db.skills import normalise_title


ACADEMIC_FIELDS = {
    "EDUCATION": "education",
    "RESEARCH_EXPERIENCE": "researchExperience",
    "RESEARCH_OUTPUT": "researchOutputs",
}

ACADEMIC_REASONS = {
    "MATCHED": (
        "ACADEMIC_CRITERIA_SUPPORTED",
        "A confirmed record supports all structured criteria.",
    ),
    "PARTIAL": (
        "ACADEMIC_CRITERIA_PARTIAL",
        "Some criteria have supporting evidence, but no single "
        "record confirms all criteria.",
    ),
    "UNKNOWN": (
        "INSUFFICIENT_EVIDENCE",
        "There is insufficient confirmed evidence for this requirement.",
    ),
}


def evaluate_academic(requirement, profile, evidence_factory):
    field = ACADEMIC_FIELDS[requirement["kind"]]
    criteria = requirement.get("criteria")

    if (
        not isinstance(criteria, dict)
        or not criteria
        or any(
            not isinstance(value, str) or not normalise_title(value)
            for value in criteria.values()
        )
    ):
        return {
            "requirement": requirement,
            "status": "UNKNOWN",
            "reasonCode": "INSUFFICIENT_EVIDENCE",
            "reason": "This requirement has no valid structured criteria.",
            "evidence": [],
        }

    full_matches = []
    partial_matches = []

    for record in profile.get(field, []):
        matched_keys = [
            key
            for key, expected in criteria.items()
            if normalise_title(str(record.get(key) or ""))
            == normalise_title(expected)
        ]

        if len(matched_keys) == len(criteria):
            full_matches.append((record, matched_keys))
        elif matched_keys:
            partial_matches.append((record, matched_keys))

    if full_matches:
        status = "MATCHED"
        selected = full_matches
    elif partial_matches:
        status = "PARTIAL"
        selected = partial_matches
    else:
        status = "UNKNOWN"
        selected = []

    evidence = []

    for record, matched_keys in selected:
        # Create a summary of the record and the matched fields.
        title = record.get("title") or record.get("qualification") or ""
        details = "; ".join(
            f"{key}: {record[key]}"
            for key in matched_keys
        )

        summary = f"{title}. Supporting fields: {details}"

        evidence.append(
            evidence_factory(
                profile,
                field,
                record["id"],
                summary,
            )
        )

    reason_code, reason = ACADEMIC_REASONS[status]

    return {
        "requirement": requirement,
        "status": status,
        "reasonCode": reason_code,
        "reason": reason,
        "evidence": evidence,
    }