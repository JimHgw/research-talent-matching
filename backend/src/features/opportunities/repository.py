"""Ordered persistence and public serialization; callers own the transaction."""

from collections import defaultdict

from sqlalchemy import delete, select

from ...db.models import OpportunityRequirement, RequirementTag

CONTENT_FIELDS = {
    "title": "title", "university": "university", "disciplineGroup": "discipline_group",
    "discipline": "discipline", "researchArea": "research_area", "description": "description",
}


def serialize_many(db, opportunities):
    """Batch child reads so a list does not query once per requirement/tag."""
    ids = [row.id for row in opportunities]
    if not ids:
        return []
    tags = defaultdict(list)
    for row in db.scalars(select(RequirementTag).where(RequirementTag.opportunity_id.in_(ids))
                         .order_by(RequirementTag.position)):
        tags[(row.opportunity_id, row.requirement_id)].append(row.tag_id)
    requirements = defaultdict(list)
    for row in db.scalars(select(OpportunityRequirement)
                         .where(OpportunityRequirement.opportunity_id.in_(ids))
                         .order_by(OpportunityRequirement.position)):
        requirements[row.opportunity_id].append({
            "id": row.id, "label": row.label, "kind": row.kind, "importance": row.importance,
            "tagIds": tags[(row.opportunity_id, row.id)],
        })
    return [{
        "id": row.id, "revision": row.revision, "status": row.status,
        "content": {**{field: getattr(row, attr) for field, attr in CONTENT_FIELDS.items()},
                    "requirements": requirements[row.id]},
        "createdAt": row.created_at.isoformat(timespec="microseconds") + "Z",
        "updatedAt": row.updated_at.isoformat(timespec="microseconds") + "Z",
    } for row in opportunities]


def serialize(db, opportunity):
    return serialize_many(db, [opportunity])[0]


def replace_content(db, opportunity, content):
    for field, attr in CONTENT_FIELDS.items():
        setattr(opportunity, attr, content[field])
    db.flush()
    # Delete dependent rows first; independent tags and accounts are never deleted.
    db.execute(delete(RequirementTag).where(RequirementTag.opportunity_id == opportunity.id))
    db.execute(delete(OpportunityRequirement).where(OpportunityRequirement.opportunity_id == opportunity.id))
    for position, requirement in enumerate(content["requirements"]):
        db.add(OpportunityRequirement(
            opportunity_id=opportunity.id, id=requirement["id"], label=requirement["label"],
            kind=requirement["kind"], importance=requirement["importance"], position=position))
    db.flush()
    for requirement in content["requirements"]:
        for position, tag_id in enumerate(requirement["tagIds"]):
            db.add(RequirementTag(opportunity_id=opportunity.id, requirement_id=requirement["id"],
                                  tag_id=tag_id, position=position))
    db.flush()
