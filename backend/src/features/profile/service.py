"""Owner profile operations using explicit inputs and the caller's Session."""

from copy import deepcopy

from ...db.database import require_write_lock
from ...db.interests import COMPONENTS
from ...db.models import utcnow
from ...db.skills import check_skills
from ...shared.validation import ApiError, invalid, validate
from . import repository
from .serialization import ARRAYS, serialize_profile
from .state import mark_profile_changed

BASE_SECTIONS = (*ARRAYS, "skills", "researchInterests")
SECTIONS = (*BASE_SECTIONS, *COMPONENTS)


def _check_revision(profile, expected_revision):
    if expected_revision != profile.revision:
        raise ApiError(
            409,
            "REVISION_CONFLICT",
            "Your profile changed. Reload the latest version.",
            revision=profile.revision,
        )


def _check_content(content, tag_kinds):
    for section in BASE_SECTIONS:
        entries = content[section]
        if section == "skills":
            check_skills(entries, "content.skills")
            continue
        ids = entries if section == "researchInterests" else [row["id"] for row in entries]
        if len(ids) != len(set(ids)):
            invalid(f"content.{section}", "Each record or tag ID must be unique within the section.")
        if section == "researchInterests":
            for tag_id in ids:
                if tag_kinds.get(tag_id) != "INTEREST":
                    invalid(f"content.{section}", "Select an existing INTEREST tag.")


def _profile_result(db, profile):
    return serialize_profile(profile, repository.load_profile_details(db, profile))


def save_profile(db, user, *, expected_revision, content):
    """Save canonical content within the caller's protected write transaction.

    The caller authenticates/authorizes the actor. Propagate errors through
    that transaction so tag resolution and all profile writes roll back together.
    An ordinary no-op preserves revision, confirmation, timestamps and origins.
    """
    require_write_lock(db)
    data = validate(
        "ProfileWrite",
        {"expectedRevision": expected_revision, "content": deepcopy(content)},
    )
    profile = repository.own_profile(db, user)
    _check_revision(profile, data["expectedRevision"])

    previous = _profile_result(db, profile)
    submitted = data["content"]
    for field in COMPONENTS:
        submitted.setdefault(field, previous["content"][field])
    _check_content(
        submitted,
        repository.load_tag_kinds(db, submitted["researchInterests"]),
    )
    personal, shared = repository.resolve_profile_personal_tags(
        db, profile, submitted["customInterestTags"], submitted["researchInterests"]
    )
    submitted["customInterestTags"] = personal
    submitted["researchInterests"] = shared
    if previous["content"] == submitted:
        return previous

    changed_sections = [
        section for section in SECTIONS
        if previous["content"][section] != submitted[section]
    ]
    mark_profile_changed(profile)
    repository.save_profile_content(db, profile, submitted, changed_sections)
    db.flush()
    return _profile_result(db, profile)


def confirm_profile(db, user, *, expected_revision):
    """Confirm the submitted current revision; repeated confirmation is stable."""
    require_write_lock(db)
    profile = repository.own_profile(db, user)
    data = validate("RevisionRequest", {"expectedRevision": expected_revision})
    _check_revision(profile, data["expectedRevision"])
    current = _profile_result(db, profile)
    content = current["content"]
    if not content["displayName"].strip():
        invalid("content.displayName", "Enter your name before confirming.")
    if not any(
        content[section].strip() if isinstance(content[section], str) else content[section]
        for section in SECTIONS
    ):
        invalid("content", "Add at least one academic or research record before confirming.")

    if current["confirmation"]["status"] != "CONFIRMED":
        now = utcnow()
        profile.confirmation_status = "CONFIRMED"
        profile.confirmed_revision = profile.revision
        profile.confirmed_at = now
        profile.updated_at = now
        db.flush()
    return _profile_result(db, profile)
