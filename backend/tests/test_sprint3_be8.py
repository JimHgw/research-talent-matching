"""BE-8: independent pre-change oracles, real HTTP pages and SQL/load bounds."""

from contextlib import contextmanager
import math

import pytest
from sqlalchemy import event, inspect, select
from sqlalchemy.dialects.mysql import dialect as mysql_dialect
from sqlalchemy.schema import CreateIndex

from backend.src.db.models import (Opportunity, PrivacySettings, PrivacyVisibleField,
                                   TalentProfile, User)
from backend.src.db.opportunity_read import serialize_many
from backend.src.db.opportunity_upgrade import upgrade_opportunity_search
from backend.src.db.query_upgrade import QUERY_INDEXES, upgrade_query_indexes
from backend.src.features.matching import repository, service, team_repository, team_service
from backend.src.features.matching.engine import evaluate_opportunity, team_evidence
from backend.src.features.opportunities.availability import active_predicates
from backend.src.features.opportunities.queries import READ_BATCH_SIZE
from backend.src.shared.search import opportunity_matches, search_parameters, talent_matches_filters
from backend.src.shared.validation import validator
from backend.tests.be8_data import (MANIFEST, NOW, OWNER, TARGET, TEAM,
                                   authenticated_client, seed_dataset)
from test_us04 import make_opportunity, research_team


@pytest.fixture(params=MANIFEST["sizes"], ids=lambda value: f"n{value}")
def dataset(app, monkeypatch, request):
    seed_dataset(app, request.param)
    for module in ("backend.src.features.opportunities.availability",
                   "backend.src.features.opportunities.service"):
        monkeypatch.setattr(module + ".utcnow", lambda: NOW)
    return app, request.param


def normalised(app, query, *, talent=False):
    with app.test_request_context(query_string=query), app.extensions["database"].transaction() as db:
        return search_parameters(db, talent=talent)


def old_ranked_page(items, page, size):
    # Independent copy of the pre-BE-8 ordering and global rank assignment.
    def key(item):
        summary = item["summary"]
        score = summary.get("recommendationScore", summary["score"])
        unknown = summary["unknownWeightPercent"]
        return (score is None, -score if score is not None else 0,
                unknown if unknown is not None else float("inf"),
                item["opportunity"]["id"] if "opportunity" in item else item["talent"]["talentId"])
    ranked = [{"rank": rank, **item} for rank, item in enumerate(sorted(items, key=key), 1)]
    start = (page - 1) * size
    return {"items": ranked[start:start + size], "total": len(ranked), "page": page, "pageSize": size}


def old_opportunities(db, user, scope, page, size, filters):
    query = select(Opportunity)
    query = query.where(Opportunity.owner_user_id == user.id) if scope == "mine" else query.where(*active_predicates(NOW))
    rows = list(db.scalars(query.order_by(Opportunity.updated_at.desc(), Opportunity.id)))
    items = [item for item in serialize_many(db, rows, NOW) if opportunity_matches(item, filters)]
    start = (page - 1) * size
    return {"items": items[start:start + size], "total": len(items), "page": page, "pageSize": size}


def old_recommendations(db, user, filters):
    profile = repository.get_owner_profile(db, user)
    service.require_confirmed(profile)
    snapshot = repository.read_matching_profile(db, profile)
    rows = list(db.scalars(select(Opportunity).where(*active_predicates(NOW)).order_by(Opportunity.id)))
    items, pairs = [], []
    for opportunity in serialize_many(db, rows, NOW):
        if opportunity_matches(opportunity, filters):
            results, summary = evaluate_opportunity(opportunity, snapshot)
            pairs.append((opportunity, snapshot, results, summary))
            items.append({"opportunity": opportunity, "summary": summary})
    service.enrich_matches(pairs)
    return items


def old_talents(db, user, filters):
    opportunity = team_repository.own_published_opportunity(db, user, TARGET)
    # No pushed-down conditions: privacy projection precedes all condition checks.
    talents = team_repository.visible_profiles(db, team_repository.discoverable_profiles(db))
    labels = team_repository.tag_labels(db)
    items, pairs = [], []
    for talent in talents:
        if talent_matches_filters(talent, filters, labels):
            snapshot = team_service.visible_snapshot(talent, labels)
            results, summary = evaluate_opportunity(opportunity, snapshot, team_evidence)
            items.append({"talent": talent, "summary": summary})
            pairs.append((opportunity, snapshot, results, summary))
    service.enrich_matches(pairs)
    return items


@contextmanager
def reads(app):
    statements, loaded = [], []
    engine = app.extensions["database"].engine

    def sql(_, __, statement, ___, ____, _____):
        if not statement.upper().startswith("BEGIN"):
            statements.append(statement)

    def load(row, _):
        loaded.append(row.id)

    event.listen(engine, "before_cursor_execute", sql)
    event.listen(Opportunity, "load", load)
    try:
        yield statements, loaded
    finally:
        event.remove(engine, "before_cursor_execute", sql)
        event.remove(Opportunity, "load", load)
    assert all(statement.lstrip().upper().startswith("SELECT") for statement in statements)


@pytest.mark.parametrize("scope", ["published", "mine"])
def test_ordinary_lists_equal_prechange_across_all_pages(dataset, scope):
    app, _ = dataset
    client = authenticated_client(app, TEAM)
    for query in ({}, MANIFEST["opportunityFilters"], {"q": "STRASSE"}, {"q": "cafe\u0301"},
                  {"q": "%_'"}, {"q": "ａｉ"}, {"university": ["ｕｎｓｗ sydney", "USYD"]},
                  {"opportunityType": "PHD"}, {"disciplineGroup": "BUSINESS"},
                  {"deadlineTo": "2030-01-15T00:00:00Z"}, {"q": "no results"}):
        filters = normalised(app, query)
        with app.extensions["database"].transaction() as db:
            user = db.get(User, TEAM)
            expected = old_opportunities(db, user, scope, 1, 10000, filters)["items"]
        seen = []
        for page in range(1, math.ceil(len(expected) / 37) + 2):
            response = client.get("/api/v1/opportunities", query_string={**query, "scope": scope, "page": page, "pageSize": 37})
            assert response.status_code == 200
            value = response.get_json()
            validator("OpportunityPage").validate(value)
            assert value["total"] == len(expected)
            assert value["items"] == expected[(page - 1) * 37:page * 37]
            seen.extend(row["id"] for row in value["items"])
        assert len(seen) == len(set(seen)) == len(expected)
        assert client.get("/api/v1/opportunities", query_string={**query, "scope": scope, "page": "9" * 100}).get_json()["items"] == []


@pytest.mark.parametrize("endpoint", ["recommendations", "talents"])
@pytest.mark.parametrize("filtered", [False, True])
def test_matching_results_scores_totals_and_global_ranks_equal_prechange(dataset, endpoint, filtered):
    app, _ = dataset
    talent = endpoint == "talents"
    user_id = TEAM if talent else OWNER
    query = (MANIFEST["talentFilters"] if talent else MANIFEST["opportunityFilters"]) if filtered else {}
    filters = normalised(app, query, talent=talent)
    with app.app_context(), app.extensions["database"].transaction() as db:
        user = db.get(User, user_id)
        expected = (old_talents if talent else old_recommendations)(db, user, filters)
    path = f"/api/v1/opportunities/{TARGET}/talent-matches" if talent else "/api/v1/me/recommendations"
    client, seen = authenticated_client(app, user_id), []
    for page in range(1, math.ceil(len(expected) / 100) + 2):
        response = client.get(path, query_string={**query, "page": page, "pageSize": 100})
        assert response.status_code == 200
        value = response.get_json()
        validator("TalentMatchPage" if talent else "RecommendationPage").validate(value)
        assert value == old_ranked_page(expected, page, 100)
        seen.extend(item["rank"] for item in value["items"])
    assert seen == list(range(1, len(expected) + 1))


@pytest.mark.parametrize("filtered", [False, True])
def test_ordinary_pages_load_only_page_and_three_child_queries(dataset, filtered):
    app, _ = dataset
    client = authenticated_client(app, OWNER)
    filters = MANIFEST["opportunityFilters"] if filtered else {}
    for size in (1, 20, 100):
        with reads(app) as (sql, loaded):
            value = client.get("/api/v1/opportunities", query_string={**filters, "pageSize": size}).get_json()
        assert len(loaded) == len(value["items"]) <= size
        for table in ("requirement_tags", "opportunity_skill_details", "opportunity_requirements"):
            assert sum("FROM " + table + " " in statement.replace("\n", " ") for statement in sql) == 1
        assert len(sql) == 7  # Auth=2, count/scalar scan=1, page=1, children=3.
        if not filtered:
            # MySQL compiles offset pagination as LIMIT offset, size; SQLite
            # spells it LIMIT size OFFSET offset. Both must paginate in SQL.
            assert any("FROM opportunities" in statement and "LIMIT" in statement for statement in sql)
            assert any("count(*)" in statement for statement in sql)
    with reads(app) as (sql, loaded):
        assert client.get("/api/v1/opportunities", query_string={**filters, "page": "9" * 100}).get_json()["items"] == []
    assert not loaded
    assert len(sql) == 3  # Empty pages do not read candidate objects or children.


def test_conditions_precede_loading_and_every_eligible_candidate_is_scored(dataset, monkeypatch):
    app, size = dataset
    owner = authenticated_client(app, OWNER)
    original, calls = service.enrich_matches, []

    def score(pairs):
        calls.append([opportunity["id"] for opportunity, _, _, _ in pairs])
        original(pairs)
        # Make the final candidate the best; paging before scoring would miss it.
        for opportunity, _, _, summary in pairs:
            summary["recommendationScore"] = int(opportunity["id"].rsplit("_", 1)[1])

    monkeypatch.setattr(service, "enrich_matches", score)
    with reads(app) as (sql, loaded):
        value = owner.get("/api/v1/me/recommendations", query_string={**MANIFEST["opportunityFilters"], "pageSize": 1}).get_json()
    assert len(calls) == 1 and len(calls[0]) == value["total"] > 1
    assert len(loaded) == value["total"] < size * .6
    assert value["items"][0]["opportunity"]["id"] == max(calls[0])
    assert value["items"][0]["rank"] == 1
    # Matching must not read the unused private resume column.
    assert not any("resume_description" in statement for statement in sql)
    assert sum("FROM opportunity_requirements " in s.replace("\n", " ") for s in sql) == math.ceil(value["total"] / READ_BATCH_SIZE)


def test_interest_pushdown_respects_current_visibility_consent_and_confirmation(dataset):
    app, _ = dataset
    client = authenticated_client(app, TEAM)
    query = {"interestTagId": ["interest_ml", "interest_health"]}
    path = f"/api/v1/opportunities/{TARGET}/talent-matches"
    first = client.get(path, query_string={**query, "pageSize": 100}).get_json()
    key = first["items"][0]["talent"]["talentId"]
    with app.extensions["database"].transaction(write=True) as db:
        db.delete(db.get(PrivacyVisibleField, (key, "researchInterests")))
    second = client.get(path, query_string={**query, "pageSize": 100}).get_json()
    assert second["total"] == first["total"] - 1
    with app.extensions["database"].transaction(write=True) as db:
        db.add(PrivacyVisibleField(talent_id=key, field="researchInterests"))
        db.get(PrivacySettings, key).discoverable = False
    assert client.get(path, query_string=query).get_json()["total"] == second["total"]
    with app.extensions["database"].transaction(write=True) as db:
        db.get(PrivacySettings, key).discoverable = True
        profile = db.get(TalentProfile, key)
        profile.confirmation_status, profile.confirmed_revision, profile.confirmed_at = "UNCONFIRMED", None, None
    assert client.get(path, query_string=query).get_json()["total"] == second["total"]


def test_real_model_query_optimisations_preserve_scores_and_ranks(dataset, application_model):
    app, _ = dataset
    app.config["SEMANTIC_MATCHING_ENABLED"] = True
    app.extensions["semantic_matching"].directory = application_model
    for talent in (False, True):
        user_id = TEAM if talent else OWNER
        query = MANIFEST["talentFilters"] if talent else MANIFEST["opportunityFilters"]
        filters = normalised(app, query, talent=talent)
        with app.app_context(), app.extensions["database"].transaction() as db:
            expected = (old_talents if talent else old_recommendations)(db, db.get(User, user_id), filters)
        path = f"/api/v1/opportunities/{TARGET}/talent-matches" if talent else "/api/v1/me/recommendations"
        response = authenticated_client(app, user_id).get(path, query_string={**query, "pageSize": 100})
        assert response.status_code == 200
        assert response.get_json() == old_ranked_page(expected, 1, 100)
        assert all(row["summary"]["semanticRequirements"]["status"] != "UNAVAILABLE" for row in expected)


def test_query_index_upgrade_is_additive_repeatable_and_removes_page_sort(dataset):
    app, _ = dataset
    database = app.extensions["database"]
    with database.transaction() as db:
        before = old_opportunities(db, db.get(User, TEAM), "mine", 1, 10000, {})
    with database.engine.begin() as connection:
        for index in Opportunity.__table__.indexes:
            if index.name in QUERY_INDEXES:
                index.drop(connection)
    assert upgrade_query_indexes(database)
    assert not upgrade_query_indexes(database)
    assert QUERY_INDEXES <= {row["name"] for row in inspect(database.engine).get_indexes("opportunities")}
    runner = app.test_cli_runner()
    result = runner.invoke(args=["upgrade-query-indexes"])
    assert result.exit_code == 0 and "current" in result.output
    with database.transaction() as db:
        assert old_opportunities(db, db.get(User, TEAM), "mine", 1, 10000, {}) == before
    if database.engine.dialect.name == "sqlite":
        with database.engine.connect() as connection:
            for scope in ("active", "mine"):
                where = "status='PUBLISHED' AND expired_at IS NULL" if scope == "active" else "owner_user_id='be8_team'"
                plan = [row[3] for row in connection.exec_driver_sql(
                    "EXPLAIN QUERY PLAN SELECT id FROM opportunities WHERE " + where + " ORDER BY updated_at DESC, id LIMIT 20")]
                assert any("ix_opportunities_" + ("active" if scope == "active" else "owner") + "_page" in row for row in plan)
                assert not any("TEMP B-TREE" in row for row in plan)
    for index in Opportunity.__table__.indexes:
        if index.name in QUERY_INDEXES:
            assert "updated_at DESC" in str(CreateIndex(index).compile(dialect=mysql_dialect()))


def test_query_upgrade_rejects_uninitialised_database(tmp_path):
    from backend.src.db.database import Database
    database = Database(f"sqlite:///{(tmp_path / 'missing.db').as_posix()}")
    try:
        with pytest.raises(ValueError, match="init-db"):
            upgrade_query_indexes(database)
    finally:
        database.engine.dispose()


@contextmanager
def without_expired_column(database):
    # MySQL fixtures clear rows between tests, but deliberately reuse the schema.
    # DDL commits independently, so even an interrupted assertion needs repair.
    try:
        with database.engine.begin() as connection:
            for index in Opportunity.__table__.indexes:
                if index.name in QUERY_INDEXES:
                    index.drop(connection, checkfirst=True)
            connection.exec_driver_sql("ALTER TABLE opportunities DROP COLUMN expired_at")
        yield
    finally:
        upgrade_opportunity_search(database)
        upgrade_query_indexes(database)


def assert_opportunity_schema_usable(app, team):
    inspector = inspect(app.extensions["database"].engine)
    assert set(Opportunity.__table__.columns.keys()) <= {
        column["name"] for column in inspector.get_columns("opportunities")}
    assert QUERY_INDEXES <= {index["name"] for index in inspector.get_indexes("opportunities")}
    item = make_opportunity(team)
    response = team[0].get("/api/v1/opportunities")
    assert response.status_code == 200, response.get_json()
    assert item["id"] in {row["id"] for row in response.get_json()["items"]}


def test_query_upgrade_requires_legacy_column_upgrade(app, research_team):
    with without_expired_column(app.extensions["database"]):
        result = app.test_cli_runner().invoke(args=["upgrade-query-indexes"])
        assert result.exit_code != 0 and "upgrade-opportunity-search" in result.output
    assert_opportunity_schema_usable(app, research_team)


def test_query_upgrade_precondition_restores_schema_after_exception(app, research_team):
    with pytest.raises(RuntimeError, match="Interrupted legacy-schema test"):
        with without_expired_column(app.extensions["database"]):
            raise RuntimeError("Interrupted legacy-schema test")
    assert_opportunity_schema_usable(app, research_team)
