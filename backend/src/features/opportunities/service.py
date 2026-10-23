"""Opportunity visibility, validation and lifecycle, independent of HTTP handlers."""

import secrets
import unicodedata

from sqlalchemy import func, select

from ...db.models import Opportunity, Tag, utcnow
from ...db.skills import normalise_title
from ...shared.validation import ApiError, invalid, validate
from .repository import replace_content, serialize, serialize_many


def published_opportunities():
    """Shared selection for discovery and future matching; drafts are excluded."""
    return select(Opportunity).where(Opportunity.status == "PUBLISHED")


def get_opportunity(db, user, opportunity_id, *, owner_only=False):
    validate("Id", opportunity_id)
    opportunity = db.get(Opportunity, opportunity_id)
    if opportunity is None or (opportunity.owner_user_id != user.id and
                               (owner_only or opportunity.status != "PUBLISHED")):
        raise ApiError(404, "NOT_FOUND", "Opportunity not found.")
    return opportunity


def list_opportunities(db, user, scope, page, page_size):
    if scope == "mine":
        if user.role != "RESEARCH_TEAM":
            raise ApiError(403, "FORBIDDEN", "Only research teams can view their own opportunities.")
        query = select(Opportunity).where(Opportunity.owner_user_id == user.id)
    else:
        query = published_opportunities()
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    # Avoid SQLite integer overflow for valid but extremely distant page numbers.
    offset = (page - 1) * page_size
    rows = list(db.scalars(query.order_by(Opportunity.updated_at.desc(), Opportunity.id)
                          .offset(offset).limit(page_size))) if offset < total else []
    return {"items": serialize_many(db, rows), "page": page, "pageSize": page_size, "total": total}


def check_content(db, content, *, published=False):
    validate("OpportunityContent", content)
    requirements = content["requirements"]
    if published and not requirements:
        invalid("content.requirements", "Published opportunities need at least one requirement.")
    if len({row["id"] for row in requirements}) != len(requirements):
        invalid("content.requirements", "Requirement IDs must be unique within an opportunity.")
    tag_ids = {tag_id for row in requirements for tag_id in row["tagIds"]}
    kinds = dict(db.execute(select(Tag.id, Tag.kind).where(Tag.id.in_(tag_ids))).all())
    for index, row in enumerate(requirements):
        if "skillTitles" in row:
            titles = row["skillTitles"]
            if len({normalise_title(title) for title in titles}) != len(titles):
                invalid(f"content.requirements[{index}].skillTitles", "Skill names must be unique.")
            for title in titles:
                if not normalise_title(title) or any(unicodedata.category(c).startswith("C") for c in title):
                    invalid(f"content.requirements[{index}].skillTitles", "Enter visible skill names without control characters.")
        for tag_index, tag_id in enumerate(row["tagIds"]):
            if kinds.get(tag_id) != row["kind"]:
                invalid(f"content.requirements[{index}].tagIds[{tag_index}]",
                        f"Select an existing {row['kind']} tag.")


def check_revision(opportunity, expected):
    if opportunity.revision != expected:
        raise ApiError(409, "REVISION_CONFLICT", "This opportunity changed. Reload and compare the latest version.",
                       revision=opportunity.revision)


def create_opportunity(db, user, content):
    check_content(db, content)
    now = utcnow()
    opportunity = Opportunity(id="opp_" + secrets.token_hex(16), owner_user_id=user.id,
                              revision=1, status="DRAFT", created_at=now, updated_at=now)
    db.add(opportunity)
    replace_content(db, opportunity, content)
    return serialize(db, opportunity)


def save_opportunity(db, opportunity, expected, content):
    check_revision(opportunity, expected)
    check_content(db, content, published=opportunity.status == "PUBLISHED")
    current = serialize(db, opportunity)
    if current["content"] == content:
        return current
    opportunity.revision += 1
    opportunity.updated_at = utcnow()
    replace_content(db, opportunity, content)
    return serialize(db, opportunity)


def publish_opportunity(db, opportunity, expected):
    check_revision(opportunity, expected)
    check_content(db, serialize(db, opportunity)["content"], published=True)
    if opportunity.status == "DRAFT":
        opportunity.status = "PUBLISHED"
        opportunity.revision += 1
        opportunity.updated_at = utcnow()
        db.flush()
    return serialize(db, opportunity)
