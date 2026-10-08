"""US-02 HTTP adapter; authentication and writes share one database transaction."""

from flask import Blueprint, jsonify, request

from ...db.database import database
from ...shared.pagination import pagination
from ...shared.security import require_csrf, require_user
from ...shared.validation import body, invalid
from .repository import serialize
from .service import (create_opportunity, get_opportunity, list_opportunities,
                      publish_opportunity, save_opportunity)

opportunities = Blueprint("opportunities", __name__, url_prefix="/api/v1/opportunities")


@opportunities.get("")
def opportunity_list():
    with database().transaction() as db:
        _, user = require_user(db)
        scopes = request.args.getlist("scope")
        scope = scopes[0] if scopes else "published"
        if len(scopes) > 1 or scope not in ("published", "mine"):
            invalid("scope", "Choose published or mine.")
        page, page_size = pagination()
        result = list_opportunities(db, user, scope, page, page_size)
    return jsonify(result)


@opportunities.post("")
def opportunity_create():
    with database().transaction(write=True) as db:
        session, user = require_user(db, "RESEARCH_TEAM")
        require_csrf(session)
        result = create_opportunity(db, user, body("OpportunityContent"))
    return jsonify(result), 201


@opportunities.get("/<opportunity_id>")
def opportunity_get(opportunity_id):
    with database().transaction() as db:
        _, user = require_user(db)
        result = serialize(db, get_opportunity(db, user, opportunity_id))
    return jsonify(result)


@opportunities.put("/<opportunity_id>")
def opportunity_put(opportunity_id):
    with database().transaction(write=True) as db:
        session, user = require_user(db, "RESEARCH_TEAM")
        require_csrf(session)
        opportunity = get_opportunity(db, user, opportunity_id, owner_only=True)
        data = body("OpportunityWrite")
        result = save_opportunity(db, opportunity, data["expectedRevision"], data["content"])
    return jsonify(result)


@opportunities.post("/<opportunity_id>/publish")
def opportunity_publish(opportunity_id):
    with database().transaction(write=True) as db:
        session, user = require_user(db, "RESEARCH_TEAM")
        require_csrf(session)
        opportunity = get_opportunity(db, user, opportunity_id, owner_only=True)
        result = publish_opportunity(db, opportunity, body("RevisionRequest")["expectedRevision"])
    return jsonify(result)
