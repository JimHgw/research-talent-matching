"""Team discovery always evaluates current, permitted fields in one transaction."""

from ...db.models import utcnow
from ...db.skills import matching_skills
from ...shared.search import talent_matches_filters
from .engine import evaluate_opportunity, team_evidence
from .semantic_runtime import enrich_matches
from .service import ranked_page
from .team_repository import (discoverable_profiles, own_published_opportunity,
                              tag_labels, visible_profiles)


def visible_snapshot(talent, labels):
    fields = talent["fields"]
    return {
        "skills": matching_skills(fields.get("skills", []), labels),
        "skillRecords": fields.get("skills", []),
        "researchInterests": {tag_id: labels[tag_id]
                              for tag_id in fields.get("researchInterests", [])},
        "researchInterestText": fields.get("researchInterestText", ""),
        "customInterestTags": fields.get("customInterestTags", []),
        "education": fields.get("education", []),
        "researchExperience": fields.get("researchExperience", []),
        "researchOutputs": fields.get("researchOutputs", []),
    }


def evaluate_visible(opportunity, talent, labels):
    snapshot = visible_snapshot(talent, labels)
    results, summary = evaluate_opportunity(opportunity, snapshot, team_evidence)
    enrich_matches([(opportunity, snapshot, summary)])
    for result in results:
        if result["status"] == "UNKNOWN":
            result["reason"] = "There is insufficient shared evidence for this requirement."
    return results, summary


def talent_matches(db, user, opportunity_id, page, page_size, filters=None):
    opportunity = own_published_opportunity(db, user, opportunity_id)
    talents = visible_profiles(db, discoverable_profiles(db))
    labels = tag_labels(db)
    talents = [talent for talent in talents if talent_matches_filters(talent, filters or {}, labels)]
    items = evaluate_talents(opportunity, talents, labels)
    return ranked_page(items, page, page_size)


def evaluate_talents(opportunity, talents, labels):
    items, pairs = [], []
    for talent in talents:
        snapshot = visible_snapshot(talent, labels)
        _, summary = evaluate_opportunity(opportunity, snapshot, team_evidence)
        pairs.append((opportunity, snapshot, summary))
        items.append({"talent": talent, "summary": summary})
    enrich_matches(pairs)
    return items


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
