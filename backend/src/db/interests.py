"""Owner-scoped interest text/tags, shared by profile saves and reviewed imports."""

import unicodedata
from uuid import uuid4

from sqlalchemy import delete, select

from .models import (ProfileComponentOrigin, PersonalInterestTag, ProfileTextDetails,
                     ProfilePersonalInterest, Tag)
from ..shared.validation import invalid


COMPONENTS = ("researchInterestText", "customInterestTags", "resumeDescription")
TEXT_FIELDS = {"researchInterestText": "research_interest_text", "resumeDescription": "resume_description"}


def normalise_label(label):
    display = " ".join(unicodedata.normalize("NFKC", label).split())
    return display, display.casefold()


def profile_components(db, talent_id):
    details = db.get(ProfileTextDetails, talent_id)
    tags = db.scalars(select(PersonalInterestTag).join(
        ProfilePersonalInterest,
        (ProfilePersonalInterest.tag_id == PersonalInterestTag.id)
        & (ProfilePersonalInterest.talent_id == PersonalInterestTag.talent_id),
    ).where(ProfilePersonalInterest.talent_id == talent_id).order_by(ProfilePersonalInterest.position))
    return {"researchInterestText": details.research_interest_text if details else "",
            "resumeDescription": details.resume_description if details else "",
            "customInterestTags": [{"id": tag.id, "label": tag.label} for tag in tags]}


def resolve_personal_tags(db, talent_id, proposals, shared_ids, field):
    """Caller holds the write mutex and has checked ownership/current revision.

    Resolve exact shared labels, then only this owner's catalogue. Proposed labels
    create no rows until an authorised save/import calls this function.
    """
    owned = list(db.scalars(select(PersonalInterestTag).where(PersonalInterestTag.talent_id == talent_id)))
    by_id = {tag.id: tag for tag in owned}
    by_label = {tag.normalised_label: tag for tag in owned}
    shared = {}
    for tag in db.scalars(select(Tag).where(Tag.kind == "INTEREST").order_by(Tag.id)):
        shared.setdefault(normalise_label(tag.label)[1], tag.id)
    selected, resolved_shared, seen_labels, seen_ids = [], list(shared_ids), set(), {}
    plans = {}
    for index, proposal in enumerate(proposals):
        path = f"{field}.{index}"
        display, key = normalise_label(proposal["label"])
        if not display or len(display) > 100 or any(unicodedata.category(char).startswith("C") for char in display):
            invalid(path + ".label", "Enter a label of 1–100 visible characters.")
        tag_id = proposal.get("id")
        if tag_id is not None:
            if tag_id not in by_id:
                invalid(path + ".id", "Select one of your own personal interest tags.")
            if tag_id in seen_ids and seen_ids[tag_id] != key:
                invalid(path + ".id", "A personal tag ID cannot have conflicting labels.")
            seen_ids[tag_id] = key
        if key in seen_labels:
            continue
        seen_labels.add(key)
        if key in shared:
            if shared[key] not in resolved_shared:
                resolved_shared.append(shared[key])
            continue
        tag = by_label.get(key)
        if tag is None:
            tag = by_id.get(tag_id)
            if tag is None:
                tag = PersonalInterestTag(id="personal_" + uuid4().hex, talent_id=talent_id,
                                          label=display, normalised_label=key)
            canonical_display = display
        else:
            canonical_display = tag.label
        if tag.id in plans:
            if plans[tag.id][2] != key:
                invalid(path + ".id", "A personal tag cannot be selected with conflicting labels.")
            continue
        plans[tag.id] = (tag, canonical_display, key)
        selected.append(tag)
    if len(resolved_shared) + len(selected) > 100:
        invalid(field, "Select at most 100 shared and personal interest tags combined.")
    # Plan the entire selection before mutating catalogue rows, so aliases and
    # renames cannot create duplicate selections or transient uniqueness errors.
    new_tags = []
    for tag, display, key in plans.values():
        tag.label, tag.normalised_label = display, key
        if tag.id not in by_id:
            new_tags.append(tag)
    db.flush()
    db.add_all(new_tags)
    db.flush()
    return [{"id": tag.id, "label": tag.label} for tag in selected], resolved_shared


def replace_personal_selection(db, talent_id, entries):
    db.execute(delete(ProfilePersonalInterest).where(ProfilePersonalInterest.talent_id == talent_id))
    for position, entry in enumerate(entries):
        db.add(ProfilePersonalInterest(talent_id=talent_id, tag_id=entry["id"], position=position))


def set_profile_text(db, talent_id, field, text):
    details = db.get(ProfileTextDetails, talent_id)
    if details is None:
        details = ProfileTextDetails(talent_id=talent_id, research_interest_text="", resume_description="")
        db.add(details)
    setattr(details, TEXT_FIELDS[field], text)


def set_component_origin(db, talent_id, field, source_type, document_id=None):
    origin = db.get(ProfileComponentOrigin, (talent_id, field))
    if origin is None:
        origin = ProfileComponentOrigin(talent_id=talent_id, field=field,
                                         source_type=source_type, document_id=document_id)
        db.add(origin)
    else:
        origin.source_type, origin.document_id = source_type, document_id
