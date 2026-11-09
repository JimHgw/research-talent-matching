"""US-20: UTC deadline boundaries, retained records and explicit reopening."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import inspect

from backend.src.app import create_app
from backend.src.db.models import Opportunity
from backend.src.db.opportunity_upgrade import upgrade_opportunity_search
from conftest import headers, sign_in
from test_us02 import BASE, checked, content, create, other_team, publish, save, team
from test_us04 import confirm_profile
from test_us05 import share

RECOMMENDATIONS = "/api/v1/me/recommendations"
DEADLINE_ERROR = (
    "Enter a valid RFC3339 deadline (years 1000-9999) with an explicit time zone and at most six "
    "fractional digits, for example 2027-01-01T17:00:00+11:00."
)


@pytest.fixture
def clock(monkeypatch):
    # Freeze opportunity availability only; authentication keeps its own clock.
    value = [datetime(2098, 12, 31)]
    for module in ("availability", "service"):
        monkeypatch.setattr(
            f"backend.src.features.opportunities.{module}.utcnow", lambda: value[0]
        )
    return value


@pytest.fixture
def talent(signed):
    profile = confirm_profile(signed)
    share(signed, ["skills", "researchInterests"])
    return signed, profile["talentId"]


def published(team, **changes):
    return checked(publish(team, create(team, {**content(), **changes})))


def update(team, item, changes, *, reopen=False, revision=None):
    return team[0].put(f"{BASE}/{item['id']}", headers=headers(team[1]), json={
        "expectedRevision": item["revision"] if revision is None else revision,
        "content": {**item["content"], **changes},
        "reopen": reopen,
    })


def assert_active_results(team, talent, item, *, active):
    signed, talent_id = talent
    for url, schema, nested in (
        (BASE, "OpportunityPage", False),
        (RECOMMENDATIONS, "RecommendationPage", True),
    ):
        for query in ({}, {"q": item["content"]["title"]}):
            page = checked(signed[0].get(url, query_string=query), schema=schema)
            assert page["total"] == (1 if active else 0)
            ids = [(row["opportunity"] if nested else row)["id"] for row in page["items"]]
            assert ids == ([item["id"]] if active else [])

    path = f"{BASE}/{item['id']}"
    for client in (team[0], signed[0]):
        detail = checked(client.get(path))
        assert detail["status"] == "PUBLISHED"
        assert detail["availabilityStatus"] == ("ACTIVE" if active else "EXPIRED")
    owned = checked(team[0].get(BASE, query_string={"scope": "mine"}), schema="OpportunityPage")
    assert owned["total"] == 1
    assert owned["items"][0]["id"] == item["id"]
    assert owned["items"][0]["availabilityStatus"] == ("ACTIVE" if active else "EXPIRED")

    for client, url, schema in (
        (signed[0], f"/api/v1/me/opportunity-matches/{item['id']}", "OwnerMatch"),
        (team[0], f"{path}/talent-matches", "TalentMatchPage"),
        (team[0], f"{path}/talent-matches/{talent_id}", "TeamMatch"),
    ):
        response = client.get(url)
        if active:
            data = checked(response, schema=schema)
            if schema == "TalentMatchPage":
                assert data["total"] == 1
        else:
            assert checked(response, status=409)["error"]["code"] == "OPPORTUNITY_EXPIRED"


@pytest.mark.parametrize("deadline", [
    "2099-01-01T00:00:00Z", "2099-01-01T11:00:00+11:00", None,
])
@pytest.mark.parametrize("offset_us", [-1, 0, 1])
def test_deadline_before_at_after_and_no_deadline(app, team, talent, clock, deadline, offset_us):
    item = published(team, deadlineAt=deadline)
    clock[0] = datetime(2099, 1, 1) + timedelta(microseconds=offset_us)
    assert_active_results(team, talent, item, active=deadline is None or offset_us < 0)
    if deadline is not None:
        detail = checked(team[0].get(f"{BASE}/{item['id']}"))
        assert detail["content"]["deadlineAt"] == "2099-01-01T00:00:00.000000Z"
    # Expiry is derived without deleting or rewriting the stored publication.
    with app.extensions["database"].transaction() as db:
        row = db.get(Opportunity, item["id"])
        assert row is not None and row.status == "PUBLISHED"
        assert row.revision == item["revision"]


@pytest.mark.parametrize("value", [
    "", "not-a-date", "2099-01-01", "2099-01-01T00:00:00",
    "2099-02-30T00:00:00Z", "2099-01-01T24:00:00Z",
    "2099-01-01T00:00:00+25:00", "2099-01-01T00:00:00.1234567Z",
    "0001-01-01T00:00:00+01:00", "0001-01-01T00:00:00Z",
    "1000-01-01T00:00:00+01:00", 42, False, {}, [],
])
def test_invalid_deadline_create_and_edit_are_clear_and_atomic(team, value):
    item = published(team, deadlineAt="2099-01-01T00:00:00Z")
    for response in (
        team[0].post(BASE, headers=headers(team[1]), json={**content(), "deadlineAt": value}),
        update(team, item, {"deadlineAt": value, "title": "Must roll back"}),
    ):
        error = checked(response, status=422)["error"]
        assert error["code"] == "VALIDATION_ERROR"
        assert error["fieldErrors"] == [{"field": "content.deadlineAt", "message": DEADLINE_ERROR}]
    assert checked(team[0].get(f"{BASE}/{item['id']}")) == item
    assert checked(team[0].get(BASE), schema="OpportunityPage")["total"] == 1


def test_saved_deadline_change_survives_restart_and_controls_expiry(app, team, talent, clock):
    item = published(team, deadlineAt="2099-01-01T11:00:00+11:00")
    item = checked(update(team, item, {"deadlineAt": "2099-02-01T11:00:00.123456+11:00"}))
    assert item["content"]["deadlineAt"] == "2099-02-01T00:00:00.123456Z"
    clock[0] = datetime(2099, 1, 1)
    assert_active_results(team, talent, item, active=True)

    restarted = create_app(dict(app.config))
    try:
        client = restarted.test_client()
        sign_in(client, "team@example.test")
        assert checked(client.get(f"{BASE}/{item['id']}")) == item
    finally:
        restarted.extensions["database"].engine.dispose()

    # Legacy edits omit the optional field without clearing the saved deadline.
    legacy = {key: value for key, value in item["content"].items() if key != "deadlineAt"}
    assert checked(save(team, item, legacy)) == item
    clock[0] = datetime(2099, 2, 1, microsecond=123455)
    assert_active_results(team, talent, item, active=True)
    clock[0] += timedelta(microseconds=1)
    assert_active_results(team, talent, item, active=False)


@pytest.mark.parametrize("deadline", ["2099-02-01T00:00:00Z", None])
def test_deadline_edit_requires_explicit_reopening(team, talent, clock, deadline):
    item = published(team, deadlineAt="2099-01-01T00:00:00Z")
    clock[0] = datetime(2099, 1, 1)
    item = checked(update(team, item, {"deadlineAt": deadline}))
    assert_active_results(team, talent, item, active=False)
    assert checked(publish(team, item))["availabilityStatus"] == "EXPIRED"
    assert checked(update(team, item, {}, reopen=True, revision=item["revision"] - 1),
                   status=409)["error"]["code"] == "REVISION_CONFLICT"
    previous_revision = item["revision"]
    item = checked(update(team, item, {}, reopen=True))
    assert item["revision"] == previous_revision + 1
    assert_active_results(team, talent, item, active=True)
    assert checked(update(team, item, {}, reopen=True)) == item


@pytest.mark.parametrize("deadline", ["2099-02-01T00:00:00Z", None])
def test_reopening_applies_new_deadline_in_one_save(team, talent, clock, deadline):
    item = published(team, deadlineAt="2099-01-01T00:00:00Z")
    clock[0] = datetime(2099, 1, 1)
    reopened = checked(update(team, item, {"deadlineAt": deadline}, reopen=True))
    assert reopened["revision"] == item["revision"] + 1
    if deadline is None:
        assert "deadlineAt" not in reopened["content"]
    else:
        assert reopened["content"]["deadlineAt"] == "2099-02-01T00:00:00.000000Z"
    assert_active_results(team, talent, reopened, active=True)


def test_active_deadline_can_be_cleared_without_reopening(team, talent, clock):
    item = published(team, deadlineAt="2099-01-01T00:00:00Z")
    item = checked(update(team, item, {"deadlineAt": None}))
    assert "deadlineAt" not in item["content"]
    clock[0] = datetime(2099, 2, 1)
    assert_active_results(team, talent, item, active=True)


@pytest.mark.parametrize("offset_us", [-1, 0])
def test_reopen_at_or_before_now_is_rejected_atomically(team, talent, clock, offset_us):
    item = published(team, deadlineAt="2099-01-01T00:00:00Z")
    clock[0] = datetime(2099, 1, 1)
    deadline = (clock[0] + timedelta(microseconds=offset_us)).isoformat() + "Z"
    error = checked(update(team, item, {"deadlineAt": deadline, "title": "Must roll back"},
                           reopen=True), status=422)["error"]
    assert error["fieldErrors"] == [{
        "field": "content.deadlineAt", "message": "Choose a future deadline before reopening.",
    }]
    current = checked(team[0].get(f"{BASE}/{item['id']}"))
    assert current == {**item, "availabilityStatus": "EXPIRED"}
    assert_active_results(team, talent, item, active=False)


@pytest.mark.parametrize("reopen", [False, True])
def test_only_authorised_owner_can_change_deadline_or_reopen(app, team, other_team, signed, clock, reopen):
    item = published(team, deadlineAt="2099-01-01T00:00:00Z")
    clock[0] = datetime(2099, 1, 1)
    change = {"deadlineAt": "2099-02-01T00:00:00Z"}
    checked(update(other_team, item, change, reopen=reopen), status=404)
    checked(update(signed, item, change, reopen=reopen), status=403)
    checked(app.test_client().put(f"{BASE}/{item['id']}", json={
        "expectedRevision": item["revision"], "content": {**item["content"], **change},
        "reopen": reopen,
    }), status=401)
    checked(team[0].put(f"{BASE}/{item['id']}", json={
        "expectedRevision": item["revision"], "content": {**item["content"], **change},
        "reopen": reopen,
    }), status=403)
    assert checked(team[0].get(f"{BASE}/{item['id']}")) == {**item, "availabilityStatus": "EXPIRED"}


def test_draft_cannot_be_reopened_or_published_with_expired_deadline(team, clock):
    item = create(team, {**content(), "deadlineAt": "2099-01-01T00:00:00Z"})
    clock[0] = datetime(2099, 1, 1)
    assert checked(update(team, item, {"deadlineAt": None}, reopen=True),
                   status=409)["error"]["code"] == "OPPORTUNITY_NOT_PUBLISHED"
    checked(publish(team, item), status=422)
    assert checked(team[0].get(f"{BASE}/{item['id']}")) == item
    assert checked(team[0].get(BASE), schema="OpportunityPage")["items"] == []


def test_legacy_database_upgrade_supports_deadline_and_retains_expired_record(app, team, talent, clock):
    item = published(team)
    database = app.extensions["database"]
    with database.engine.begin() as connection:
        for index in Opportunity.__table__.indexes:
            if index.name == "ix_opportunities_active_page":
                index.drop(connection, checkfirst=True)
        for name in ("deadline_at", "expired_at"):
            connection.exec_driver_sql(f"ALTER TABLE opportunities DROP COLUMN {name}")
    assert upgrade_opportunity_search(database) is True
    assert upgrade_opportunity_search(database) is False
    columns = {column["name"]: column for column in inspect(database.engine).get_columns("opportunities")}
    assert all(columns[name]["nullable"] for name in ("deadline_at", "expired_at"))
    if database.engine.dialect.name == "mysql":
        assert columns["deadline_at"]["type"].fsp == 6
    assert checked(team[0].get(f"{BASE}/{item['id']}")) == item
    item = checked(update(team, item, {"deadlineAt": "2099-01-01T00:00:00.123456Z"}))
    clock[0] = datetime(2099, 1, 1, microsecond=123456)
    assert_active_results(team, talent, item, active=False)
