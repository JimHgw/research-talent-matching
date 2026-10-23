"""US-13 experiment integrity, privacy, real model execution and failure reporting."""

import hashlib
import importlib.util
import json

import pytest

from backend.src.features.matching import evaluate_semantic
from backend.src.features.matching.evaluate_semantic import (ROOT, compare, main,
                                                            make_rows, metrics,
                                                            text_sha256)
from backend.src.features.matching.semantic import (MiniLMEncoder, cosine,
                                                   interest_input, relevance)
from test_us04 import confirmed, research_team, make_opportunity, checked

DIRECTORY = ROOT / "docs/testing/us13"


def read(name):
    return json.loads((DIRECTORY / name).read_text(encoding="utf-8"))


def test_corpus_has_disjoint_complete_labelled_pools_and_all_input_modes():
    data = read("dataset.json")
    rows = make_rows(data)
    assert len(rows) == len(data["pairs"]) == 84
    assert len([r for r in rows if r["split"] == "final"]) == 66
    assert {"text-only", "shared-only", "personal-only", "combined", "missing", "hidden"} <= {
        r["inputMode"] for r in rows}
    for key in ("talentId", "opportunityId"):
        assert not ({r[key] for r in rows if r["split"] == "tuning"}
                    & {r[key] for r in rows if r["split"] == "final"})
    # Equal tags are not a candidate gate: retain text and alias examples.
    assert any(r["talentId"] == "eval_language" and r["label"] == "RELEVANT" for r in rows)
    assert {r["label"] for r in rows} == {"RELEVANT", "PARTIAL", "UNRELATED", "UNKNOWN"}


def test_interest_projection_deduplicates_and_never_reads_resume_or_skills():
    fields = {"researchInterestText": "  Graph   learning ", "researchInterests": ["graph"],
              "customInterestTags": [{"id": "personal", "label": "ＧＲＡＰＨ learning"}],
              "resumeDescription": "PRIVATE_RESUME", "skills": [{"title": "PRIVATE_SKILL"}]}
    result = interest_input(fields, {"graph": "Graph learning"})
    assert result == {"text": "Graph learning", "sources": [{"field": "researchInterestText", "recordId": None}]}
    fields["researchInterestText"] = ""
    result = interest_input(fields, {"graph": "Graph learning"})
    assert result["text"] == "Graph learning"
    assert len(result["sources"]) == 1
    fields["researchInterestText"] = "Graph learning."
    assert interest_input(fields, {"graph": "Graph learning"})["text"] == "Graph learning."


def test_permission_checks_happen_before_baseline_or_model_input_construction():
    rows = make_rows(read("dataset.json"))
    assert all(not r["profileInput"]["text"] for r in rows if r["talentId"] == "eval_hidden")
    assert all(not r["baselineProfile"]["researchInterests"] for r in rows if r["talentId"] == "eval_hidden")
    assert "PRIVATE_" not in json.dumps(rows)
    assert not any(r["talentId"].startswith("excluded_") for r in rows)


def test_semantic_unavailable_is_incomplete_with_actual_baseline_and_explicit_fallback():
    report = compare(read("dataset.json"), read("config.json"), None, "missing model")
    assert report["status"] == "INCOMPLETE"
    assert report["metrics"]["final"]["semantic"] is None
    assert report["thresholds"] is None
    assert report["errors"]
    assert all(r["baseline"] == r["fallback"] for r in report["pairs"])
    assert all(r["semantic"]["similarity"] is None for r in report["pairs"])
    assert report["decision"]["applicationDecision"] == "OMIT"
    assert "PRIVATE_" not in json.dumps(report)


def test_cli_missing_model_returns_failure_and_saves_incomplete_evidence(tmp_path):
    output = tmp_path / "incomplete.json"
    assert main(["--model-dir", str(tmp_path / "absent"), "--output", str(output)]) == 1
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["status"] == "INCOMPLETE"
    assert report["metrics"]["final"]["baseline"]["pairs"] == 66
    assert report["costs"]["encodedTexts"] == 0


@pytest.mark.parametrize("newline", [b"\n", b"\r\n"], ids=["LF", "CRLF"])
def test_cli_text_fingerprints_are_portable(tmp_path, monkeypatch, newline):
    inputs = {name: DIRECTORY / name for name in ("dataset.json", "config.json")}
    inputs.update({name: ROOT / "backend/src/features/matching" / name
                   for name in ("engine.py", "semantic.py", "evaluate_semantic.py")})
    contents = {name: path.read_text(encoding="utf-8").encode("utf-8")
                for name, path in inputs.items()}
    for name, content in contents.items():
        (tmp_path / name).write_bytes(content.replace(b"\n", newline))
    monkeypatch.setattr(evaluate_semantic, "__file__", str(tmp_path / "evaluate_semantic.py"))
    output = tmp_path / "report.json"
    assert main(["--dataset", str(tmp_path / "dataset.json"),
                 "--config", str(tmp_path / "config.json"),
                 "--model-dir", str(tmp_path / "absent"), "--output", str(output)]) == 1
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["textChecksumNormalization"] == "CRLF to LF"
    for key, name in (("datasetSha256", "dataset.json"), ("configSha256", "config.json")):
        assert report[key] == hashlib.sha256(contents[name]).hexdigest()
    assert report["implementationSha256"] == {
        name: hashlib.sha256(contents[name]).hexdigest()
        for name in ("engine.py", "semantic.py", "evaluate_semantic.py")}


def test_checksum_failure_is_detected_before_loading_graph(tmp_path):
    (tmp_path / "bad.onnx").write_bytes(b"corrupt")
    with pytest.raises(RuntimeError, match="checksum mismatch"):
        MiniLMEncoder(tmp_path, {"artifacts": {"bad.onnx": "0" * 64}})


def test_cosine_and_missing_evidence_boundaries():
    assert cosine([1, 0], [1, 0]) == 1
    assert cosine([1, 0], [0, 1]) == 0
    for left, right in (([0, 0], [1, 0]), ([1], [1, 2]), ([float("nan")], [1])):
        with pytest.raises(ValueError):
            cosine(left, right)
    thresholds = {"partial": 0.4, "relevant": 0.7}
    assert [relevance(v, thresholds) for v in (None, 0.1, 0.4, 0.7)] == [
        "UNKNOWN", "UNRELATED", "PARTIAL", "RELEVANT"]


def test_saved_evidence_matches_inputs_and_metrics():
    report = read("results.json")
    assert report["status"] == "COMPLETE"
    assert report["errors"] == []
    assert report["textChecksumNormalization"] == "CRLF to LF"
    for key, name in (("datasetSha256", "dataset.json"), ("configSha256", "config.json")):
        assert report[key] == text_sha256(DIRECTORY / name)
    for name, checksum in report["implementationSha256"].items():
        assert checksum == text_sha256(ROOT / "backend/src/features/matching" / name)
    for split in ("tuning", "final"):
        rows = [r for r in report["pairs"] if r["split"] == split]
        for method in ("baseline", "semantic"):
            assert metrics(rows, method, 3) == report["metrics"][split][method]
    assert report["decision"]["applicationDecision"] == "OMIT"
    assert "PRIVATE_" not in json.dumps(report)


def test_application_baseline_works_without_optional_semantic_packages(confirmed, research_team, monkeypatch):
    import sys
    for name in ("onnxruntime", "numpy", "tokenizers"):
        monkeypatch.setitem(sys.modules, name, None)
    (client, _), _ = confirmed
    opportunity = make_opportunity(research_team)
    detail = checked(client.get(f"/api/v1/me/opportunity-matches/{opportunity['id']}"), "OwnerMatch")
    assert detail["summary"]["algorithmVersion"] == "tag-coverage-v1"
    assert detail["summary"]["score"] == 50


@pytest.mark.skipif(not (ROOT / "data/us13/model/onnx/model.onnx").is_file()
                    or importlib.util.find_spec("onnxruntime") is None,
                    reason="Optional real MiniLM check: install requirements-semantic and download the pinned model.")
def test_real_model_reproduces_saved_semantic_outputs():
    config = read("config.json")
    encoder = MiniLMEncoder(ROOT / "data/us13/model", config)
    report = compare(read("dataset.json"), config, encoder)
    assert report["status"] == "COMPLETE"
    assert report["thresholds"] == read("results.json")["thresholds"]
    assert report["costs"]["encodedTexts"] == 23
    for actual, saved in zip(report["pairs"], read("results.json")["pairs"]):
        assert actual["baseline"] == saved["baseline"]
        assert actual["semantic"]["label"] == saved["semantic"]["label"]
        assert actual["semantic"]["similarity"] == pytest.approx(saved["semantic"]["similarity"], abs=1e-5)
