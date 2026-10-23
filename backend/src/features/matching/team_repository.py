"""Read only eligible talent and construct the team's visible profile boundary."""

from sqlalchemy import select

from ...db.models import (Opportunity, PrivacySettings, PrivacyVisibleField,
                          PersonalInterestTag, ProfileInterest, ProfileTextDetails,
                          ProfilePersonalInterest, ProfileSkill, TalentProfile, Tag, User)
from ...db.opportunity_read import serialize
from ...shared.validation import ApiError, validate

SCALARS = {"displayName": "display_name", "disciplineGroup": "discipline_group"}
RECORDS = {
    "education": ("education", ("id", "institution", "qualification", "discipline",
                                "startYear", "endYear")),
    "courses": ("courses", ("id", "name", "code", "description")),
    "researchExperience": ("research_experience", ("id", "title", "organisation", "description")),
    "researchOutputs": ("research_outputs", ("id", "title", "type", "url", "description")),
}


def own_published_opportunity(db, user, opportunity_id):
    validate("Id", opportunity_id)
    opportunity = db.scalar(select(Opportunity).where(
        Opportunity.id == opportunity_id,
        Opportunity.owner_user_id == user.id,
        Opportunity.status == "PUBLISHED",
    ))
    if opportunity is None:
        raise ApiError(404, "NOT_FOUND", "Opportunity not found.")
    return serialize(db, opportunity)


def discoverable_profiles(db, talent_id=None):
    query = (select(TalentProfile).join(PrivacySettings).join(User)
             .where(PrivacySettings.discoverable.is_(True),
                    TalentProfile.confirmation_status == "CONFIRMED",
                    TalentProfile.confirmed_revision == TalentProfile.revision,
                    User.role == "TALENT", User.active.is_(True))
             .order_by(TalentProfile.talent_id))
    if talent_id is not None:
        validate("Id", talent_id)
        query = query.where(TalentProfile.talent_id == talent_id)
    profiles = list(db.scalars(query))
    if talent_id is not None and not profiles:
        raise ApiError(404, "NOT_FOUND", "Talent profile not found.")
    return profiles


def visible_profiles(db, profiles):
    if not profiles:
        return []
    ids = [profile.talent_id for profile in profiles]
    allowed = {talent_id: set() for talent_id in ids}
    for talent_id, field in db.execute(select(
        PrivacyVisibleField.talent_id, PrivacyVisibleField.field
    ).where(PrivacyVisibleField.talent_id.in_(ids))):
        allowed[talent_id].add(field)

    visible = {}
    for profile in profiles:
        fields = {}
        for field, attr in SCALARS.items():
            if field in allowed[profile.talent_id]:
                fields[field] = getattr(profile, attr)
        for field, (attr, keys) in RECORDS.items():
            if field in allowed[profile.talent_id]:
                fields[field] = [{key: record[key] for key in keys}
                                 for record in getattr(profile, attr)]
        for field in ("skills", "researchInterests"):
            if field in allowed[profile.talent_id]:
                fields[field] = []
        if "researchInterests" in allowed[profile.talent_id]:
            fields["researchInterestText"] = ""
            fields["customInterestTags"] = []
        visible[profile.talent_id] = {"talentId": profile.talent_id, "fields": fields}

    # Filter child rows before reading them. No hidden claims or origins enter matching.
    for model, field in ((ProfileSkill, "skills"), (ProfileInterest, "researchInterests")):
        rows = db.scalars(select(model).join(
            PrivacyVisibleField,
            (PrivacyVisibleField.talent_id == model.talent_id)
            & (PrivacyVisibleField.field == field),
        ).where(model.talent_id.in_(ids)).order_by(model.talent_id, model.position))
        for row in rows:
            value = ({"tagId": row.tag_id, "claim": row.claim, "evidenceText": row.evidence_text}
                     if field == "skills" else row.tag_id)
            visible[row.talent_id]["fields"][field].append(value)
    interest_ids = [key for key in ids if "researchInterests" in allowed[key]]
    if interest_ids:
        # Select only the permitted interest column; never load the whole private resume description.
        for talent_id, interest_text in db.execute(select(ProfileTextDetails.talent_id, ProfileTextDetails.research_interest_text)
                                                   .where(ProfileTextDetails.talent_id.in_(interest_ids))):
            visible[talent_id]["fields"]["researchInterestText"] = interest_text
        rows = db.execute(select(ProfilePersonalInterest.talent_id, PersonalInterestTag).join(
            PersonalInterestTag,
            (ProfilePersonalInterest.tag_id == PersonalInterestTag.id)
            & (ProfilePersonalInterest.talent_id == PersonalInterestTag.talent_id),
        ).where(ProfilePersonalInterest.talent_id.in_(interest_ids))
          .order_by(ProfilePersonalInterest.talent_id, ProfilePersonalInterest.position))
        for talent_id, tag in rows:
            visible[talent_id]["fields"]["customInterestTags"].append({"id": tag.id, "label": tag.label})
    return list(visible.values())


def tag_labels(db):
    return dict(db.execute(select(Tag.id, Tag.label)).all())
