"""Application semantic ranking, real inference, privacy and structured fallback."""

import importlib.util
import math
from copy import deepcopy

import pytest

from backend.src.features.matching import semantic_runtime
from backend.src.features.matching.engine import summarize
from backend.src.shared.paths import ROOT
from conftest import headers, sign_in
from test_us04 import (MATCHES, RECOMMENDATIONS, checked, confirm_profile,
                       example, research_team)
from test_us05 import share
from test_us14 import opportunity

GRAPH = "Graph neural networks for molecular discovery"
HISTORY = "Medieval archival history"


class Encoder:
    def __init__(self):
        self.calls = []

    def encode(self, texts):
        self.calls.append(list(texts))
        # A deterministic encoder isolates application plumbing; real MiniLM is
        # exercised separately through the very same HTTP endpoints below.
        return [[0, 1] + [0] * 382 if HISTORY in text else [1, 0] + [0] * 382 for text in texts]


@pytest.fixture
def semantic_app(app):
    app.config["SEMANTIC_MATCHING_ENABLED"] = True
    encoder = Encoder()
    app.extensions["semantic_matching"]._encoder = encoder
    return app, encoder


def profile(signed, *, text=GRAPH, personal=None):
    content = example("profile-write.json")["content"]
    content.update(researchInterests=[], researchInterestText=text,
                   customInterestTags=personal or [], resumeDescription="PRIVATE_RESUME_SENTINEL")
    return confirm_profile(signed, content)


def interest_requirement():
    return {"id": "req_interest", "label": GRAPH, "kind": "INTEREST",
            "importance": "REQUIRED", "tagIds": ["interest_ml"]}


def test_owner_recommendations_and_details_use_text_without_shared_tag_gate(semantic_app, signed, research_team):
    _, encoder = semantic_app
    saved = profile(signed)
    # Equal structured scores must be reordered by semantic relevance before pagination.
    unrelated = opportunity(research_team, title="History", researchArea=HISTORY)
    related = opportunity(research_team, title="Graph research", researchArea=GRAPH)
    client, _ = signed
    page = checked(client.get(RECOMMENDATIONS + "?pageSize=1"), "RecommendationPage")
    item = page["items"][0]
    assert page["total"] == 2
    assert item["opportunity"]["id"] == related["id"]
    assert item["summary"]["score"] == 50
    assert item["summary"]["recommendationScore"] == 65
    assert item["summary"]["semanticInterest"]["relevance"] == "RELEVANT"
    assert len(encoder.calls) == 1
    assert len(encoder.calls[0]) == len(set(encoder.calls[0])) == 2
    detail = checked(client.get(f"{MATCHES}/{related['id']}"), "OwnerMatch")
    assert detail["summary"] == item["summary"]
    assert detail["profileRevision"] == saved["revision"]
    assert [row["status"] for row in detail["requirements"]] == ["MATCHED", "PARTIAL", "GAP", "UNKNOWN"]
    second = checked(client.get(RECOMMENDATIONS + "?page=2&pageSize=1"), "RecommendationPage")
    assert second["items"][0]["opportunity"]["id"] == unrelated["id"]
    assert second["items"][0]["summary"]["recommendationScore"] == 35
    assert "PRIVATE_RESUME_SENTINEL" not in str(encoder.calls)


@pytest.mark.parametrize("mode", ["personal-only", "text-only", "shared-only"])
def test_all_interest_inputs_participate_without_creating_skill_or_interest_evidence(semantic_app, signed, research_team, mode):
    _, encoder = semantic_app
    saved = profile(signed, text=GRAPH if mode == "text-only" else "",
                    personal=[{"label": GRAPH}] if mode == "personal-only" else None)
    if mode == "shared-only":
        content = deepcopy(saved["content"])
        content["researchInterests"] = ["interest_ml"]
        confirm_profile(signed, content)
    published = opportunity(research_team, researchArea=GRAPH, requirements=[interest_requirement()])
    detail = checked(signed[0].get(f"{MATCHES}/{published['id']}"), "OwnerMatch")
    summary = detail["summary"]
    assert summary["semanticInterest"]["status"] == "AVAILABLE"
    assert summary["semanticInterest"]["score"] == 100
    row = detail["requirements"][0]
    assert row["status"] == ("MATCHED" if mode == "shared-only" else "UNKNOWN")
    if mode != "shared-only":
        assert row["evidence"] == []
        assert summary["score"] == 0
        assert summary["recommendationScore"] == 30
    assert "PRIVATE_RESUME_SENTINEL" not in str(encoder.calls)


def test_team_lists_details_and_shortlists_use_current_visible_interest_fields(semantic_app, signed, research_team, app):
    _, encoder = semantic_app
    saved = profile(signed)
    share(signed, ["displayName", "researchInterests"])
    published = opportunity(research_team, researchArea=GRAPH, requirements=[interest_requirement()])
    team, token = research_team
    url = f"/api/v1/opportunities/{published['id']}/talent-matches"
    shortlist = f"/api/v1/opportunities/{published['id']}/shortlist"
    checked(team.put(f"{shortlist}/{saved['talentId']}", headers=headers(token)), "CollectionState")
    page = checked(team.get(url), "TalentMatchPage")
    summary = page["items"][0]["summary"]
    assert summary["recommendationScore"] == 30
    detail = checked(team.get(f"{url}/{saved['talentId']}"), "TeamMatch")
    assert detail["summary"] == summary
    assert checked(team.get(shortlist), "TalentMatchPage")["items"][0]["summary"] == summary
    assert "PRIVATE_RESUME_SENTINEL" not in str(encoder.calls) + str(detail)
    assert "confirmedRevision" not in str(detail)

    # A previous successful inference cannot survive withdrawing interest sharing.
    calls_before = len(encoder.calls)
    share(signed, ["displayName"])
    for path, schema in ((url, "TalentMatchPage"), (shortlist, "TalentMatchPage"),
                         (f"{url}/{saved['talentId']}", "TeamMatch")):
        data = checked(team.get(path), schema)
        current = data["summary"] if "summary" in data else data["items"][0]["summary"]
        assert current["semanticInterest"]["status"] == "MISSING_EVIDENCE"
        assert current["semanticInterest"]["score"] is None
        assert current["recommendationScore"] == current["score"] == 0
        assert GRAPH not in str(data.get("talent", data.get("items")))
    assert len(encoder.calls) == calls_before
    # Owner continues to use the confirmed private interest text.
    assert checked(signed[0].get(f"{MATCHES}/{published['id']}"), "OwnerMatch")["summary"]["semanticInterest"]["status"] == "AVAILABLE"
    share(signed, ["researchInterests"], discoverable=False)
    assert checked(team.get(url), "TalentMatchPage")["total"] == 0
    assert checked(team.get(shortlist), "TalentMatchPage")["total"] == 0
    assert team.get(f"{url}/{saved['talentId']}").status_code == 404


def test_team_semantic_ranking_happens_before_pagination_and_batches_text(semantic_app, signed, research_team, app):
    _, encoder = semantic_app
    profile(signed, text=HISTORY)
    share(signed, ["displayName", "researchInterests"])
    other = app.test_client()
    other_signed = other, sign_in(other, "other@example.test")
    related_profile = profile(other_signed)
    share(other_signed, ["displayName", "researchInterests"])
    published = opportunity(research_team, researchArea=GRAPH, requirements=[interest_requirement()])
    url = f"/api/v1/opportunities/{published['id']}/talent-matches?pageSize=1"
    data = checked(research_team[0].get(url), "TalentMatchPage")
    assert data["total"] == 2
    assert data["items"][0]["talent"]["talentId"] == related_profile["talentId"]
    assert data["items"][0]["summary"]["recommendationScore"] == 30
    assert len(encoder.calls) == 1
    assert len(encoder.calls[0]) == 2


@pytest.mark.parametrize("failure", ["missing", "exception", "nan", "zero", "short_batch", "dimensions"])
def test_model_failures_keep_http_matching_available_and_scores_consistent(semantic_app, signed, research_team, tmp_path, failure):
    app, encoder = semantic_app
    profile(signed)
    published = opportunity(research_team, researchArea=GRAPH)
    runtime = app.extensions["semantic_matching"]
    if failure == "missing":
        runtime._encoder = None
        runtime.directory = tmp_path / "missing-model"
    else:
        def fail(texts):
            if failure == "exception":
                raise RuntimeError("PRIVATE_EXCEPTION_SENTINEL")
            if failure == "short_batch":
                return []
            if failure == "dimensions":
                return [[1, 0] for _ in texts]
            return [[float("nan") if failure == "nan" else 0] * 384 for _ in texts]
        encoder.encode = fail
    data = checked(signed[0].get(RECOMMENDATIONS), "RecommendationPage")
    detail = checked(signed[0].get(f"{MATCHES}/{published['id']}"), "OwnerMatch")
    assert data["items"][0]["summary"] == detail["summary"]
    summary = detail["summary"]
    assert summary["score"] == summary["recommendationScore"] == 50
    assert summary["semanticInterest"]["status"] == "UNAVAILABLE"
    assert summary["semanticInterest"]["weight"] == 0
    assert summary["semanticInterest"]["similarity"] is None
    assert "PRIVATE_EXCEPTION_SENTINEL" not in str(detail)


def test_empty_interest_is_unknown_and_does_not_load_model(semantic_app, signed, research_team):
    _, encoder = semantic_app
    profile(signed, text="")
    published = opportunity(research_team, researchArea=GRAPH)
    summary = checked(signed[0].get(f"{MATCHES}/{published['id']}"), "OwnerMatch")["summary"]
    assert summary["semanticInterest"]["status"] == "MISSING_EVIDENCE"
    assert summary["semanticInterest"]["relevance"] == "UNKNOWN"
    assert summary["recommendationScore"] == summary["score"]
    assert encoder.calls == []


@pytest.mark.parametrize("weight,coverage,expected", [
    (0, 50, 50), (0.25, 50, 62.5), (1, 50, 100), (0.3, None, 100), (0, None, None),
])
def test_configurable_blend_and_missing_structured_criteria(semantic_app, weight, coverage, expected):
    app, _ = semantic_app
    app.config["SEMANTIC_MATCHING_WEIGHT"] = weight
    summary = {**summarize([]), "score": coverage}
    published = {"content": {"researchArea": GRAPH, "requirements": []}}
    snapshot = {"researchInterests": {}, "researchInterestText": GRAPH}
    with app.app_context():
        semantic_runtime.enrich_matches([(published, snapshot, summary)])
    assert summary["score"] == coverage
    assert summary["recommendationScore"] == expected
    assert summary["semanticInterest"]["weight"] == (1 if coverage is None and weight else weight)


@pytest.mark.parametrize("setting,value", [
    ("SEMANTIC_MATCHING_WEIGHT", -0.1), ("SEMANTIC_MATCHING_WEIGHT", 1.1),
    ("SEMANTIC_MATCHING_WEIGHT", "nan"), ("SEMANTIC_MATCHING_WEIGHT", "inf"),
    ("SEMANTIC_MATCHING_WEIGHT", "bad"), ("SEMANTIC_MATCHING_ENABLED", "maybe"),
])
def test_invalid_semantic_configuration_fails_at_startup(app, setting, value):
    app.config[setting] = value
    with pytest.raises(ValueError, match=setting):
        semantic_runtime.configure_semantic(app)


def test_failed_encoder_retries_after_cooldown_and_batches_inference(monkeypatch, tmp_path):
    now, attempts = [0], []
    encoder = Encoder()

    def load(directory, config):
        attempts.append(directory)
        if len(attempts) == 1:
            raise RuntimeError("Missing model")
        return encoder

    monkeypatch.setattr(semantic_runtime, "monotonic", lambda: now[0])
    monkeypatch.setattr(semantic_runtime, "MiniLMEncoder", load)
    runtime = semantic_runtime.SemanticRuntime(tmp_path)
    with pytest.raises(RuntimeError, match="Missing model"):
        runtime.encode([GRAPH])
    now[0] = 59
    with pytest.raises(RuntimeError, match="temporarily unavailable"):
        runtime.encode([GRAPH])
    assert len(attempts) == 1
    now[0] = 60
    assert len(runtime.encode([str(i) for i in range(33)])) == 33
    assert [len(batch) for batch in encoder.calls] == [16, 16, 1]
    runtime.encode([GRAPH])
    assert len(attempts) == 2  # Healthy model object is reused, input is encoded afresh.


def test_profile_edit_requires_confirmation_and_new_text_replaces_old_semantics(semantic_app, signed, research_team):
    _, encoder = semantic_app
    saved = profile(signed)
    share(signed, ["researchInterests"])
    published = opportunity(research_team, researchArea=GRAPH)
    client, token = signed
    path = f"{MATCHES}/{published['id']}"
    assert checked(client.get(path), "OwnerMatch")["summary"]["semanticInterest"]["score"] == 100
    content = deepcopy(saved["content"])
    content["researchInterestText"] = HISTORY
    updated = checked(client.put("/api/v1/me/profile", json={"expectedRevision": saved["revision"], "content": content}, headers=headers(token)), "Profile")
    assert client.get(path).status_code == 409
    team_path = f"/api/v1/opportunities/{published['id']}/talent-matches"
    assert checked(research_team[0].get(team_path), "TalentMatchPage")["total"] == 0
    checked(client.post("/api/v1/me/profile/confirmation", json={"expectedRevision": updated["revision"]}, headers=headers(token)), "Profile")
    assert checked(client.get(path), "OwnerMatch")["summary"]["semanticInterest"]["score"] == 0
    assert HISTORY in encoder.calls[-1]
    assert GRAPH in encoder.calls[-1]  # Opportunity text, not a cached profile.


@pytest.mark.skipif(not (ROOT / "data/us13/model/onnx/model.onnx").is_file()
                    or importlib.util.find_spec("onnxruntime") is None,
                    reason="Pinned MiniLM artifacts are required for real application inference.")
def test_real_minilm_runs_in_owner_and_team_http_matching(app, signed, research_team):
    # No encoder substitution in this case.
    app.config["SEMANTIC_MATCHING_ENABLED"] = True
    saved = profile(signed, text="Using graph based neural models to discover new molecules.")
    related = opportunity(research_team, researchArea=GRAPH)
    unrelated = opportunity(research_team, researchArea=HISTORY)
    data = checked(signed[0].get(RECOMMENDATIONS), "RecommendationPage")
    assert data["items"][0]["opportunity"]["id"] == related["id"]
    scores = {item["opportunity"]["id"]: item["summary"]["semanticInterest"]["similarity"] for item in data["items"]}
    assert scores[related["id"]] > scores[unrelated["id"]]
    assert all(math.isfinite(value) for value in scores.values())
    share(signed, ["researchInterests", "skills"])
    team_path = f"/api/v1/opportunities/{related['id']}/talent-matches"
    detail = checked(research_team[0].get(f"{team_path}/{saved['talentId']}"), "TeamMatch")
    owner = checked(signed[0].get(f"{MATCHES}/{related['id']}"), "OwnerMatch")
    assert detail["summary"] == owner["summary"]
    assert detail["summary"]["semanticInterest"]["status"] == "AVAILABLE"
    assert [row["status"] for row in owner["requirements"]] == ["MATCHED", "PARTIAL", "GAP", "UNKNOWN"]
