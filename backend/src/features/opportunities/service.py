"""Opportunity visibility, validation and lifecycle, independent of HTTP handlers."""

import secrets
import unicodedata
from urllib.parse import urlsplit

from jsonschema import FormatChecker

from sqlalchemy import select

from ...db.models import Opportunity, Tag, utcnow
from ...db.skills import normalise_title
from ...shared.validation import ApiError, SOURCE_URL_ERROR, invalid, validate
from ...shared.search import opportunity_matches, parse_datetime
from .availability import active_predicates, availability
from .repository import replace_content, serialize, serialize_many


def published_opportunities(now=None):
    """Shared selection for discovery and future matching; drafts are excluded."""
    return select(Opportunity).where(*active_predicates(now))


def get_opportunity(db, user, opportunity_id, *, owner_only=False):
    validate("Id", opportunity_id)
    opportunity = db.get(Opportunity, opportunity_id)
    if opportunity is None or (opportunity.owner_user_id != user.id and
                               (owner_only or opportunity.status != "PUBLISHED")):
        raise ApiError(404, "NOT_FOUND", "Opportunity not found.")
    return opportunity


def authorise_scope(user, scope):
    if scope == "mine" and user.role != "RESEARCH_TEAM":
        raise ApiError(403, "FORBIDDEN", "Only research teams can view their own opportunities.")


def list_opportunities(db, user, scope, page, page_size, filters=None):
    now = utcnow()
    authorise_scope(user, scope)
    if scope == "mine":
        query = select(Opportunity).where(Opportunity.owner_user_id == user.id)
    else:
        query = published_opportunities(now)
    rows = list(db.scalars(query.order_by(Opportunity.updated_at.desc(), Opportunity.id)))
    items = [item for item in serialize_many(db, rows, now) if opportunity_matches(item, filters or {})]
    offset = (page - 1) * page_size
    return {"items": items[offset:offset + page_size], "page": page, "pageSize": page_size, "total": len(items)}


def check_source_url(value):
    """Validate only the saved address; never request the linked resource."""
    if value is None:
        return
    valid = False
    if (isinstance(value, str) and 0 < len(value) <= 2048
            and not any(char.isspace() or char == "\\"
                        or unicodedata.category(char).startswith("C")
                        for char in value)):
        try:
            parsed = urlsplit(value)
            parsed.port  # Raises for malformed/out-of-range ports.
            valid = (parsed.scheme in {"http", "https"}
                     and bool(parsed.netloc) and bool(parsed.hostname)
                     and parsed.username is None and parsed.password is None
                     and FormatChecker().conforms(value, "iri"))
        except (ValueError, UnicodeError):
            valid = False
    if not valid:
        invalid("content.sourceUrl", SOURCE_URL_ERROR)


def check_content(db, content, *, published=False):
    validate("OpportunityContent", content)
    if "sourceUrl" in content:
        check_source_url(content["sourceUrl"])
    if content.get("deadlineAt") is not None:
        parse_datetime(content["deadlineAt"], "content.deadlineAt")
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
    return serialize(db, opportunity, now)


def save_opportunity(db, opportunity, expected, content, reopen=False):
    check_revision(opportunity, expected)
    check_content(db, content, published=opportunity.status == "PUBLISHED")
    now = utcnow()
    current = serialize(db, opportunity, now)
    was_expired = availability(opportunity, now) == "EXPIRED"
    if reopen and opportunity.status != "PUBLISHED":
        raise ApiError(409, "OPPORTUNITY_NOT_PUBLISHED", "Publish this opportunity before reopening it.")
    if was_expired:
        opportunity.expired_at = opportunity.expired_at or opportunity.deadline_at or now
    replace_content(db, opportunity, content)
    if reopen:
        if opportunity.deadline_at is not None and opportunity.deadline_at <= now:
            invalid("content.deadlineAt", "Choose a future deadline before reopening.")
        opportunity.expired_at = None
    result = serialize(db, opportunity, now)
    if result["content"] != current["content"] or (reopen and was_expired):
        opportunity.revision += 1
        opportunity.updated_at = now
    return serialize(db, opportunity, now)


def publish_opportunity(db, opportunity, expected):
    now = utcnow()
    check_revision(opportunity, expected)
    check_content(db, serialize(db, opportunity, now)["content"], published=True)
    if opportunity.status == "DRAFT":
        if opportunity.deadline_at is not None and opportunity.deadline_at <= now:
            invalid("content.deadlineAt", "Choose a future deadline before publishing.")
        opportunity.status = "PUBLISHED"
        opportunity.revision += 1
        opportunity.updated_at = now
        db.flush()
    return serialize(db, opportunity, now)
