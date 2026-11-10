from ...db.models import utcnow
from ...shared.validation import ApiError
from .engine import evaluate_opportunity
from .semantic_runtime import enrich_matches
from .repository import (
    get_owner_profile,
    get_published,
    list_published,
    read_matching_profile,
)


def require_confirmed(profile):
    if (
        profile.confirmation_status != "CONFIRMED"
        or profile.confirmed_revision != profile.revision
    ):
        raise ApiError(
            409,
            "PROFILE_UNCONFIRMED",
            "Review and confirm your current profile first.",
        )


def ranking_key(item):
    summary = item["summary"]
    score = summary.get("recommendationScore", summary["score"])
    unknown = summary["unknownWeightPercent"]
    return (
        score is None,
        -score if score is not None else 0,
        unknown if unknown is not None else float("inf"),
        (item["opportunity"]["id"] if "opportunity" in item
         else item["talent"]["talentId"]),
    )


def recommendations(db, user, page, page_size, filters=None):
    profile = get_owner_profile(db, user)
    require_confirmed(profile)

    snapshot = read_matching_profile(db, profile)
    items = []
    pairs = []

    for opportunity in list_published(db, filters):
        results, summary = evaluate_opportunity(opportunity, snapshot)
        pairs.append((opportunity, snapshot, results, summary))
        items.append({
            "opportunity": opportunity,
            "summary": summary,
        })

    enrich_matches(pairs)
    return ranked_page(items, page, page_size)


def ranked_page(items, page, page_size):
    items.sort(key=ranking_key)
    start = (page - 1) * page_size
    return {
        "items": [{"rank": index, **item}
                  for index, item in enumerate(items[start:start + page_size], start=start + 1)],
        "page": page,
        "pageSize": page_size,
        "total": len(items),
    }


def owner_match(db, user, opportunity_id):
    opportunity = get_published(db, opportunity_id, active=True)
    profile = get_owner_profile(db, user)
    require_confirmed(profile)
    snapshot = read_matching_profile(db, profile)
    results, summary = evaluate_opportunity(opportunity, snapshot)
    enrich_matches([(opportunity, snapshot, results, summary)])
    return {
        "opportunity": opportunity,
        "profileRevision": profile.revision,
        "summary": summary,
        "requirements": results,
        "evaluatedAt": (
            utcnow().isoformat(timespec="microseconds") + "Z"
        ),
    }
