from collections import defaultdict

from sqlalchemy import select

from .models import OpportunityRequirement, OpportunitySkillDetails, RequirementTag

CONTENT_FIELDS = {
    "title": "title", "university": "university", "disciplineGroup": "discipline_group",
    "discipline": "discipline", "researchArea": "research_area", "description": "description",
}


def serialize_many(db, opportunities, now=None):
    """Batch child reads so a list does not query once per requirement/tag."""
    from ..features.opportunities.availability import availability, utcnow
    now = now if now is not None else utcnow()
    ids = [row.id for row in opportunities]
    if not ids:
        return []
    tags = defaultdict(list)
    for row in db.scalars(select(RequirementTag).where(RequirementTag.opportunity_id.in_(ids))
                         .order_by(RequirementTag.position)):
        tags[(row.opportunity_id, row.requirement_id)].append(row.tag_id)
    skill_titles = {(row.opportunity_id, row.requirement_id): row.titles
                    for row in db.scalars(select(OpportunitySkillDetails)
                                          .where(OpportunitySkillDetails.opportunity_id.in_(ids)))}
    requirements = defaultdict(list)
    for row in db.scalars(select(OpportunityRequirement)
                         .where(OpportunityRequirement.opportunity_id.in_(ids))
                         .order_by(OpportunityRequirement.position)):
        requirements[row.opportunity_id].append({
            "id": row.id, "label": row.label, "kind": row.kind, "importance": row.importance,
            "tagIds": tags[(row.opportunity_id, row.id)],
            **({"skillTitles": skill_titles[(row.opportunity_id, row.id)]}
               if (row.opportunity_id, row.id) in skill_titles else {}),
            **(
                {"criteria": row.criteria}
                if row.criteria is not None
                else {}
            ),
        })
    return [{
        "id": row.id, "revision": row.revision, "status": row.status,
        "availabilityStatus": availability(row, now),
        "content": {**{field: getattr(row, attr) for field, attr in CONTENT_FIELDS.items()},
                    **({"opportunityType": row.opportunity_type} if row.opportunity_type is not None else {}),
                    **({"deadlineAt": row.deadline_at.isoformat(timespec="microseconds") + "Z"}
                       if row.deadline_at is not None else {}),
                    "requirements": requirements[row.id]},
        "createdAt": row.created_at.isoformat(timespec="microseconds") + "Z",
        "updatedAt": row.updated_at.isoformat(timespec="microseconds") + "Z",
    } for row in opportunities]


def serialize(db, opportunity, now=None):
    return serialize_many(db, [opportunity], now)[0]
