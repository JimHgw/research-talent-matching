from sqlalchemy import select

from ...db.models import (
    Opportunity,
    PersonalInterestTag,
    ProfileInterest,
    ProfileOrigin,
    ProfilePersonalInterest,
    ProfileTextDetails,
    Tag,
    TalentProfile,
)
from ...db.opportunity_read import serialize, serialize_many
from ...db.skills import matching_skills, read_skills_many
from ...shared.validation import ApiError, validate
from ..opportunities import availability as opportunity_availability
from ..opportunities.queries import READ_BATCH_SIZE, filtered_rows


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
    interest_text = db.scalar(select(ProfileTextDetails.research_interest_text)
                              .where(ProfileTextDetails.talent_id == profile.talent_id))
    personal_tags = db.execute(select(PersonalInterestTag.id, PersonalInterestTag.label).join(
        ProfilePersonalInterest,
        (ProfilePersonalInterest.tag_id == PersonalInterestTag.id)
        & (ProfilePersonalInterest.talent_id == PersonalInterestTag.talent_id),
    ).where(ProfilePersonalInterest.talent_id == profile.talent_id)
      .order_by(ProfilePersonalInterest.position))
    return {
        "researchInterestText": interest_text or "",
        "customInterestTags": [{"id": key, "label": label} for key, label in personal_tags],
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


def list_published(db, filters=None, now=None):
    # Load every eligible candidate, with conditions applied before child reads.
    now = now if now is not None else opportunity_availability.utcnow()
    rows, _ = filtered_rows(db, select(Opportunity)
        .where(*opportunity_availability.active_predicates(now)).order_by(Opportunity.id), filters)
    return [item for start in range(0, len(rows), READ_BATCH_SIZE)
            for item in serialize_many(db, rows[start:start + READ_BATCH_SIZE], now)]


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
