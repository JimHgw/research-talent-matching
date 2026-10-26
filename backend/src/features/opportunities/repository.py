"""Ordered persistence and public serialization; callers own the transaction."""

from sqlalchemy import delete

from ...db.models import OpportunityRequirement, OpportunitySkillDetails, RequirementTag
from ...db.opportunity_read import CONTENT_FIELDS, serialize, serialize_many
from ...shared.search import parse_datetime

def replace_content(db, opportunity, content):
    for field, attr in CONTENT_FIELDS.items():
        setattr(opportunity, attr, content[field])
    if "opportunityType" in content:
        opportunity.opportunity_type = content["opportunityType"]
    if "deadlineAt" in content:
        opportunity.deadline_at = (parse_datetime(content["deadlineAt"], "content.deadlineAt")
                                   if content["deadlineAt"] is not None else None)
    db.flush()
    # Delete dependent rows first; independent tags and accounts are never deleted.
    db.execute(delete(RequirementTag).where(RequirementTag.opportunity_id == opportunity.id))
    db.execute(delete(OpportunitySkillDetails).where(OpportunitySkillDetails.opportunity_id == opportunity.id))
    db.execute(delete(OpportunityRequirement).where(OpportunityRequirement.opportunity_id == opportunity.id))
    for position, requirement in enumerate(content["requirements"]):
        db.add(OpportunityRequirement(
            opportunity_id=opportunity.id, id=requirement["id"], label=requirement["label"],
            kind=requirement["kind"], importance=requirement["importance"], position=position))
    db.flush()
    for requirement in content["requirements"]:
        if "skillTitles" in requirement:
            db.add(OpportunitySkillDetails(opportunity_id=opportunity.id,
                                          requirement_id=requirement["id"], titles=requirement["skillTitles"]))
        for position, tag_id in enumerate(requirement["tagIds"]):
            db.add(RequirementTag(opportunity_id=opportunity.id, requirement_id=requirement["id"],
                                  tag_id=tag_id, position=position))
    db.flush()
