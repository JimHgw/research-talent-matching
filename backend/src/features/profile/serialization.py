"""Build owner-profile responses from already loaded data."""

SCALARS = {
    "displayName": "display_name",
    "disciplineGroup": "discipline_group",
}
ARRAYS = {
    "education": "education",
    "courses": "courses",
    "researchExperience": "research_experience",
    "researchOutputs": "research_outputs",
}


def timestamp(value):
    if value is None:
        return None
    return value.isoformat(timespec="microseconds") + "Z"


def serialize_profile(profile, details):
    content = {
        field: getattr(profile, attr)
        for field, attr in (SCALARS | ARRAYS).items()
    }
    content["skills"] = details["skills"]
    content["researchInterests"] = details["researchInterests"]
    content.update(details["components"])

    return {
        "talentId": profile.talent_id,
        "revision": profile.revision,
        "content": content,
        "confirmation": {
            "status": profile.confirmation_status,
            "confirmedRevision": profile.confirmed_revision,
            "confirmedAt": timestamp(profile.confirmed_at),
        },
        "origins": sorted(
            details["origins"],
            key=lambda item: item["field"],
        ),
        "updatedAt": timestamp(profile.updated_at),
    }


def serialize_tag_catalogue(rows):
    return [
        {
            "id": tag.id,
            "label": tag.label,
            "kind": tag.kind,
            "disciplineGroups": groups,
        }
        for tag, groups in rows
    ]
