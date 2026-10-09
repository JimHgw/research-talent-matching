from sqlalchemy import select

from ...db.models import (
    Opportunity,
    ProfileInterest,
    ProfileOrigin,
    ProfileSkill,
    Tag,
    TalentProfile,
)
from ...db.opportunity_read import serialize, serialize_many
from ...shared.validation import ApiError, validate


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
    skills = {}
    rows = db.execute(
        select(ProfileSkill, Tag.label)
        .join(Tag, ProfileSkill.tag_id == Tag.id)
        .where(ProfileSkill.talent_id == profile.talent_id)
        .order_by(ProfileSkill.position)
    )
    for skill, label in rows:
        skills[skill.tag_id] = {
            "claim": skill.claim,
            "evidenceText": skill.evidence_text,
            "label": label,
        }
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
        "revision": profile.revision,
        "skills": skills,
        "researchInterests": interests,
        "origins": origins,
    }


def list_published(db):
    # List all published opportunities, ordered by ID.
    rows = list(
        db.scalars(
            select(Opportunity)
            .where(Opportunity.status == "PUBLISHED")
            .order_by(Opportunity.id)
        )
    )

    return serialize_many(db, rows)


def get_published(db, opportunity_id):
    validate("Id", opportunity_id)
    opportunity = db.get(Opportunity, opportunity_id)

    if opportunity is None or opportunity.status != "PUBLISHED":
        raise ApiError(
            404, "NOT_FOUND", "Opportunity not found."
        )
    return serialize(db, opportunity)