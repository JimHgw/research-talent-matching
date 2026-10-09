"""US-02 contract, persistence, ownership and concurrent lifecycle acceptance."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime
import json
from threading import Barrier

import pytest
from sqlalchemy import event, select
from sqlalchemy.exc import IntegrityError

from backend.src.app import create_app
from backend.src.db.models import Opportunity, OpportunityRequirement, RequirementTag, Tag, User
from backend.src.features.auth.routes import provision_user
from backend.src.features.opportunities.service import published_opportunities
from backend.src.shared.paths import ROOT
from backend.src.shared.validation import validator
from conftest import PASSWORD, headers, sign_in

BASE = "/api/v1/opportunities"


def checked(response, status=200, schema="Opportunity"):
    data = response.get_json()
    assert response.status_code == status, data
    validator("Error" if status >= 400 else schema).validate(data)
    assert response.headers["Cache-Control"] == "no-store"
    if status >= 400:
        assert data["requestId"] == response.headers["X-Request-Id"]
    return data


def content():
    return json.loads((ROOT / "docs/api/examples/opportunity-create.json").read_text())


@pytest.fixture
def team(app):
    client = app.test_client()
    return client, sign_in(client, "team@example.test")


@pytest.fixture
def other_team(app):
    with app.app_context():
        provision_user("team2@example.test", PASSWORD, "Other team", "RESEARCH_TEAM")
    client = app.test_client()
    return client, sign_in(client, "team2@example.test")


def create(team, value=None):
    client, csrf = team
    return checked(client.post(BASE, json=content() if value is None else value,
                               headers=headers(csrf)), 201)


def save(team, opportunity, value=None, revision=None):
    client, csrf = team
    return client.put(f"{BASE}/{opportunity['id']}", headers=headers(csrf), json={
        "expectedRevision": opportunity["revision"] if revision is None else revision,
        "content": opportunity["content"] if value is None else value,
    })


def publish(team, opportunity, revision=None):
    client, csrf = team
    return client.post(f"{BASE}/{opportunity['id']}/publish", headers=headers(csrf), json={
        "expectedRevision": opportunity["revision"] if revision is None else revision,
    })


def listing(client, query=""):
    return checked(client.get(BASE + query), schema="OpportunityPage")


def test_lifecycle_noops_and_persistence(app, team, signed):
    client, _ = team
    talent, _ = signed
    draft = create(team, {**content(), "requirements": []})
    assert draft["revision"] == 1 and draft["status"] == "DRAFT"
    assert draft["createdAt"] == draft["updatedAt"]
    assert checked(client.get(f"{BASE}/{draft['id']}")) == draft
    assert checked(save(team, draft)) == draft
    checked(publish(team, draft), 422)
    assert listing(talent)["total"] == 0
    edited = checked(save(team, draft, content()))
    assert edited["revision"] == 2
    public = checked(publish(team, edited))
    assert public["status"] == "PUBLISHED" and public["revision"] == 3
    assert checked(publish(team, public)) == public
    assert checked(save(team, public)) == public
    assert listing(talent)["items"] == [public]
    edited_public = checked(save(team, public, {**content(), "title": "Updated after publication"}))
    assert edited_public["status"] == "PUBLISHED" and edited_public["revision"] == 4
    checked(save(team, edited_public, {**content(), "requirements": []}), 422)
    assert checked(talent.get(f"{BASE}/{draft['id']}")) == edited_public
    restarted = create_app(dict(app.config))
    try:
        reader = restarted.test_client()
        sign_in(reader)
        assert checked(reader.get(f"{BASE}/{draft['id']}")) == edited_public
    finally:
        restarted.extensions["database"].engine.dispose()


def test_drafts_and_owner_permissions(team, other_team, signed, app):
    draft = create(team)
    second = create(other_team)
    talent, talent_csrf = signed
    owner, _ = team
    other, other_csrf = other_team
    for client in (talent, other):
        checked(client.get(f"{BASE}/{draft['id']}"), 404)
        assert listing(client)["total"] == 0
    checked(talent.get(BASE + "?scope=mine"), 403)
    assert listing(owner, "?scope=mine")["items"] == [draft]
    assert listing(other, "?scope=mine")["items"] == [second]
    for published in (False, True):
        if published:
            draft = checked(publish(team, draft))
            assert checked(other.get(f"{BASE}/{draft['id']}")) == draft
        checked(save(other_team, draft), 404)
        checked(publish(other_team, draft), 404)
        checked(save((talent, talent_csrf), draft), 403)
        checked(publish((talent, talent_csrf), draft), 403)
    checked(talent.post(BASE, json=content(), headers=headers(talent_csrf)), 403)
    assert not {"owner", "ownerUserId", "owner_user_id", "email"} & draft.keys()
    with app.extensions["database"].transaction() as db:
        assert [row.id for row in db.scalars(published_opportunities())] == [draft["id"]]


@pytest.mark.parametrize("method,path", [("get", ""), ("get", "/missing"), ("post", ""),
                                        ("put", "/missing"), ("post", "/missing/publish")])
def test_authentication_required(client, method, path):
    checked(getattr(client, method)(BASE + path), 401)


@pytest.mark.parametrize("bad_headers", [{}, {"Origin": "https://other.example", "X-CSRF-Token": "csrf"},
                                       {"Origin": "http://127.0.0.1:5173", "X-CSRF-Token": "wrong"}])
def test_all_mutations_require_csrf(team, bad_headers):
    draft = create(team)
    client, csrf = team
    supplied = {k: csrf if v == "csrf" else v for k, v in bad_headers.items()}
    for method, path, body in [("post", "", content()),
                               ("put", f"/{draft['id']}", {"expectedRevision": 1, "content": content()}),
                               ("post", f"/{draft['id']}/publish", {"expectedRevision": 1})]:
        error = checked(getattr(client, method)(BASE + path, json=body, headers=supplied), 403)
        assert error["error"]["code"] == "CSRF_INVALID"


@pytest.mark.parametrize("query", ["scope=all", "scope=", "scope=mine&scope=published", "page=0",
    "page=-1", "page=1.5", "page=1e2", "page=abc", "page=", "page=1&page=2", "pageSize=0",
    "pageSize=101", "pageSize=20.0", "pageSize=true"])
def test_invalid_list_parameters(team, query):
    checked(team[0].get(BASE + "?" + query), 422)


def test_filter_count_order_and_pagination(app, team, other_team, signed):
    owner_items = [create(team, {**content(), "title": f"Opportunity {i}"}) for i in range(3)]
    other = create(other_team)
    published = [checked(publish(team, owner_items[0])), checked(publish(other_team, other))]
    # A tied timestamp must fall back to ID order, not insertion or row order.
    with app.extensions["database"].transaction(write=True) as db:
        for row in db.scalars(select(Opportunity)):
            row.updated_at = datetime(2026, 10, 1)
        db.get(Opportunity, owner_items[2]["id"]).updated_at = datetime(2026, 10, 2)
    expected = [owner_items[2]["id"]] + sorted(item["id"] for item in owner_items[:2])
    actual = [listing(team[0], f"?scope=mine&pageSize=1&page={i}") for i in range(1, 4)]
    assert [page["items"][0]["id"] for page in actual] == expected
    assert all(page["total"] == 3 for page in actual)
    visible = listing(signed[0], "?pageSize=100")
    assert [item["id"] for item in visible["items"]] == sorted(item["id"] for item in published)
    assert visible["total"] == 2
    for query in ("?scope=mine&page=4&pageSize=1", "?page=" + "9" * 100):
        assert listing(team[0], query)["items"] == []


@pytest.mark.parametrize("mutation", [
    lambda c: c.update(ownerUserId="other"), lambda c: c.update(status="PUBLISHED"),
    lambda c: c.update(revision=50), lambda c: c.pop("title"),
    lambda c: c.update(title=""), lambda c: c.update(title="a" * 201),
    lambda c: c.update(description="a" * 10001), lambda c: c.update(disciplineGroup="OTHER"),
    lambda c: c["requirements"].append(deepcopy(c["requirements"][0])),
    lambda c: c["requirements"][0].update(id="invalid id"),
    lambda c: c["requirements"][0].update(label=""),
    lambda c: c["requirements"][0].update(importance="OPTIONAL"),
    lambda c: c["requirements"][0].update(tagIds=[]),
    lambda c: c["requirements"][0].update(tagIds=["missing"]),
    lambda c: c["requirements"][0].update(tagIds=["skill_python", "skill_python"]),
    lambda c: c["requirements"][0].update(kind="INTEREST"),
    lambda c: c.update(requirements=[{**c["requirements"][0], "id": f"req_{i}"} for i in range(51)]),
])
def test_invalid_creation_is_atomic(team, mutation):
    value = content()
    mutation(value)
    client, csrf = team
    checked(client.post(BASE, json=value, headers=headers(csrf)), 422)
    assert listing(client, "?scope=mine")["total"] == 0


def test_ordered_replacement_ids_and_failed_updates(team):
    value = content()
    value["requirements"].append({"id": "interest", "label": "Interest in ML", "kind": "INTEREST",
                                  "importance": "PREFERRED", "tagIds": ["interest_ml"]})
    draft = create(team, value)
    updated = deepcopy(value)
    updated["requirements"].reverse()
    updated["requirements"][3]["tagIds"].reverse()
    result = checked(save(team, draft, updated))
    assert result["content"] == updated
    broken = deepcopy(updated)
    broken["requirements"][0]["tagIds"] = ["skill_python"]
    error = checked(save(team, result, broken), 422)
    assert error["error"]["fieldErrors"][0]["field"] == "content.requirements[0].tagIds[0]"
    assert checked(team[0].get(f"{BASE}/{draft['id']}")) == result
    cleared = checked(save(team, result, {**updated, "requirements": []}))
    assert cleared["content"]["requirements"] == []
    # IDs need only be unique within each opportunity.
    assert create(team, value)["content"] == value


def test_stale_revision_is_rejected_even_for_noop_or_republish(team):
    draft = create(team)
    public = checked(publish(team, draft))
    for response in (save(team, public, revision=1), publish(team, public, revision=1)):
        error = checked(response, 409)["error"]
        assert error["code"] == "REVISION_CONFLICT" and error["currentRevision"] == 2
    assert checked(team[0].get(f"{BASE}/{draft['id']}")) == public


@pytest.mark.parametrize("mode", ["save", "publish", "mixed"])
def test_concurrent_writers_cannot_overwrite_each_other(app, team, mode):
    draft = create(team)
    clients = [(app.test_client(), None) for _ in range(2)]
    clients = [(client, sign_in(client, "team@example.test")) for client, _ in clients]
    barrier = Barrier(2)
    def write(index):
        barrier.wait(timeout=5)
        if mode == "publish" or (mode == "mixed" and index == 1):
            return publish(clients[index], draft)
        return save(clients[index], draft, {**draft["content"], "title": f"Writer {index}"})
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(write, range(2)))
    assert sorted(response.status_code for response in responses) == [200, 409]
    winner = next(checked(response) for response in responses if response.status_code == 200)
    assert winner["revision"] == 2
    assert checked(team[0].get(f"{BASE}/{draft['id']}")) == winner


def test_rollback_after_child_write_failure(app, team):
    draft = create(team)
    engine = app.extensions["database"].engine
    def fail_tags(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO requirement_tags"):
            raise RuntimeError("Synthetic write failure")
    event.listen(engine, "before_cursor_execute", fail_tags)
    try:
        checked(save(team, draft, {**draft["content"], "title": "Must roll back"}), 500)
    finally:
        event.remove(engine, "before_cursor_execute", fail_tags)
    assert checked(team[0].get(f"{BASE}/{draft['id']}")) == draft


def test_foreign_keys_restrict_independent_resource_deletion(app, team):
    draft = create(team)
    database = app.extensions["database"]
    with database.transaction() as db:
        opportunity = db.get(Opportunity, draft["id"])
        assert opportunity.owner.role == "RESEARCH_TEAM"
        requirement = db.get(OpportunityRequirement, (draft["id"], "req_python"))
        assert requirement.opportunity.id == draft["id"]
        relation = db.get(RequirementTag, (draft["id"], "req_python", "skill_python"))
        assert relation.requirement.id == "req_python" and relation.tag.kind == "SKILL"
        owner_id = opportunity.owner_user_id
    for model, key in ((User, owner_id), (Tag, "skill_python"), (Opportunity, draft["id"])):
        with pytest.raises(IntegrityError), database.transaction(write=True) as db:
            db.delete(db.get(model, key))
    assert checked(team[0].get(f"{BASE}/{draft['id']}")) == draft
