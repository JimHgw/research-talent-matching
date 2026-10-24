"""One UTC predicate for active discovery and retained expiry on owner edits."""

from sqlalchemy import or_

from ...db.models import Opportunity, utcnow
from ...shared.validation import ApiError


def availability(opportunity, now=None):
    now = now if now is not None else utcnow()
    if opportunity.status == "DRAFT":
        return "DRAFT"
    if opportunity.expired_at is not None or (opportunity.deadline_at is not None and opportunity.deadline_at <= now):
        return "EXPIRED"
    return "ACTIVE"


def active_predicates(now=None):
    now = now if now is not None else utcnow()
    return (Opportunity.status == "PUBLISHED", Opportunity.expired_at.is_(None),
            or_(Opportunity.deadline_at.is_(None), Opportunity.deadline_at > now))


def require_active(opportunity, now=None):
    if availability(opportunity, now) == "EXPIRED":
        raise ApiError(409, "OPPORTUNITY_EXPIRED", "This opportunity has expired.")
