"""Application operation for importing user-reviewed document sections."""

from copy import deepcopy

from ...db.models import utcnow
from ...shared.validation import ApiError, invalid, validate
from ..profile.repository import load_profile_details, own_profile
from ..profile.serialization import serialize_profile
from . import repository
from .review import check_reviewed_sections


def apply_reviewed_extraction(
    db,
    user,
    document_id,
    *,
    expected_profile_revision,
    sections,
):
    """Import reviewed sections within the caller's protected transaction.

    The caller authenticates/authorizes the actor and establishes the write
    transaction before invoking this operation. Exceptions must propagate
    through that transaction so all changes roll back together.
    """
    document = repository.own_document(db, user, document_id)

    data = validate(
        "ApplyExtractionRequest",
        {
            "expectedProfileRevision": expected_profile_revision,
            "sections": deepcopy(sections),
        },
    )
    reviewed = data["sections"]

    if document.status in ("QUEUED", "PROCESSING"):
        raise ApiError(
            409,
            "EXTRACTION_NOT_READY",
            "The document is still being processed.",
        )

    if document.status == "FAILED":
        raise ApiError(
            422,
            "EXTRACTION_FAILED",
            "The document could not be processed.",
        )

    profile = own_profile(db, user)

    if data["expectedProfileRevision"] != profile.revision:
        raise ApiError(
            409,
            "REVISION_CONFLICT",
            "Your profile changed. Reload the latest version.",
            revision=profile.revision,
        )

    if "customInterestTags" in reviewed:
        current = load_profile_details(db, profile)
        personal, shared = repository.resolve_reviewed_personal_tags(
            db,
            profile,
            reviewed["customInterestTags"],
            reviewed.get(
                "researchInterests",
                current["researchInterests"],
            ),
        )
        reviewed["customInterestTags"] = personal
        if (
            "researchInterests" in reviewed
            or shared != current["researchInterests"]
        ):
            reviewed["researchInterests"] = shared

    elif "researchInterests" in reviewed:
        current = load_profile_details(db, profile)
        personal = current["components"]["customInterestTags"]
        if len(reviewed["researchInterests"]) + len(personal) > 100:
            invalid(
                "sections.researchInterests",
                "Select at most 100 shared and personal interest tags combined.",
            )

    tag_kinds = repository.load_tag_kinds(
        db, reviewed.get("researchInterests", [])
    )
    check_reviewed_sections(reviewed, tag_kinds)

    profile.revision += 1
    profile.confirmation_status = "UNCONFIRMED"
    profile.confirmed_revision = None
    profile.confirmed_at = None
    profile.updated_at = utcnow()

    repository.save_reviewed_sections(
        db, profile, reviewed, document.id
    )
    db.flush()

    return serialize_profile(
        profile, load_profile_details(db, profile)
    )
