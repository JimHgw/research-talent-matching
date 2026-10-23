"""Validate and save user-reviewed document sections."""

from ...db.models import ProfileInterest, ProfileOrigin, ProfileSkill, Tag
from ...db.interests import (COMPONENTS, TEXT_FIELDS, replace_personal_selection, set_component_origin,
                            set_profile_text)
from ...shared.validation import invalid
from sqlalchemy import delete

def check_reviewed_sections(db, sections):
    for section, entries in sections.items():
        if section in TEXT_FIELDS:
            continue
        if section == "researchInterests":
            ids = entries
        elif section == "skills":
            ids = [entry["tagId"] for entry in entries]
        else:
            ids = [entry["id"] for entry in entries]

        if len(ids) != len(set(ids)):
            invalid(
                f"sections.{section}",
                "Each record or tag ID must be unique within the section.",
            )

        if section not in ("skills", "researchInterests"):
            continue

        if section == "skills":
            expected = "SKILL"
        else:
            expected = "INTEREST"

        for tag_id in ids:
            tag = db.get(Tag, tag_id)

            if tag is None or tag.kind != expected:
                invalid(
                    f"sections.{section}",
                    f"Select an existing {expected} tag.",
                )

def replace_reviewed_skills(db, profile, skills):
    db.execute(
        delete(ProfileSkill).where(
            ProfileSkill.talent_id == profile.talent_id
        )
    )

    for position, skill in enumerate(skills):
        db.add(
            ProfileSkill(
                talent_id=profile.talent_id,
                tag_id=skill["tagId"],
                claim=skill["claim"],
                evidence_text=skill["evidenceText"],
                position=position,
            )
        )


def replace_reviewed_interests(db, profile, interests):
    db.execute(
        delete(ProfileInterest).where(
            ProfileInterest.talent_id == profile.talent_id
        )
    )

    for position, tag_id in enumerate(interests):
        db.add(
            ProfileInterest(
                talent_id=profile.talent_id,
                tag_id=tag_id,
                position=position,
            )
        )

def save_reviewed_sections(db, profile, sections, document_id):
    for section, entries in sections.items():
        if section in COMPONENTS:
            if section in TEXT_FIELDS:
                set_profile_text(db, profile.talent_id, section, entries)
            else:
                replace_personal_selection(db, profile.talent_id, entries)
            set_component_origin(db, profile.talent_id, section, "USER_REVIEWED_DOCUMENT", document_id)
            continue
        if section == "education":
            profile.education = entries

        elif section == "courses":
            profile.courses = entries

        elif section == "researchExperience":
            profile.research_experience = entries

        elif section == "researchOutputs":
            profile.research_outputs = entries

        elif section == "skills":
            replace_reviewed_skills(db, profile, entries)

        elif section == "researchInterests":
            replace_reviewed_interests(db, profile, entries)

        # Record the source of each submitted section.
        origin = db.get(
            ProfileOrigin,
            (profile.talent_id, section),
        )

        if origin is None:
            origin = ProfileOrigin(
                talent_id=profile.talent_id,
                field=section,
            )
            db.add(origin)

        origin.source_type = "USER_REVIEWED_DOCUMENT"
        origin.document_id = document_id
