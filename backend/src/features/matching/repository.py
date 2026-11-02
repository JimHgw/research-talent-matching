from sqlalchemy import select

from ...db.models import (
    Opportunity,
    ProfileInterest,
    ProfileOrigin,
    Tag,
    TalentProfile,
)
from ...db.opportunity_read import serialize, serialize_many
from ...db.skills import matching_skills, read_skills_many
from ...db.interests import profile_components
from ...shared.validation import ApiError, validate
from ..opportunities import availability as opportunity_availability


def get_owner_profile(db, user):
    # Get the profile for the given user, or raise a 404 error if not found.
    profile = db.scalar(
        select(TalentProfile).where(
            TalentProfile.user_id == user.id
        )
    )

    if profile is None:
        raise ApiError(404, "NOT_FOUND", "Profile not found.")

    return profile


def read_matching_profile(db, profile):
    # Read the profile's skills, research interests, and origins in a single transaction.
    skill_records = read_skills_many(db, [profile.talent_id])[profile.talent_id]
    labels = dict(db.execute(select(Tag.id, Tag.label)).all())
    skills = matching_skills(skill_records, labels)
    interests = dict(
        db.execute(
            select(ProfileInterest.tag_id, Tag.label)
            .join(Tag, ProfileInterest.tag_id == Tag.id)
            .where(ProfileInterest.talent_id == profile.talent_id)
            .order_by(ProfileInterest.position)
        ).all()
    )
    origins = {
        row.field: {
            "sourceType": row.source_type,
            "documentId": row.document_id,
        }
        for row in db.scalars(
            select(ProfileOrigin).where(
                ProfileOrigin.talent_id == profile.talent_id
            )
        )
    }
    return {
        **{key: value for key, value in profile_components(db, profile.talent_id).items()
           if key in ("researchInterestText", "customInterestTags")},
        "revision": profile.revision,
        "skills": skills,
        "skillRecords": skill_records,
        "tagLabels": labels,
        "researchInterests": interests,
        "origins": origins,
        "education": profile.education,
        "researchExperience": profile.research_experience,
        "researchOutputs": profile.research_outputs,
    }


def list_published(db):
    # List all published opportunities, ordered by ID.
    now = opportunity_availability.utcnow()
    rows = list(
        db.scalars(
            select(Opportunity)
            .where(*opportunity_availability.active_predicates(now))
            .order_by(Opportunity.id)
        )
    )

    return serialize_many(db, rows, now)


def get_published(db, opportunity_id, *, active=False):
    now = opportunity_availability.utcnow()
    validate("Id", opportunity_id)
    opportunity = db.get(Opportunity, opportunity_id)

    if opportunity is None or opportunity.status != "PUBLISHED":
        raise ApiError(
            404, "NOT_FOUND", "Opportunity not found."
        )
    if active:
        opportunity_availability.require_active(opportunity, now)
    return serialize(db, opportunity, now)
