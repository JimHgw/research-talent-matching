"""Owner-scoped saved opportunities and privacy-preserving opportunity shortlists."""

from flask import Blueprint, jsonify, request
from sqlalchemy import delete, func, select

from ..db.collections import SavedOpportunity, ShortlistedTalent
from ..db.database import database
from ..db.models import Opportunity
from ..db.opportunity_read import serialize
from ..shared.pagination import pagination
from ..shared.security import require_csrf, require_user
from ..shared.validation import validate
from .matching.repository import get_published
from .matching.service import ranked_page
from .matching.team_repository import (discoverable_profiles, own_published_opportunity,
                                       tag_labels, visible_profiles)
from .matching.team_service import evaluate_visible

collections = Blueprint("collections", __name__, url_prefix="/api/v1")


@collections.get("/me/saved-opportunities")
def saved_list():
    with database().transaction() as db:
        _, user = require_user(db, "TALENT")
        page, size = pagination()
        query = (select(Opportunity).join(SavedOpportunity)
                 .where(SavedOpportunity.user_id == user.id,
                        Opportunity.status == "PUBLISHED"))
        total = db.scalar(select(func.count()).select_from(query.subquery()))
        rows = db.scalars(query.order_by(SavedOpportunity.created_at.desc(), Opportunity.id)
                          .offset(min((page - 1) * size, total)).limit(size))
        result = {"items": [serialize(db, row) for row in rows],
                  "page": page, "pageSize": size, "total": total}
    return jsonify(result)


@collections.route("/me/saved-opportunities/<opportunity_id>", methods=["GET", "PUT", "DELETE"])
def saved_item(opportunity_id):
    writing = request.method != "GET"
    with database().transaction(write=writing) as db:
        session, user = require_user(db, "TALENT")
        if writing:
            require_csrf(session)
        validate("Id", opportunity_id)
        # Require current publication for reads/additions; allow removing stale relations.
        if request.method != "DELETE":
            get_published(db, opportunity_id)
        key = (user.id, opportunity_id)
        row = db.get(SavedOpportunity, key)
        if request.method == "PUT" and row is None:
            db.add(SavedOpportunity(user_id=user.id, opportunity_id=opportunity_id))
        elif request.method == "DELETE":
            db.execute(delete(SavedOpportunity).where(
                SavedOpportunity.user_id == user.id,
                SavedOpportunity.opportunity_id == opportunity_id))
        result = {"saved": request.method == "PUT" or (request.method == "GET" and row is not None)}
    return jsonify(result)


@collections.get("/opportunities/<opportunity_id>/shortlist")
def shortlist_list(opportunity_id):
    with database().transaction() as db:
        _, user = require_user(db, "RESEARCH_TEAM")
        opportunity = own_published_opportunity(db, user, opportunity_id)
        page, size = pagination()
        ids = set(db.scalars(select(ShortlistedTalent.talent_id).where(
            ShortlistedTalent.opportunity_id == opportunity_id)))
        # Recheck consent, confirmation and active account on EVERY retrieval.
        profiles = [profile for profile in discoverable_profiles(db) if profile.talent_id in ids]
        talents = visible_profiles(db, profiles)
        labels = tag_labels(db)
        items = []
        for talent in talents:
            _, summary = evaluate_visible(opportunity, talent, labels)
            items.append({"talent": talent, "summary": summary})
        result = ranked_page(items, page, size)
    return jsonify(result)


@collections.route("/opportunities/<opportunity_id>/shortlist/<talent_id>",
                   methods=["GET", "PUT", "DELETE"])
def shortlist_item(opportunity_id, talent_id):
    writing = request.method != "GET"
    with database().transaction(write=writing) as db:
        session, user = require_user(db, "RESEARCH_TEAM")
        if writing:
            require_csrf(session)
        own_published_opportunity(db, user, opportunity_id)
        validate("Id", talent_id)
        if request.method != "DELETE":
            discoverable_profiles(db, talent_id)
        row = db.get(ShortlistedTalent, (opportunity_id, talent_id))
        if request.method == "PUT" and row is None:
            db.add(ShortlistedTalent(opportunity_id=opportunity_id, talent_id=talent_id))
        elif request.method == "DELETE":
            db.execute(delete(ShortlistedTalent).where(
                ShortlistedTalent.opportunity_id == opportunity_id,
                ShortlistedTalent.talent_id == talent_id))
        result = {"saved": request.method == "PUT" or (request.method == "GET" and row is not None)}
    return jsonify(result)
