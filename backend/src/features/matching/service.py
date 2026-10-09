from ...db.models import utcnow
from ...shared.validation import ApiError
from .engine import evaluate_opportunity
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
    score = summary["score"]
    unknown = summary["unknownWeightPercent"]
    return (
        score is None,
        -score if score is not None else 0,
        unknown if unknown is not None else float("inf"),
        item["opportunity"]["id"],
    )


def recommendations(db, user, page, page_size):
    profile = get_owner_profile(db, user)
    require_confirmed(profile)

    snapshot = read_matching_profile(db, profile)
    items = []

    for opportunity in list_published(db):
        _, summary = evaluate_opportunity(opportunity, snapshot)
        items.append({
            "opportunity": opportunity,
            "summary": summary,
        })

    items.sort(key=ranking_key)
    ranked = [
        {"rank": index, **item}
        for index, item in enumerate(items, start=1)
    ]
    start = (page - 1) * page_size
    return {
        "items": ranked[start:start + page_size],
        "page": page,
        "pageSize": page_size,
        "total": len(ranked),
    }


def owner_match(db, user, opportunity_id):
    opportunity = get_published(db, opportunity_id)
    profile = get_owner_profile(db, user)
    require_confirmed(profile)
    snapshot = read_matching_profile(db, profile)
    results, summary = evaluate_opportunity(opportunity, snapshot)
    return {
        "opportunity": opportunity,
        "profileRevision": profile.revision,
        "summary": summary,
        "requirements": results,
        "evaluatedAt": (
            utcnow().isoformat(timespec="microseconds") + "Z"
        ),
    }