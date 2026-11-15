"""Validate resolved reviewed sections against loaded reference data."""

from ...db.interests import TEXT_FIELDS
from ...db.skills import check_skills
from ...shared.validation import invalid


def check_reviewed_sections(sections, tag_kinds):
    for section, entries in sections.items():
        if section in TEXT_FIELDS:
            continue

        if section == "skills":
            check_skills(entries, "sections.skills")
            continue

        if section == "researchInterests":
            ids = entries
        else:
            ids = [entry["id"] for entry in entries]

        if len(ids) != len(set(ids)):
            invalid(
                f"sections.{section}",
                "Each record or tag ID must be unique within the section.",
            )

        if section != "researchInterests":
            continue

        for tag_id in ids:
            if tag_kinds.get(tag_id) != "INTEREST":
                invalid(
                    f"sections.{section}",
                    "Select an existing INTEREST tag.",
                )
