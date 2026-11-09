"""Filter before loading children; preserve Python's exact Unicode comparisons.

SQL collations/LOWER do not implement NFKC + split-whitespace + casefold. Text
filters therefore inspect only needed scalar columns, never serialised candidates.
Ordinary pages retain at most page_size matching IDs; recommendations retain all
matching IDs and load them in bounded batches without truncating the score pool.
"""

from sqlalchemy import func, select

from ...db.models import Opportunity
from ...db.opportunity_read import CONTENT_FIELDS
from ...shared.search import SEARCH_FIELDS, opportunity_matches

READ_BATCH_SIZE = 1000
TEXT_COLUMNS = {**CONTENT_FIELDS, "opportunityType": "opportunity_type"}


def filtered_rows(db, query, filters=None, *, page=None, page_size=None):
    """Return (ordered ORM rows, exact total) within the caller's read transaction."""
    filters = filters or {}
    # These values are constrained uppercase enums in both supported databases.
    if "disciplineGroup" in filters:
        query = query.where(Opportunity.discipline_group.in_([v.upper() for v in filters["disciplineGroup"]]))
    if "deadlineFrom" in filters:
        query = query.where(Opportunity.deadline_at >= filters["deadlineFrom"])
    if "deadlineTo" in filters:
        query = query.where(Opportunity.deadline_at < filters["deadlineTo"])
    residual = {key: value for key, value in filters.items()
                if key not in ("disciplineGroup", "deadlineFrom", "deadlineTo")}
    offset = (page - 1) * page_size if page is not None else 0
    if not residual:
        if page is None:
            rows = list(db.scalars(query))
            return rows, len(rows)
        total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
        # Avoid binding an arbitrarily large offset accepted by legacy clients.
        rows = list(db.scalars(query.offset(offset).limit(page_size))) if offset < total else []
        return rows, total

    fields = set(SEARCH_FIELDS) if "q" in residual else set()
    fields.update(key for key in residual if key != "q")
    columns = [getattr(Opportunity, TEXT_COLUMNS[field]).label(field) for field in sorted(fields)]
    scalars = query.with_only_columns(Opportunity.id, *columns).execution_options(yield_per=READ_BATCH_SIZE)
    ids, total = [], 0
    for row in db.execute(scalars):
        if opportunity_matches({"content": row._mapping}, residual):
            if page is None or offset <= total < offset + page_size:
                ids.append(row.id)
            total += 1
    # The scalar scan already established global order; IN does not preserve it.
    by_id = {}
    for start in range(0, len(ids), READ_BATCH_SIZE):
        by_id.update((row.id, row) for row in db.scalars(
            select(Opportunity).where(Opportunity.id.in_(ids[start:start + READ_BATCH_SIZE]))))
    return [by_id[key] for key in ids], total
