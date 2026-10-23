"""Team discovery always evaluates current, permitted fields in one transaction."""

from ...db.models import utcnow
from ...db.skills import matching_skills
from .engine import evaluate_opportunity, team_evidence
from .service import ranked_page
from .team_repository import (discoverable_profiles, own_published_opportunity,
                              tag_labels, visible_profiles)


def evaluate_visible(opportunity, talent, labels):
    fields = talent["fields"]
    snapshot = {
        "skills": matching_skills(fields.get("skills", []), labels),
        "researchInterests": {tag_id: labels[tag_id]
                              for tag_id in fields.get("researchInterests", [])},
    }
    results, summary = evaluate_opportunity(opportunity, snapshot, team_evidence)
    for result in results:
        if result["status"] == "UNKNOWN":
            result["reason"] = "There is insufficient shared evidence for this requirement."
    return results, summary


def talent_matches(db, user, opportunity_id, page, page_size):
    opportunity = own_published_opportunity(db, user, opportunity_id)
    talents = visible_profiles(db, discoverable_profiles(db))
    labels = tag_labels(db)
    items = []
    for talent in talents:
        _, summary = evaluate_visible(opportunity, talent, labels)
        items.append({"talent": talent, "summary": summary})
    return ranked_page(items, page, page_size)


def team_match(db, user, opportunity_id, talent_id):
    opportunity = own_published_opportunity(db, user, opportunity_id)
    talent = visible_profiles(db, discoverable_profiles(db, talent_id))[0]
    results, summary = evaluate_visible(opportunity, talent, tag_labels(db))
    return {
        "opportunityId": opportunity["id"],
        "opportunityRevision": opportunity["revision"],
        "talent": talent,
        "summary": summary,
        "requirements": results,
        "evaluatedAt": utcnow().isoformat(timespec="microseconds") + "Z",
    }
