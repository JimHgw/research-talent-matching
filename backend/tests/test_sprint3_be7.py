"""BE-7 acceptance: independent fixtures, real application HTTP and fail-closed gate."""

import json
import math
import os
import subprocess
import sys

import pytest

from backend.src.db.skills import skill_claims
from backend.src.features.matching.semantic import cosine
from backend.src.features.matching import semantic_runtime
from backend.src.features.matching.semantic_runtime import model_config
from backend.src.shared.paths import ROOT
from conftest import headers
from test_requirement_scoring import Vectors, evaluate, requirement, snapshot
from test_semantic_matching import Encoder, profile
from test_us04 import MATCHES, RECOMMENDATIONS, checked, confirm_profile, research_team
from test_us05 import share
from test_us14 import opportunity

FIXTURES = ROOT / "backend/tests/data/sprint3/be7-scoring.json"
CASES = json.loads(FIXTURES.read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
def test_fixed_scoring_examples(app, case):
    vectors = Vectors({text: [value, math.sqrt(1 - value ** 2)]
                       for text, value in case["cosines"].items()})
    rows, summary = evaluate(app, case["requirements"], snapshot(**case["fields"]), vectors)
    expected = case["expected"]
    for field, key in (("score", "scores"), ("weight", "weights"), ("contribution", "contributions")):
        assert [row["scoring"][field] for row in rows] == expected[key]
    assert [row["status"] for row in rows] == expected["statuses"]
    assert summary["recommendationScore"] == expected["recommendationScore"]
    assert summary["semanticRequirements"]["totalWeight"] == expected["totalWeight"]
    assert summary["semanticInterest"]["weight"] == 0
    # Fixed hard criteria must never be sent to the semantic encoder.
    assert not {"Bachelor", "Masters", "PUBLICATION", "PROJECT", "Required University", "Other University"} & set(vectors.calls[0])


@pytest.mark.parametrize("prefix", ["不会", "不懂", "不熟悉", "不具备", "没有", "未曾使用过"])
def test_chinese_skill_title_denials_override_positive_claims(app, prefix):
    skills = [{"id": "skill_yes", "title": "source", "evidenceText": ""},
              {"id": "skill_no", "title": prefix + "source", "evidenceText": ""}]
    for records in (skills, list(reversed(skills))):
        assert skill_claims(records)["source"]["claim"] == "DOES_NOT_HAVE"
        rows, summary = evaluate(app, [requirement("SKILL")], snapshot(skillRecords=records),
                                 Vectors({"source": [1, 0], "target": [1, 0]}))
        assert rows[0]["scoring"]["method"] == "EXPLICIT_GAP"
        assert rows[0]["scoring"]["matches"] == []
        assert summary["recommendationScore"] == 0


def test_http_failure_cooldown_recovers_using_current_profile(app, signed, research_team, monkeypatch):
    app.config["SEMANTIC_MATCHING_ENABLED"] = True
    now, attempts, failures = [0], [], []
    healthy = Encoder()

    class Broken:
        def encode(self, texts):
            failures.append(1)
            raise RuntimeError("private inference failure")

    def load(directory, config):
        attempts.append(directory)
        return Broken() if len(attempts) == 1 else healthy

    monkeypatch.setattr(semantic_runtime, "monotonic", lambda: now[0])
    monkeypatch.setattr(semantic_runtime, "MiniLMEncoder", load)
    saved = profile(signed, text="old interest text")
    share(signed, ["researchInterests"])
    published = opportunity(research_team, requirements=[requirement("INTEREST", tagIds=["interest_ml"])])
    url = f"{MATCHES}/{published['id']}"
    first = checked(signed[0].get(url), "OwnerMatch")["summary"]
    assert first["semanticRequirements"]["status"] == "UNAVAILABLE"
    assert first["recommendationScore"] == first["score"] == 0
    now[0] = 59
    content = saved["content"]
    content["researchInterestText"] = "current interest text"
    saved = confirm_profile(signed, content)
    team_url = f"/api/v1/opportunities/{published['id']}/talent-matches/{saved['talentId']}"
    assert checked(research_team[0].get(team_url), "TeamMatch")["summary"] == first
    assert checked(signed[0].get(RECOMMENDATIONS), "RecommendationPage")["items"][0]["summary"] == first
    assert len(attempts) == len(failures) == 1
    now[0] = 60
    recovered = checked(signed[0].get(url), "OwnerMatch")["summary"]
    assert recovered["semanticRequirements"]["status"] == "AVAILABLE"
    assert recovered["recommendationScore"] == 100
    assert checked(research_team[0].get(team_url), "TeamMatch")["summary"] == recovered
    assert len(attempts) == 2
    assert all("old interest text" not in batch for batch in healthy.calls)
    assert all("current interest text" in batch for batch in healthy.calls)


def test_real_chinese_negation_and_collection_consistency(
        application_model, app, signed, research_team, record_testsuite_property):
    """Use pinned MiniLM, real routes, persistence, confirmation and consent."""
    app.config["SEMANTIC_MATCHING_ENABLED"] = True
    saved = profile(signed, text="")
    content = saved["content"]
    content["skills"] = [{"id": "skill_bio", "title": "生物科技研究", "evidenceText": ""}]
    saved = confirm_profile(signed, content)
    share(signed, ["skills"])
    related = opportunity(research_team, requirements=[requirement("SKILL", "生物技术研究")])
    unrelated = opportunity(research_team, requirements=[requirement("SKILL", "法国文学研究")])
    owner, owner_csrf = signed
    team, csrf = research_team
    path = f"/api/v1/opportunities/{related['id']}"
    shortlist = path + "/shortlist"
    checked(team.put(f"{shortlist}/{saved['talentId']}", headers=headers(csrf)), "CollectionState")
    checked(owner.put(f"/api/v1/me/saved-opportunities/{related['id']}",
                      headers=headers(owner_csrf)), "CollectionState")

    detail = checked(owner.get(f"{MATCHES}/{related['id']}"), "OwnerMatch")
    positive = detail["requirements"][0]["scoring"]["score"]
    assert 75 < positive < 100
    assert detail["requirements"][0]["status"] == "UNKNOWN"
    different = checked(owner.get(f"{MATCHES}/{unrelated['id']}"), "OwnerMatch")
    assert different["requirements"][0]["scoring"]["score"] == 0
    page = checked(owner.get(RECOMMENDATIONS + "?pageSize=1"), "RecommendationPage")
    assert page["total"] == 2
    assert page["items"][0]["opportunity"]["id"] == related["id"]
    assert page["items"][0]["summary"] == detail["summary"]
    for url, schema in ((path + "/talent-matches", "TalentMatchPage"),
                        (shortlist, "TalentMatchPage"),
                        (f"{path}/talent-matches/{saved['talentId']}", "TeamMatch")):
        data = checked(team.get(url), schema)
        summary = data["summary"] if "summary" in data else data["items"][0]["summary"]
        assert summary == detail["summary"]

    runtime = app.extensions["semantic_matching"]
    left, right = runtime.encode(["生物科技研究", "生物技术研究"])
    assert cosine(left, right) > 0.75  # A high raw cosine cannot override a denial.
    negatives = []
    for title, evidence in (("不会生物科技研究", ""),
                            ("生物科技研究", "我不会生物科技研究"),
                            ("不会生物技术研究", "")):
        content["skills"] = [{"id": "skill_bio", "title": title, "evidenceText": evidence}]
        saved = confirm_profile(signed, content)
        denied = checked(owner.get(f"{MATCHES}/{related['id']}"), "OwnerMatch")
        scoring = denied["requirements"][0]["scoring"]
        assert denied["requirements"][0]["status"] != "MATCHED"
        assert scoring["score"] == 0
        assert scoring["method"] == "EXPLICIT_GAP"
        assert scoring["matches"] == [] and scoring["similarity"] is None
        for url in (path + "/talent-matches", shortlist):
            assert checked(team.get(url), "TalentMatchPage")["items"][0]["summary"] == denied["summary"]
        negatives.append({"title": title, "evidence": evidence, "score": scoring["score"]})

    config = model_config()
    for key in ("model", "modelVersion", "revision", "preprocessingVersion", "thresholdVersion", "thresholds", "artifacts"):
        record_testsuite_property("BE7." + key, json.dumps(config[key], ensure_ascii=False))
    record_testsuite_property("BE7.scoringVersion", detail["summary"]["rankingAlgorithmVersion"])
    record_testsuite_property("BE7.realHttpScores", json.dumps({
        "chineseSynonym": positive, "unrelated": 0, "negations": negatives,
    }, ensure_ascii=False))


@pytest.mark.parametrize("resource", ["missing", "corrupt"])
def test_required_real_model_gate_fails_instead_of_skipping(tmp_path, resource):
    directory = tmp_path / "model"
    if resource == "corrupt":
        directory.mkdir()
        (directory / "tokenizer.json").write_bytes(b"invalid tokenizer")
    env = {**os.environ, "SEMANTIC_MODEL_DIR": str(directory)}
    result = subprocess.run([
        sys.executable, "-m", "pytest", "backend/tests/test_requirement_scoring.py::"
        "test_real_chinese_synonyms_and_distinct_meanings_through_http",
        "--require-application-model", "-q", "--basetemp", str(tmp_path / "pytest"),
    ], cwd=ROOT, env=env, capture_output=True, text=True, timeout=60)
    output = result.stdout + result.stderr
    assert result.returncode == 1, output
    assert "Real application model unavailable" in output
    assert "skipped" not in output
