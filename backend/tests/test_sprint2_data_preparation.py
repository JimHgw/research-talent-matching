"""Source-aware, isolated preparation and independently labelled matching cases."""

from copy import deepcopy
import json
import secrets

import pytest
from sqlalchemy import func, select

from backend.src.db.models import User, TalentProfile, Opportunity
from backend.src.features.auth.routes import provision_user
from backend.src.features.matching.engine import evaluate_opportunity
from backend.src.shared.validation import validator
from backend.tests.conftest import headers
from backend.tests.data_preparation import DATASET, FILES, digest, load_dataset, prepare_run


@pytest.fixture(scope="module")
def prepared(tmp_path_factory):
    run = prepare_run(tmp_path_factory.mktemp("sprint2") / "initial")
    yield run
    run.close()


def test_manifest_sources_and_independent_labels(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Loading expectations must not execute matching.")
    monkeypatch.setattr("backend.src.features.matching.engine.evaluate_opportunity", forbidden)
    data = load_dataset()
    manifest = data["manifest"]
    assert manifest["datasetVersion"] == "sprint2-synthetic-v1"
    assert manifest["sourceStatus"] == "AUTHORISED_REAL_INPUT_REQUIRED"
    assert manifest["authorisedRealExamples"] == 0
    assert all(s["sourceCategory"] == "synthetic" and not s["originalFileRetained"]
               and not s["originalContainsPrivateInformation"] for s in manifest["sources"])
    assert len(manifest["sources"]) == 17
    scenarios = {item["purpose"] for item in data["talents"]}
    assert {"perfect_match", "partial_multi_tag_requirement", "explicit_negative_gap",
            "missing_information", "unmatched_tags", "incomplete_profile", "no_matching_criteria",
            "hidden_information", "private_profile", "unconfirmed_profile"} == scenarios
    assert {s for case in data["expected-results"]["cases"] for s in case.get("statuses", [])} == {
        "MATCHED", "PARTIAL", "GAP", "UNKNOWN"}
    assert manifest["deadlineSupported"] is False


@pytest.mark.parametrize("mutation", ["duplicate", "source", "version", "schema", "tag", "state"])
def test_invalid_dataset_refused_before_directory_creation(tmp_path, mutation):
    data = load_dataset()
    if mutation == "duplicate":
        data["talents"].append(deepcopy(data["talents"][0]))
    elif mutation == "source":
        data["manifest"]["sources"].pop()
    elif mutation == "version":
        data["expected-results"]["datasetVersion"] = "different"
    elif mutation == "schema":
        data["opportunities"][0]["content"]["deadline"] = "2027-01-01"
    elif mutation == "tag":
        data["talents"][0]["content"]["skills"][0]["tagId"] = "missing_tag"
    else:
        data["talents"][0]["state"]["profileRevision"] = 99
    directory = tmp_path / "dataset"
    directory.mkdir()
    for filename in FILES:
        (directory / filename).write_text(json.dumps(data[filename.removesuffix(".json")]), encoding="utf-8")
    with pytest.raises(Exception):
        prepare_run(tmp_path / "run", dataset_directory=directory)
    assert not (tmp_path / "run").exists()


def test_structures_and_starting_states(prepared):
    report = prepared.report
    assert report["datasetSha256"] == digest(prepared.dataset)
    for record in prepared.dataset["talents"]:
        client, _ = prepared.clients[record["id"]]
        profile = client.get("/api/v1/me/profile").json
        validator("Profile").validate(profile)
        assert profile["content"] == record["content"]
        assert profile["revision"] == record["state"]["profileRevision"]
        assert profile["confirmation"]["status"] == record["state"]["confirmationStatus"]
        assert profile["confirmation"]["confirmedRevision"] == (
            profile["revision"] if record["state"]["confirmationStatus"] == "CONFIRMED" else None)
        privacy = client.get("/api/v1/me/privacy").json
        assert privacy["visibleFields"] == sorted(record["state"]["visibleFields"])
        assert privacy["discoverable"] == record["state"]["discoverable"]
        assert report["talents"][record["id"]]["contentSha256"] == digest(record["content"])
    for record in prepared.dataset["opportunities"]:
        client, _ = prepared.clients[record["owner"]]
        identifier = report["opportunities"][record["id"]]["opportunityId"]
        opportunity = client.get("/api/v1/opportunities/" + identifier).json
        validator("Opportunity").validate(opportunity)
        assert opportunity["content"] == record["content"]
        assert {key: opportunity[key] for key in ("status", "revision")} == record["state"]


@pytest.mark.parametrize("case", load_dataset()["expected-results"]["cases"], ids=lambda c: c["id"])
def test_prepared_matching_against_manual_labels(prepared, case, record_property):
    record_property("datasetVersion", prepared.report["datasetVersion"])
    record_property("datasetSha256", prepared.report["datasetSha256"])
    opportunity_id = prepared.report["opportunities"][case["opportunity"]]["opportunityId"]
    if case["audience"] == "engine":
        # Empty criteria cannot be published. Preserve the existing US-06 engine-only case.
        record = next(r for r in prepared.dataset["opportunities"] if r["id"] == case["opportunity"])
        requirements, summary = evaluate_opportunity(record, {})
    else:
        if case["audience"] == "owner":
            client, _ = prepared.clients[case["talent"]]
            url = f"/api/v1/me/opportunity-matches/{opportunity_id}"
        else:
            client, _ = prepared.clients["s2_team"]
            talent_id = prepared.report["talents"][case["talent"]]["talentId"]
            url = f"/api/v1/opportunities/{opportunity_id}/talent-matches/{talent_id}"
        response = client.get(url)
        assert response.status_code == case["httpStatus"], response.json
        if case["httpStatus"] != 200:
            validator("Error").validate(response.json)
            assert response.json["error"]["code"] == (
                "PROFILE_UNCONFIRMED" if case["httpStatus"] == 409 else "NOT_FOUND")
            return
        validator("OwnerMatch" if case["audience"] == "owner" else "TeamMatch").validate(response.json)
        requirements, summary = response.json["requirements"], response.json["summary"]
    assert [r["status"] for r in requirements] == case["statuses"]
    assert {key: summary[key] for key in case["summary"]} == case["summary"]
    assert summary["algorithmVersion"] == prepared.report["algorithmVersion"]
    if case["id"] == "hidden_information":
        assert set(response.json["talent"]["fields"]) == {"displayName"}
        assert all(r["evidence"] == [] for r in requirements)


def test_discovery_exclusions_and_no_source_metadata(prepared):
    client, _ = prepared.clients["s2_team"]
    identifier = prepared.report["opportunities"]["s2_opp_perfect_match"]["opportunityId"]
    url = f"/api/v1/opportunities/{identifier}/talent-matches"
    page = client.get(url).json
    actual = {item["talent"]["talentId"] for item in page["items"]}
    expected = {prepared.report["talents"][r["id"]]["talentId"] for r in prepared.dataset["talents"]
                if r["state"]["discoverable"] and r["state"]["confirmationStatus"] == "CONFIRMED"}
    assert actual == expected and page["total"] == len(expected)
    def no_private_keys(value):
        if isinstance(value, dict):
            assert not set(value) & {"sources", "sourceReference", "email", "password", "password_hash",
                "documentId", "storageKey", "downloadUrl", "origins", "originalFileRetained"}
            for nested in value.values():
                no_private_keys(nested)
        elif isinstance(value, list):
            for nested in value:
                no_private_keys(nested)
    no_private_keys(page)
    no_private_keys(prepared.report)
    for talent_id in actual:
        no_private_keys(client.get(url + "/" + talent_id).json)
    other, _ = prepared.clients["s2_other_team"]
    assert other.get(url).status_code == 404
    draft = prepared.report["opportunities"]["s2_opp_no_matching_criteria"]["opportunityId"]
    talent, _ = prepared.clients["s2_perfect_match"]
    assert talent.get("/api/v1/opportunities/" + draft).status_code == 404


def test_restore_is_deterministic_and_preserves_existing_data(tmp_path, monkeypatch):
    # Ambient configuration must never select a shared database.
    sentinel = tmp_path / "unrelated.sqlite3"
    sentinel.write_bytes(b"Unrelated existing database must not be opened.")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///" + sentinel.as_posix())
    first = prepare_run(tmp_path / "first")
    try:
        with first.app.app_context():
            unrelated = provision_user("unrelated@example.test", secrets.token_urlsafe(32) + "aA1!",
                                       "Unrelated test account", "TALENT")
        team, team_csrf = first.clients["s2_team"]
        extra_content = deepcopy(first.dataset["opportunities"][0]["content"])
        extra_content["title"] = "Unrelated opportunity created during testing"
        extra = team.post("/api/v1/opportunities", headers=headers(team_csrf), json=extra_content)
        assert extra.status_code == 201
        extra_id = extra.json["id"]
        document = tmp_path / "first/documents/unrelated.txt"
        document.parent.mkdir()
        document.write_text("Existing document", encoding="utf-8")
        client, csrf = first.clients["s2_perfect_match"]
        profile = client.get("/api/v1/me/profile").json
        changed = deepcopy(profile["content"])
        changed["displayName"] = "Changed during test"
        assert client.put("/api/v1/me/profile", headers=headers(csrf), json={
            "expectedRevision": profile["revision"], "content": changed}).status_code == 200
        db_path = tmp_path / "first/test.sqlite3"
        before = db_path.read_bytes()
        with pytest.raises(FileExistsError):
            prepare_run(tmp_path / "first")
        assert db_path.read_bytes() == before
        second = prepare_run(tmp_path / "restored")
        try:
            def semantic_state(report):
                return {section: {key: {k: v for k, v in record.items()
                        if k not in ("userId", "talentId", "opportunityId")}
                        for key, record in report[section].items()}
                        for section in ("accounts", "talents", "opportunities")}
            assert semantic_state(first.report) == semantic_state(second.report)
            assert first.report["datasetSha256"] == second.report["datasetSha256"]
            for run, users in ((first, 13), (second, 12)):
                with run.app.extensions["database"].transaction() as db:
                    assert db.scalar(select(func.count()).select_from(User)) == users
                    assert db.scalar(select(func.count()).select_from(TalentProfile)) == users - 2
                    assert db.scalar(select(func.count()).select_from(Opportunity)) == (8 if run is first else 7)
            with first.app.extensions["database"].transaction() as db:
                assert db.get(User, unrelated) is not None
            assert client.get("/api/v1/me/profile").json["content"] == changed
            assert team.get("/api/v1/opportunities/" + extra_id).json["content"] == extra_content
            restored, _ = second.clients["s2_perfect_match"]
            assert restored.get("/api/v1/me/profile").json["content"]["displayName"] != changed["displayName"]
            assert document.read_text() == "Existing document"
            assert sentinel.read_bytes() == b"Unrelated existing database must not be opened."
        finally:
            second.close()
    finally:
        first.close()


def test_committed_dataset_has_no_original_documents_or_credentials():
    assert {p.name for p in DATASET.iterdir()} == set(FILES)
    text = "\n".join((DATASET / name).read_text(encoding="utf-8") for name in FILES)
    assert '"password"' not in text and '"email"' not in text
    assert 'C:\\' not in text and '/Users/' not in text and '/home/' not in text
