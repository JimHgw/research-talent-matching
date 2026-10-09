from flask import Blueprint, jsonify

from ...db.database import database
from ...shared.pagination import pagination
from ...shared.security import require_user
from .service import owner_match, recommendations


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