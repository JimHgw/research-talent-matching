"""US-19 real API, persistence, privacy, additive upgrade and evidence boundaries."""

from copy import deepcopy

import pytest
from sqlalchemy import inspect

from backend.src.app import create_app
from backend.src.db.opportunity_upgrade import upgrade_opportunity_search
from backend.src.shared.validation import SOURCE_URL_ERROR
from conftest import headers, sign_in
from test_us02 import BASE, checked, content, create, other_team, publish, save, team
from test_us04 import confirm_profile


@pytest.mark.parametrize("url", [
    "https://www.unsw.edu.au/research",
    "http://www.google.com/search?q=research#details",
    "https://www.linkedin.com/jobs/view/123/",
    "HTTPS://example.org/search?q=研究",
    "http://[::1]:8000/path",
    "https://example.org/" + "a" * (2048 - len("https://example.org/")),
])
def test_source_add_edit_omit_remove_and_restart(app, team, url):
    item = create(team, {**content(), "sourceUrl": url})
    assert item["content"]["sourceUrl"] == url
    item = checked(publish(team, item))
    path = f"{BASE}/{item['id']}"

    restarted = create_app(dict(app.config))
    try:
        reader = restarted.test_client()
        sign_in(reader)
        assert checked(reader.get(path)) == item
    finally:
        restarted.extensions["database"].engine.dispose()

    # An older client edits another field without sending sourceUrl.
    value = deepcopy(item["content"])
    value.pop("sourceUrl")
    value["title"] = "Source-preserving legacy edit"
    item = checked(save(team, item, value))
    assert item["content"]["sourceUrl"] == url

    value = {**item["content"], "sourceUrl": "https://example.org/updated?q=1#part"}
    previous_revision = item["revision"]
    item = checked(save(team, item, value))
    assert item["revision"] == previous_revision + 1
    assert item["content"]["sourceUrl"] == value["sourceUrl"]
    assert checked(save(team, item)) == item

    item = checked(save(team, item, {**item["content"], "sourceUrl": None}))
    assert "sourceUrl" not in item["content"]
    assert checked(team[0].get(path)) == item
    assert checked(save(team, item, {**item["content"], "sourceUrl": None})) == item


@pytest.mark.parametrize("url", [
    "", "   ", "javascript:alert(1)", "ftp://example.org/file", "//example.org/path",
    "https://", "https://example.org:99999", "https://example.org:abc",
    "https://user:password@example.org", "https://example.org/a b",
    "https://example.org/\\path", "https://example.org/%ZZ",
    "https://example.org/\npath", "https://example.org/" + "a" * 2048,
    42, False, [], {},
])
def test_invalid_source_is_clear_and_atomic(team, url):
    item = create(team, {**content(), "sourceUrl": "https://example.org/original"})
    value = {**item["content"], "sourceUrl": url}
    for response in (
        save(team, item, value),
        team[0].post(BASE, json=value, headers=headers(team[1])),
    ):
        error = checked(response, status=422)["error"]
        assert error["code"] == "VALIDATION_ERROR"
        assert error["fieldErrors"] == [{"field": "content.sourceUrl", "message": SOURCE_URL_ERROR}]
    assert checked(team[0].get(f"{BASE}/{item['id']}")) == item


def test_only_owner_can_change_source(app, team, other_team, signed):
    item = checked(publish(team, create(team, {**content(), "sourceUrl": "https://example.org/owner"})))
    changed = {**item["content"], "sourceUrl": "https://example.org/other"}
    checked(save(other_team, item, changed), status=404)
    checked(save(signed, item, changed), status=403)
    checked(app.test_client().put(f"{BASE}/{item['id']}", json={
        "expectedRevision": item["revision"], "content": changed,
    }), status=401)
    assert checked(team[0].get(f"{BASE}/{item['id']}")) == item


def test_stale_source_write_cannot_overwrite_current_value(team):
    original = create(team)
    saved = checked(save(team, original, {**original["content"], "sourceUrl": "https://example.org/current"}))
    checked(save(team, original, {**original["content"], "sourceUrl": "https://example.org/stale"}), status=409)
    assert checked(team[0].get(f"{BASE}/{original['id']}")) == saved


def test_unset_and_explicit_null_sources_work(team):
    for value in (content(), {**content(), "sourceUrl": None}):
        item = checked(publish(team, create(team, value)))
        assert "sourceUrl" not in item["content"]
        assert checked(team[0].get(f"{BASE}/{item['id']}")) == item


def test_source_is_not_fetched_or_used_as_evidence(team, signed, monkeypatch):
    confirm_profile(signed)
    item = checked(publish(team, create(team)))
    url = f"/api/v1/me/opportunity-matches/{item['id']}"
    before = checked(signed[0].get(url), schema="OwnerMatch")

    def forbidden(*args, **kwargs):
        raise AssertionError("A source URL must not trigger an HTTP request.")

    monkeypatch.setattr("urllib.request.urlopen", forbidden)
    monkeypatch.setattr("http.client.HTTPConnection.request", forbidden)
    item = checked(save(team, item, {**item["content"], "sourceUrl": "https://example.org/research"}))
    after = checked(signed[0].get(url), schema="OwnerMatch")
    assert after["summary"] == before["summary"]
    assert after["requirements"] == before["requirements"]
    assert checked(signed[0].get(f"{BASE}/{item['id']}"))["content"]["sourceUrl"] == item["content"]["sourceUrl"]
    page = checked(signed[0].get(BASE), schema="OpportunityPage")
    assert page["items"][0]["content"]["sourceUrl"] == item["content"]["sourceUrl"]


def test_old_opportunity_table_upgrade_preserves_records_and_allows_source(app, team):
    item = create(team)
    database = app.extensions["database"]
    with database.engine.begin() as connection:
        connection.exec_driver_sql("ALTER TABLE opportunities DROP COLUMN source_url")
    assert "source_url" not in {column["name"] for column in inspect(database.engine).get_columns("opportunities")}
    assert upgrade_opportunity_search(database) is True
    assert upgrade_opportunity_search(database) is False
    column = next(column for column in inspect(database.engine).get_columns("opportunities")
                  if column["name"] == "source_url")
    assert column["nullable"] is True
    assert column["type"].length == 2048
    path = f"{BASE}/{item['id']}"
    assert checked(team[0].get(path)) == item
    saved = checked(save(team, item, {**item["content"], "sourceUrl": "https://example.org/upgraded"}))
    assert checked(team[0].get(path)) == saved
