"""Ordered persistence and public serialization; callers own the transaction."""

from collections import defaultdict

from sqlalchemy import delete, select

from ...db.models import OpportunityRequirement, RequirementTag
from ...db.opportunity_read import CONTENT_FIELDS, serialize, serialize_many

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
