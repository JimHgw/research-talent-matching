"""Document reads and reviewed writes using the caller's Session."""

from sqlalchemy import delete, select

from ...db.interests import (
    COMPONENTS,
    TEXT_FIELDS,
    replace_personal_selection,
    resolve_personal_tags,
    set_component_origin,
    set_profile_text,
)
from ...db.models import (
    Document,
    DocumentExtraction,
    ProfileInterest,
    ProfileOrigin,
    Tag,
    TalentProfile,
)
from ...db.skills import replace_skills
from ...shared.validation import ApiError, invalid, validator


def own_document(db, user, document_id):
    if not validator("Id").is_valid(document_id):
        invalid(
            "documentId",
            "Use an ID of 1–64 letters, digits, underscores or hyphens.",
        )

    document = db.scalar(
        select(Document)
        .join(TalentProfile)
        .where(
            Document.id == document_id,
            TalentProfile.user_id == user.id,
        )
    )
    if document is None:
        raise ApiError(404, "NOT_FOUND", "Document not found.")
    return document


def get_extraction(db, document_id):
    return db.get(DocumentExtraction, document_id)


def load_tag_kinds(db, tag_ids):
    if not tag_ids:
        return {}
    return dict(
        db.execute(
            select(Tag.id, Tag.kind).where(Tag.id.in_(tag_ids))
        ).all()
    )


def resolve_reviewed_personal_tags(db, profile, proposals, shared_ids):
    return resolve_personal_tags(
        db,
        profile.talent_id,
        proposals,
        shared_ids,
        "sections.customInterestTags",
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
                replace_personal_selection(
                    db, profile.talent_id, entries
                )
            set_component_origin(
                db,
                profile.talent_id,
                section,
                "USER_REVIEWED_DOCUMENT",
                document_id,
            )
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
            replace_skills(db, profile.talent_id, entries)
        elif section == "researchInterests":
            replace_reviewed_interests(db, profile, entries)

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
