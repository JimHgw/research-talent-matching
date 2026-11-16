"""Owner-scoped profile reads using the caller's Session."""

from sqlalchemy import select

from ...db.interests import profile_components
from ...db.models import (
    ProfileComponentOrigin,
    ProfileInterest,
    ProfileOrigin,
    TalentProfile,
)
from ...db.skills import read_skills_many
from ...shared.validation import ApiError


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
