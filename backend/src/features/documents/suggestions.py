"""Build extraction suggestions for user review."""


def new_extraction_result(document_id):
    return {
        "documentId": document_id,
        "status": "READY",
        "suggestedSections": {},
        "uncertainFields": [],
        "warnings": [
            "Review all suggestions before saving."
        ],
        "reviewRequired": True,
    }

def find_skill_suggestions(text, tags):
    suggestions = []
    seen = set()

    for line in text.splitlines():
        line = line.strip()

        # Evidence must fit the API's length limit.
        if len(line) > 2000:
            continue

        header, separator, values = line.partition(":")

        if not separator:
            continue

        if header.strip().casefold() not in (
            "skills",
            "technical skills",
            "programming skills",
        ):
            continue

        names = {
            name.strip().casefold()
            for name in values.replace(";", ",").split(",")
        }

        for tag in tags:
            if tag["kind"] != "SKILL":
                continue

            if tag["label"].casefold() not in names:
                continue

            if tag["id"] in seen:
                continue

            suggestions.append(
                {
                    "tagId": tag["id"],
                    "claim": "HAS",
                    "evidenceText": line,
                }
            )
            seen.add(tag["id"])

            if len(suggestions) >= 100:
                return suggestions

    return suggestions

def find_interest_suggestions(text, tags):
    suggestions = []

    for line in text.splitlines():
        header, separator, values = line.partition(":")


        if not separator:
            continue

        if header.strip().casefold() not in (
            "research interests",
            "research interest",
            "interests",
        ):
            continue

        names = {
            name.strip().casefold()
            for name in values.replace(";", ",").split(",")
        }

        for tag in tags:
            if tag["kind"] != "INTEREST":
                continue

            if tag["label"].casefold() not in names:
                continue

            if tag["id"] in suggestions:
                continue

            suggestions.append(tag["id"])

            if len(suggestions) >= 100:
                return suggestions

    return suggestions

def build_extraction_result(document_id, text, tags):
    result = new_extraction_result(document_id)

    skills = find_skill_suggestions(text, tags)
    interests = find_interest_suggestions(text, tags)

    if skills:
        result["suggestedSections"]["skills"] = skills

    if interests:
        result["suggestedSections"]["researchInterests"] = interests

    for section in (
        "education",
        "courses",
        "researchExperience",
        "skills",
        "researchInterests",
        "researchOutputs",
    ):
        if not result["suggestedSections"].get(section):
            result["uncertainFields"].append(
                {
                    "field": section,
                    "status": "NOT_RECOGNISED",
                    "reason": (
                        "No reliable information was recognised "
                        "for this section."
                    ),
                }
            )
    if not text.strip():
        result["warnings"].append(
            "No readable text was found. Enter information manually."
        )

    return result