from flask import Blueprint, jsonify

from ...db.database import database
from ...shared.pagination import pagination
from ...shared.security import require_user
from .service import owner_match, recommendations
from .team_service import talent_matches, team_match


matching = Blueprint(
    "matching",
    __name__,
    url_prefix="/api/v1",
)


@matching.get("/me/recommendations")
def recommendation_list():
    with database().transaction() as db:
        _, user = require_user(db, "TALENT")
        page, page_size = pagination()

        result = recommendations(
            db, user, page, page_size
        )

    return jsonify(result)


@matching.get("/me/opportunity-matches/<opportunity_id>")
def match_detail(opportunity_id):
    with database().transaction() as db:
        _, user = require_user(db, "TALENT")

        result = owner_match(
            db, user, opportunity_id
        )

    return jsonify(result)


@matching.get("/opportunities/<opportunity_id>/talent-matches")
def talent_list(opportunity_id):
    with database().transaction() as db:
        _, user = require_user(db, "RESEARCH_TEAM")
        page, page_size = pagination()
        result = talent_matches(db, user, opportunity_id, page, page_size)
    return jsonify(result)


@matching.get("/opportunities/<opportunity_id>/talent-matches/<talent_id>")
def talent_detail(opportunity_id, talent_id):
    with database().transaction() as db:
        _, user = require_user(db, "RESEARCH_TEAM")
        result = team_match(db, user, opportunity_id, talent_id)
    return jsonify(result)
