"""US-01: owner-only full profile replacement and shared tag vocabulary."""

from flask import Blueprint, jsonify, request
from sqlalchemy import delete, select

from ...db.database import database
from ...db.interests import (COMPONENTS, TEXT_FIELDS, profile_components, replace_personal_selection,
                            resolve_personal_tags, set_component_origin, set_profile_text)
from ...db.models import ProfileComponentOrigin
from ...db.skills import check_skills, read_skills_many, replace_skills
from ...db.models import (ProfileInterest, ProfileOrigin, Tag, TagDisciplineGroup,
                          TalentProfile, utcnow)
from ...shared.security import require_csrf, require_user
from ...shared.validation import ApiError, body, invalid, validate

profiles = Blueprint("profiles", __name__, url_prefix="/api/v1")
SCALARS = {"displayName": "display_name", "disciplineGroup": "discipline_group"}
ARRAYS = {"education": "education", "courses": "courses", "researchExperience": "research_experience",
          "researchOutputs": "research_outputs"}
BASE_SECTIONS = (*ARRAYS, "skills", "researchInterests")
SECTIONS = (*BASE_SECTIONS, *COMPONENTS)


def timestamp(value):
    return value.isoformat(timespec="microseconds") + "Z" if value is not None else None


def serialize_profile(db, profile):
    content = {field: getattr(profile, attr) for field, attr in (SCALARS | ARRAYS).items()}
    content["skills"] = read_skills_many(db, [profile.talent_id])[profile.talent_id]
    content["researchInterests"] = list(db.scalars(
        select(ProfileInterest.tag_id).where(ProfileInterest.talent_id == profile.talent_id)
        .order_by(ProfileInterest.position)))
    content.update(profile_components(db, profile.talent_id))
    origins = [{"field": row.field, "sourceType": row.source_type, "documentId": row.document_id}
               for model in (ProfileOrigin, ProfileComponentOrigin)
               for row in db.scalars(select(model).where(model.talent_id == profile.talent_id))]
    return {
        "talentId": profile.talent_id, "revision": profile.revision, "content": content,
        "confirmation": {"status": profile.confirmation_status,
                         "confirmedRevision": profile.confirmed_revision,
                         "confirmedAt": timestamp(profile.confirmed_at)},
        "origins": sorted(origins, key=lambda item: item["field"]),
        "updatedAt": timestamp(profile.updated_at),
    }


def own_profile(db, user):
    profile = db.scalar(select(TalentProfile).where(TalentProfile.user_id == user.id))
    if profile is None:
        raise ApiError(404, "NOT_FOUND", "Profile not found.")
    return profile


def check_content(db, content):
    for section in BASE_SECTIONS:
        entries = content[section]
        if section == "skills":
            check_skills(entries, "content.skills")
            continue
        ids = entries if section == "researchInterests" else [row["id"] for row in entries]
        if len(ids) != len(set(ids)):
            invalid(f"content.{section}", "Each record or tag ID must be unique within the section.")
        if section == "researchInterests":
            expected = "INTEREST"
            for tag_id in ids:
                tag = db.get(Tag, tag_id)
                if tag is None or tag.kind != expected:
                    invalid(f"content.{section}", f"Select an existing {expected} tag.")


@profiles.get("/tags")
def tags_get():
    with database().transaction() as db:
        require_user(db)
        kind = request.args.get("kind")
        if kind is not None and kind not in ("SKILL", "INTEREST"):
            invalid("kind", "Choose SKILL or INTEREST.")
        query = select(Tag).order_by(Tag.id)
        if kind:
            query = query.where(Tag.kind == kind)
        items = [{"id": tag.id, "label": tag.label, "kind": tag.kind,
                  "disciplineGroups": list(db.scalars(select(TagDisciplineGroup.discipline_group)
                    .where(TagDisciplineGroup.tag_id == tag.id).order_by(TagDisciplineGroup.discipline_group)))}
                 for tag in db.scalars(query)]
    return jsonify(items=items)


@profiles.get("/me/profile")
def profile_get():
    with database().transaction() as db:
        _, user = require_user(db, "TALENT")
        result = serialize_profile(db, own_profile(db, user))
    return jsonify(result)


@profiles.put("/me/profile")
def profile_put():
    # Acquire the writer lock before reading expectedRevision, avoiding lost updates.
    with database().transaction(write=True) as db:
        session, user = require_user(db, "TALENT")
        require_csrf(session)
        data = body("ProfileWrite")
        profile = own_profile(db, user)
        if data["expectedRevision"] != profile.revision:
            raise ApiError(409, "REVISION_CONFLICT", "Your profile changed. Reload the latest version.",
                           revision=profile.revision)
        old = serialize_profile(db, profile)
        content = data["content"]
        for field in COMPONENTS:
            content.setdefault(field, old["content"][field])
        check_content(db, content)
        content["customInterestTags"], content["researchInterests"] = resolve_personal_tags(
            db, profile.talent_id, content["customInterestTags"], content["researchInterests"],
            "content.customInterestTags")
        if old["content"] == content:
            result = old
        else:
            for field, attr in (SCALARS | ARRAYS).items():
                setattr(profile, attr, content[field])
            profile.revision += 1
            profile.confirmation_status = "UNCONFIRMED"
            profile.confirmed_revision = profile.confirmed_at = None
            profile.updated_at = utcnow()
            for section in SECTIONS:
                if old["content"][section] != content[section]:
                    if section in COMPONENTS:
                        set_component_origin(db, profile.talent_id, section, "MANUAL")
                        continue
                    origin = db.get(ProfileOrigin, (profile.talent_id, section))
                    if origin is None:
                        origin = ProfileOrigin(talent_id=profile.talent_id, field=section)
                        db.add(origin)
                    origin.source_type, origin.document_id = "MANUAL", None
            db.execute(delete(ProfileInterest).where(ProfileInterest.talent_id == profile.talent_id))
            replace_skills(db, profile.talent_id, content["skills"])
            for position, tag_id in enumerate(content["researchInterests"]):
                db.add(ProfileInterest(talent_id=profile.talent_id, tag_id=tag_id, position=position))
            for field in TEXT_FIELDS:
                set_profile_text(db, profile.talent_id, field, content[field])
            replace_personal_selection(db, profile.talent_id, content["customInterestTags"])
            db.flush()
            result = serialize_profile(db, profile)
    return jsonify(result)

@profiles.post("/me/profile/confirmation")
def profile_confirm():
    with database().transaction(write=True) as db:
        # Check identity and request security information
        session, user = require_user(db, "TALENT")
        require_csrf(session)

        # Read request and current user's information
        profile = own_profile(db, user)
        data = body("RevisionRequest")

        # The version checked by the user must be the current version
        if data["expectedRevision"] != profile.revision:
            raise ApiError(
                409,
                "REVISION_CONFLICT",
                "Your profile changed. Reload the latest version.",
                revision=profile.revision,
            )

        # Check the name and information column
        current = serialize_profile(db, profile)
        content = current["content"]

        if not content["displayName"].strip():
            invalid(
                "content.displayName",
                "Enter your name before confirming."
            )

        if not any(content[section].strip() if isinstance(content[section], str) else content[section]
                   for section in SECTIONS):
            invalid(
                "content",
                "Add at least one academic or research record before confirming."
            )

        # Record the status and time during the first confirmation
        # Record the status and time during the first confirmation
        if current["confirmation"]["status"] != "CONFIRMED":
            now = utcnow()

            profile.confirmation_status = "CONFIRMED"
            profile.confirmed_revision = profile.revision
            profile.confirmed_at = now
            profile.updated_at = now

            db.flush()

        # Organize the returned data
        result = serialize_profile(db, profile)

    return jsonify(result)

def seed_tags(items):
    """Insert missing controlled vocabulary; never silently redefine an existing tag."""
    validate("TagList", {"items": items})
    if len({tag["id"] for tag in items}) != len(items):
        raise ValueError("Duplicate tag ID in seed file.")
    with database().transaction(write=True) as db:
        for item in items:
            existing = db.get(Tag, item["id"])
            if existing:
                groups = set(db.scalars(select(TagDisciplineGroup.discipline_group)
                             .where(TagDisciplineGroup.tag_id == existing.id)))
                if (existing.label != item["label"] or existing.kind != item["kind"]
                        or groups != set(item["disciplineGroups"])):
                    raise ValueError("An existing tag differs from the seed file.")
                continue
            db.add(Tag(id=item["id"], label=item["label"], kind=item["kind"]))
            db.flush()
            for group in item["disciplineGroups"]:
                db.add(TagDisciplineGroup(tag_id=item["id"], discipline_group=group))
