"""Cross-workflow acceptance using the versioned Sprint 2 preparation helper."""

from copy import deepcopy
from datetime import datetime, timedelta

import pytest

from backend.tests.conftest import PASSWORD, headers, sign_in
from backend.tests.data_preparation import prepare_run
from backend.tests.test_us09_frontend_integration import (
    test_us09_real_frontend_workflow as _document_workflow,
)

PROFILE = "/api/v1/me/profile"
OPPORTUNITIES = "/api/v1/opportunities"


@pytest.fixture
def prepared(tmp_path, record_property):
    run = prepare_run(tmp_path / "prepared", password=PASSWORD)
    record_property("datasetVersion", run.report["datasetVersion"])
    record_property("datasetSha256", run.report["datasetSha256"])
    try:
        yield run
    finally:
        run.close()


def checked(response, status=200):
    assert response.status_code == status, response.get_json()
    return response.get_json()


def opportunity_id(run):
    return run.report["opportunities"]["s2_opp_perfect_match"]["opportunityId"]


def test_independent_sessions_privacy_and_logout(prepared):
    """E2E-SESSION-01: concurrent role sessions and immediate consent enforcement."""
    talent, csrf = prepared.clients["s2_perfect_match"]
    team, team_csrf = prepared.clients["s2_team"]
    owner = checked(talent.get(PROFILE))
    path = f"{OPPORTUNITIES}/{opportunity_id(prepared)}/talent-matches"
    detail = path + "/" + owner["talentId"]
    assert checked(team.get(detail))["talent"]["fields"]["displayName"] == owner["content"]["displayName"]
    checked(team.put(PROFILE, json={"expectedRevision": owner["revision"],
        "content": owner["content"]}, headers=headers(team_csrf)), 403)
    assert checked(talent.get(PROFILE)) == owner
    privacy = checked(talent.get("/api/v1/me/privacy"))
    privacy = checked(talent.put("/api/v1/me/privacy", headers=headers(csrf), json={
        "expectedRevision": privacy["revision"], "discoverable": True,
        "visibleFields": ["displayName"]}))
    hidden = checked(team.get(detail))
    assert set(hidden["talent"]["fields"]) == {"displayName"}
    assert all(r["status"] == "UNKNOWN" and r["evidence"] == [] for r in hidden["requirements"])
    checked(talent.put("/api/v1/me/privacy", headers=headers(csrf), json={
        "expectedRevision": privacy["revision"], "discoverable": False, "visibleFields": []}))
    checked(team.get(detail), 404)
    assert owner["talentId"] not in {r["talent"]["talentId"] for r in checked(team.get(path))["items"]}
    assert talent.post("/api/v1/auth/logout", headers=headers(csrf)).status_code == 204
    checked(talent.get(PROFILE), 401)
    assert checked(team.get("/api/v1/auth/session"))["user"]["role"] == "RESEARCH_TEAM"
    assert checked(team.get(OPPORTUNITIES, query_string={"scope": "mine"}))["total"] == 7


def test_edit_reload_reconfirm_and_matching(prepared):
    """E2E-PROFILE-02: editing revokes eligibility until the saved revision is confirmed."""
    client, csrf = prepared.clients["s2_perfect_match"]
    team, _ = prepared.clients["s2_team"]
    before = checked(client.get(PROFILE))
    content = deepcopy(before["content"])
    content["displayName"] = "Reviewed test profile"
    saved = checked(client.put(PROFILE, headers=headers(csrf), json={
        "expectedRevision": before["revision"], "content": content}))
    assert saved["revision"] == before["revision"] + 1
    assert saved["confirmation"]["status"] == "UNCONFIRMED"
    checked(client.get("/api/v1/me/recommendations"), 409)
    detail = f"{OPPORTUNITIES}/{opportunity_id(prepared)}/talent-matches/{before['talentId']}"
    checked(team.get(detail), 404)
    returning = prepared.app.test_client()
    token = sign_in(returning, "s2_perfect_match@example.test")
    assert checked(returning.get(PROFILE))["content"] == content
    confirmed = checked(returning.post(PROFILE + "/confirmation", headers=headers(token),
        json={"expectedRevision": saved["revision"]}))
    assert confirmed["confirmation"]["confirmedRevision"] == saved["revision"]
    assert checked(returning.get("/api/v1/me/recommendations"))["total"] == 6
    assert checked(team.get(detail))["talent"]["fields"]["displayName"] == content["displayName"]


def test_search_combinations_on_prepared_records(prepared):
    """E2E-SEARCH-02: stable expected counts on the prepared published records."""
    talent, _ = prepared.clients["s2_perfect_match"]
    team, _ = prepared.clients["s2_team"]
    for query, total in [({}, 6), ({"q": "perfect match"}, 1),
                         ({"disciplineGroup": "STEM"}, 6),
                         ({"q": "perfect match", "university": "UNSW", "disciplineGroup": "STEM"}, 1),
                         ({"q": "unfindable-example"}, 0)]:
        for path in (OPPORTUNITIES, "/api/v1/me/recommendations"):
            assert checked(talent.get(path, query_string=query))["total"] == total
    checked(talent.get(OPPORTUNITIES, query_string={"q": ""}), 422)
    assert checked(talent.get(OPPORTUNITIES))["total"] == 6
    path = f"{OPPORTUNITIES}/{opportunity_id(prepared)}/talent-matches"
    assert checked(team.get(path))["total"] == 4
    assert checked(team.get(path, query_string={"q": "unfindable-example", "skill": "Python"}))["total"] == 0
    assert checked(team.get(path))["total"] == 4


def test_source_deadline_publication_and_boundary(prepared, monkeypatch):
    """E2E-EXPIRY-02: source persistence, publication and exact UTC expiry."""
    team, csrf = prepared.clients["s2_team"]
    talent, _ = prepared.clients["s2_perfect_match"]
    content = deepcopy(prepared.dataset["opportunities"][0]["content"])
    content.update(title="Deadline boundary example", sourceUrl="https://example.org/research",
                   deadlineAt="2099-01-01T00:00:00Z")
    draft = checked(team.post(OPPORTUNITIES, headers=headers(csrf), json=content), 201)
    assert draft["availabilityStatus"] == "DRAFT"
    path = f"{OPPORTUNITIES}/{draft['id']}"
    checked(talent.get(path), 404)
    item = checked(team.post(path + "/publish", headers=headers(csrf),
        json={"expectedRevision": draft["revision"]}))
    assert checked(talent.get(path))["content"]["sourceUrl"] == content["sourceUrl"]
    bad = {**item["content"], "sourceUrl": "javascript:void(0)"}
    checked(team.put(path, headers=headers(csrf), json={"expectedRevision": item["revision"], "content": bad}), 422)
    boundary = datetime(2099, 1, 1)
    now = [boundary - timedelta(microseconds=1)]
    for module in ("availability", "service"):
        monkeypatch.setattr(f"backend.src.features.opportunities.{module}.utcnow", lambda: now[0])
    for instant, count in ((now[0], 1), (boundary, 0), (boundary + timedelta(microseconds=1), 0)):
        now[0] = instant
        for listing in (OPPORTUNITIES, "/api/v1/me/recommendations"):
            assert checked(talent.get(listing, query_string={"q": content["title"]}))["total"] == count
        assert checked(talent.get(path))["availabilityStatus"] == ("ACTIVE" if count else "EXPIRED")
        checked(team.get(path + "/talent-matches"), 200 if count else 409)
    assert checked(team.get(path))["status"] == "PUBLISHED"


@pytest.mark.parametrize("format", ["pdf", "docx"])
def test_regression_35_review_correct_apply_reconfirm(prepared, request, tmp_path, monkeypatch, format):
    """E2E-REGRESSION-35: reuse the real upload, worker and React review workflow."""
    client, csrf = prepared.clients["s2_unconfirmed_profile"]
    before = checked(client.get(PROFILE))
    content = deepcopy(before["content"])
    for key, value in content.items():
        content[key] = [] if isinstance(value, list) else None if key == "disciplineGroup" else ""
    checked(client.put(PROFILE, headers=headers(csrf), json={
        "expectedRevision": before["revision"], "content": content}))
    monkeypatch.setenv("TEST_TALENT_IDENTIFIER", "s2_unconfirmed_profile@example.test")
    _document_workflow(prepared.app, request, tmp_path, format)
