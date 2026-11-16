"""Profile and vocabulary persistence using the caller's Session."""

from sqlalchemy import delete, select

from ...db.interests import (
    COMPONENTS,
    TEXT_FIELDS,
    profile_components,
    replace_personal_selection,
    resolve_personal_tags,
    set_component_origin,
    set_profile_text,
)
from ...db.models import (
    ProfileComponentOrigin,
    ProfileInterest,
    ProfileOrigin,
    TalentProfile,
    Tag,
    TagDisciplineGroup,
)
from ...db.skills import read_skills_many, replace_skills
from ...shared.validation import ApiError
from .serialization import ARRAYS, SCALARS


def own_profile(db, user):
    profile = db.scalar(
        select(TalentProfile).where(TalentProfile.user_id == user.id)
    )
    if profile is None:
        raise ApiError(404, "NOT_FOUND", "Profile not found.")
    return profile


def load_profile_details(db, profile):
    talent_id = profile.talent_id

    skills = read_skills_many(db, [talent_id])[talent_id]
    interests = list(
        db.scalars(
            select(ProfileInterest.tag_id)
            .where(ProfileInterest.talent_id == talent_id)
            .order_by(ProfileInterest.position)
        )
    )
    components = profile_components(db, talent_id)
    origins = [
        {
            "field": row.field,
            "sourceType": row.source_type,
            "documentId": row.document_id,
        }
        for model in (ProfileOrigin, ProfileComponentOrigin)
        for row in db.scalars(
            select(model).where(model.talent_id == talent_id)
        )
    ]

    return {
        "skills": skills,
        "researchInterests": interests,
        "components": components,
        "origins": origins,
    }


def load_tag_kinds(db, tag_ids):
    if not tag_ids:
        return {}
    return dict(db.execute(select(Tag.id, Tag.kind).where(Tag.id.in_(tag_ids))).all())


def resolve_profile_personal_tags(db, profile, proposals, shared_ids):
    return resolve_personal_tags(
        db, profile.talent_id, proposals, shared_ids, "content.customInterestTags"
    )


def save_profile_content(db, profile, content, changed_sections):
    """Replace saved content and mark only changed components as manual."""
    for field, attr in (SCALARS | ARRAYS).items():
        setattr(profile, attr, content[field])
    for section in changed_sections:
        if section in COMPONENTS:
            set_component_origin(db, profile.talent_id, section, "MANUAL")
            continue
        origin = db.get(ProfileOrigin, (profile.talent_id, section))
        if origin is None:
            origin = ProfileOrigin(talent_id=profile.talent_id, field=section)
            db.add(origin)
        origin.source_type = "MANUAL"
        origin.document_id = None

    db.execute(delete(ProfileInterest).where(ProfileInterest.talent_id == profile.talent_id))
    replace_skills(db, profile.talent_id, content["skills"])
    for position, tag_id in enumerate(content["researchInterests"]):
        db.add(ProfileInterest(talent_id=profile.talent_id, tag_id=tag_id, position=position))
    for field in TEXT_FIELDS:
        set_profile_text(db, profile.talent_id, field, content[field])
    replace_personal_selection(db, profile.talent_id, content["customInterestTags"])


def load_tag_catalogue(db, kind=None):
    query = select(Tag).order_by(Tag.id)
    if kind:
        query = query.where(Tag.kind == kind)
    return [
        (tag, list(db.scalars(
            select(TagDisciplineGroup.discipline_group)
            .where(TagDisciplineGroup.tag_id == tag.id)
            .order_by(TagDisciplineGroup.discipline_group)
        )))
        for tag in db.scalars(query)
    ]


def seed_tag_rows(db, items):
    """Insert missing vocabulary without redefining existing tags."""
    for item in items:
        existing = db.get(Tag, item["id"])
        if existing:
            groups = set(db.scalars(
                select(TagDisciplineGroup.discipline_group)
                .where(TagDisciplineGroup.tag_id == existing.id)
            ))
            if (
                existing.label != item["label"]
                or existing.kind != item["kind"]
                or groups != set(item["disciplineGroups"])
            ):
                raise ValueError("An existing tag differs from the seed file.")
            continue
        db.add(Tag(id=item["id"], label=item["label"], kind=item["kind"]))
        db.flush()
        for group in item["disciplineGroups"]:
            db.add(TagDisciplineGroup(tag_id=item["id"], discipline_group=group))
