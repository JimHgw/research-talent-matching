"""Reproduce US-13 with saved inputs, both real matchers and measured costs.

python -m backend.src.features.matching.evaluate_semantic --help
"""

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import platform
import statistics
import sys
import time
import urllib.request

from .engine import evaluate_opportunity, team_evidence
from .semantic import (VERSION, MiniLMEncoder, cosine, interest_input,
                       opportunity_input, relevance)

ROOT = Path(__file__).resolve().parents[4]
LABELS = ("RELEVANT", "PARTIAL", "UNRELATED", "UNKNOWN")


def eligible(profile):
    return (profile["role"] == "TALENT" and profile["active"]
            and profile["discoverable"] and profile["confirmationStatus"] == "CONFIRMED"
            and profile["revision"] == profile["confirmedRevision"])


def permitted_interests(profile):
    # Apply the same group boundary as team_repository.visible_profiles before
    # tokenisation, vector caching, baseline evaluation or report construction.
    if "researchInterests" not in profile["visibleFields"]:
        return {}
    return {key: profile["content"][key]
            for key in ("researchInterestText", "researchInterests", "customInterestTags")
            if key in profile["content"]}


def make_rows(dataset):
    profiles = {p["id"]: p for p in dataset["profiles"] if eligible(p)}
    opportunities = {o["id"]: o for o in dataset["opportunities"]
                     if o["status"] == "PUBLISHED" and o["availabilityStatus"] == "ACTIVE"}
    pairs = {(p["talentId"], p["opportunityId"]): p["label"] for p in dataset["pairs"]}
    if len(pairs) != len(dataset["pairs"]):
        raise ValueError("Duplicate labelled pair.")
    rows = []
    for profile in profiles.values():
        fields = permitted_interests(profile)
        for opportunity in opportunities.values():
            if profile["split"] != opportunity["split"]:
                continue
            label = pairs.get((profile["id"], opportunity["id"]))
            if label not in LABELS:
                raise ValueError("Every eligible pair needs an independent relevance label.")
            rows.append({
                "talentId": profile["id"], "opportunityId": opportunity["id"],
                "profileRevision": profile["revision"], "opportunityRevision": opportunity["revision"],
                "split": profile["split"], "inputMode": profile["inputMode"], "label": label,
                "profileInput": interest_input(fields, dataset["sharedLabels"]),
                "opportunityInput": opportunity_input(opportunity),
                "baselineProfile": {"skills": {}, "researchInterests": {
                    key: dataset["sharedLabels"][key] for key in fields.get("researchInterests", [])}},
                "opportunity": opportunity,
            })
    return rows


def metrics(rows, method, k=3):
    if not rows:
        raise ValueError("Evaluation split must not be empty.")
    actual = [row["label"] for row in rows]
    predicted = [row[method]["label"] for row in rows]
    per_label = {}
    for label in LABELS:
        tp = sum(a == p == label for a, p in zip(actual, predicted))
        fp = sum(a != label and p == label for a, p in zip(actual, predicted))
        fn = sum(a == label and p != label for a, p in zip(actual, predicted))
        per_label[label] = {"support": actual.count(label), "truePositive": tp,
                            "falsePositive": fp, "falseNegative": fn,
                            "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0}
    positive = {"RELEVANT", "PARTIAL"}
    tp = sum(a in positive and p in positive for a, p in zip(actual, predicted))
    fp = sum(a not in positive and p in positive for a, p in zip(actual, predicted))
    fn = sum(a in positive and p not in positive for a, p in zip(actual, predicted))
    by_opportunity = defaultdict(list)
    for row in rows:
        by_opportunity[row["opportunityId"]].append(row)
    gain = {"RELEVANT": 2, "PARTIAL": 1, "UNRELATED": 0, "UNKNOWN": 0}

    def dcg(items):
        return sum((2 ** gain[row["label"]] - 1) / math.log2(index + 2)
                   for index, row in enumerate(items[:k]))

    ndcgs = []
    for items in by_opportunity.values():
        ranked = sorted(items, key=lambda row: (
            row[method]["score"] is None, -(row[method]["score"] or 0), row["talentId"]))
        ideal = dcg(sorted(items, key=lambda row: -gain[row["label"]]))
        if ideal:
            ndcgs.append(dcg(ranked) / ideal)
    return {
        "pairs": len(rows), "accuracy": sum(a == p for a, p in zip(actual, predicted)) / len(rows),
        "macroF1": statistics.mean(item["f1"] for item in per_label.values()),
        "perLabel": per_label,
        "retrievalPrecision": tp / (tp + fp) if tp + fp else 0.0,
        "retrievalRecall": tp / (tp + fn) if tp + fn else 0.0,
        "retrievalF1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0,
        "ndcgAtK": statistics.mean(ndcgs) if ndcgs else None,
        "unknownCount": predicted.count("UNKNOWN"),
        "incorrectPairs": [{"talentId": r["talentId"], "opportunityId": r["opportunityId"],
                            "expected": r["label"], "actual": r[method]["label"]}
                           for r in rows if r["label"] != r[method]["label"]],
    }


def tune(rows, grid):
    best, best_key = None, None
    for partial in grid:
        for relevant in grid:
            if partial >= relevant:
                continue
            thresholds = {"partial": partial, "relevant": relevant}
            for row in rows:
                row["semantic"]["label"] = relevance(row["semantic"]["score"], thresholds)
            result = metrics(rows, "semantic")
            key = (result["macroF1"], result["accuracy"], relevant, partial)
            if best_key is None or key > best_key:
                best, best_key = thresholds, key
    if best is None:
        raise ValueError("Threshold grid needs at least two distinct values.")
    return best


def adoption_decision(dataset, config, final_metrics, complete):
    gates = config["adoptionGates"]
    reasons = []
    count = len({p["id"] for p in dataset["profiles"] if p["split"] == "final" and eligible(p)})
    if not complete:
        reasons.append("Semantic comparison incomplete; model execution failed.")
    if count < gates["minimumFinalProfiles"]:
        reasons.append(f"Only {count} final profiles; need {gates['minimumFinalProfiles']} for adoption.")
    if dataset["provenance"]["independentHumanReviewers"] < gates["minimumIndependentHumanReviewers"]:
        reasons.append("Synthetic author labels lack independent human review.")
    if complete:
        semantic, baseline = final_metrics["semantic"], final_metrics["baseline"]
        if semantic["retrievalPrecision"] < gates["minimumRetrievalPrecision"]:
            reasons.append("Final semantic retrieval precision is below the adoption gate.")
        if semantic["macroF1"] - baseline["macroF1"] < gates["minimumMacroF1Gain"]:
            reasons.append("Final macro-F1 benefit is below the adoption gate.")
        partial = semantic["perLabel"]["PARTIAL"]
        if partial["support"] and not partial["truePositive"]:
            reasons.append("No partial-relevance examples correctly classified in the final split.")
    return {"applicationDecision": "OMIT" if reasons else "ADOPTION_REVIEW_REQUIRED",
            "reasons": reasons, "applicationAlgorithm": "tag-coverage-v1 (interest baseline retained)",
            "fallback": "Existing application matcher runs without semantic dependencies or artifacts.",
            "automaticIntegration": False}


def compare(dataset, config, encoder, model_error=None):
    started, cpu_started = time.perf_counter(), time.process_time()
    rows = make_rows(dataset)
    baseline_ms = []
    for row in rows:
        tick = time.perf_counter()
        results, summary = evaluate_opportunity(row.pop("opportunity"), row.pop("baselineProfile"), team_evidence)
        row["baseline"] = {"label": {"MATCHED": "RELEVANT", "PARTIAL": "PARTIAL",
                                     "GAP": "UNRELATED", "UNKNOWN": "UNKNOWN"}[results[0]["status"]],
                           "score": summary["score"], "summary": summary,
                           "requirementStatuses": [r["status"] for r in results]}
        baseline_ms.append((time.perf_counter() - tick) * 1000)
    texts = sorted({row[key]["text"] for row in rows for key in ("profileInput", "opportunityInput")
                    if row[key]["text"]})
    vectors, errors = {}, []
    tick = time.perf_counter()
    if encoder is not None:
        try:
            for offset in range(0, len(texts), config["batchSize"]):
                batch = texts[offset:offset + config["batchSize"]]
                encoded = encoder.encode(batch)
                if len(encoded) != len(batch):
                    raise ValueError("Encoder batch size mismatch.")
                vectors.update(zip(batch, encoded))
        except Exception as error:
            model_error = f"{type(error).__name__}: {error}"
    encoding_ms = (time.perf_counter() - tick) * 1000
    for row in rows:
        left, right = row["profileInput"]["text"], row["opportunityInput"]["text"]
        state, similarity = "MISSING_EVIDENCE", None
        if left and right:
            try:
                if model_error or encoder is None:
                    raise RuntimeError(model_error or "Semantic encoder unavailable.")
                similarity = cosine(vectors[left], vectors[right])
                state = "EVALUATED"
            except Exception as error:
                state = "ERROR"
                errors.append({"talentId": row["talentId"], "opportunityId": row["opportunityId"],
                               "error": str(error)})
        row["semantic"] = {"score": similarity, "similarity": similarity, "state": state, "label": "UNKNOWN"}
        # A fallback is separately named; never report a baseline result as semantic inference.
        row["fallback"] = row["baseline"]
    complete = encoder is not None and model_error is None and not errors
    tuning_rows = [r for r in rows if r["split"] == "tuning"]
    final_rows = [r for r in rows if r["split"] == "final"]
    if not tuning_rows or not final_rows:
        raise ValueError("Both disjoint tuning and final splits are required.")
    thresholds = tune(tuning_rows, config["thresholdGrid"]) if complete else None
    if thresholds:
        for row in rows:
            row["semantic"]["label"] = relevance(row["semantic"]["score"], thresholds)
    scores = {split: {"baseline": metrics(group, "baseline", config["rankingK"]),
                      "semantic": metrics(group, "semantic", config["rankingK"]) if complete else None}
              for split, group in (("tuning", tuning_rows), ("final", final_rows))}
    return {
        "status": "COMPLETE" if complete else "INCOMPLETE", "algorithmVersion": VERSION,
        "thresholds": thresholds, "thresholdSelection": "Tuning macro-F1, then accuracy, then higher thresholds; final labels unused.",
        "metrics": scores,
        "byInputMode": {mode: {method: metrics([r for r in final_rows if r["inputMode"] == mode], method, config["rankingK"])
                               for method in ("baseline", "semantic") if method == "baseline" or complete}
                        for mode in sorted({r["inputMode"] for r in final_rows})},
        "costs": {"comparisonWallMs": (time.perf_counter() - started) * 1000,
                  "comparisonCpuMs": (time.process_time() - cpu_started) * 1000,
                  "baselineTotalMs": sum(baseline_ms), "baselineMedianPairMs": statistics.median(baseline_ms),
                  "semanticEncodingMs": encoding_ms, "uniqueTexts": len(texts),
                  "encodedTexts": getattr(encoder, "encoded_texts", 0),
                  "truncatedTexts": getattr(encoder, "truncated_texts", 0),
                  "modelArtifactBytes": getattr(encoder, "artifact_bytes", 0), "paidApiCalls": 0},
        "errors": errors, "modelError": model_error,
        "decision": adoption_decision(dataset, config, scores["final"], complete),
        "eligibility": {"eligibleProfiles": sum(eligible(p) for p in dataset["profiles"]),
                        "excluded": [{"talentId": p["id"], "reason": "NOT_CURRENT_CONFIRMED_OPTED_IN_TALENT"}
                                     for p in dataset["profiles"] if not eligible(p)]},
        "pairs": rows,
    }


def download_model(directory, config):
    directory.mkdir(parents=True, exist_ok=True)
    for name, expected in config["artifacts"].items():
        path = directory / name
        if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == expected:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        partial = path.with_suffix(path.suffix + ".partial")
        url = f"https://huggingface.co/{config['model']}/resolve/{config['revision']}/{name}"
        try:
            with urllib.request.urlopen(url, timeout=60) as response, partial.open("wb") as output:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
            if hashlib.sha256(partial.read_bytes()).hexdigest() != expected:
                raise RuntimeError(f"Downloaded checksum mismatch: {name}.")
            partial.replace(path)
        finally:
            partial.unlink(missing_ok=True)


def peak_rss_mib():
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("faults", wintypes.DWORD)] + [
                (key, ctypes.c_size_t) for key in ("peak", "working", "peakPool", "pool", "peakNon", "non", "page", "peakPage")]
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        process = ctypes.windll.kernel32.GetCurrentProcess
        process.restype = wintypes.HANDLE
        read_memory = ctypes.windll.psapi.GetProcessMemoryInfo
        read_memory.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        read_memory.restype = wintypes.BOOL
        if read_memory(process(), ctypes.byref(counters), counters.cb):
            return counters.peak / 1024 ** 2
        return None
    import resource
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak / (1024 ** 2 if sys.platform == "darwin" else 1024)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=ROOT / "docs/testing/us13/dataset.json")
    parser.add_argument("--config", type=Path, default=ROOT / "docs/testing/us13/config.json")
    parser.add_argument("--model-dir", type=Path, default=ROOT / "data/us13/model")
    parser.add_argument("--output", type=Path, default=ROOT / "data/us13/latest.json")
    parser.add_argument("--download-model", action="store_true", help="Explicitly download checksum-pinned public model files.")
    args = parser.parse_args(argv)
    config = json.loads(args.config.read_text(encoding="utf-8"))
    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    encoder, error = None, None
    tick = time.perf_counter()
    try:
        if args.download_model:
            download_model(args.model_dir, config)
        encoder = MiniLMEncoder(args.model_dir, config)
    except Exception as exception:
        error = f"{type(exception).__name__}: {exception}"
    load_ms = (time.perf_counter() - tick) * 1000
    report = compare(dataset, config, encoder, error)
    report.update({"createdAt": datetime.now(timezone.utc).isoformat(),
                   "datasetVersion": dataset["version"], "configuration": config,
                   "datasetSha256": hashlib.sha256(args.dataset.read_bytes()).hexdigest(),
                   "configSha256": hashlib.sha256(args.config.read_bytes()).hexdigest(),
                   "implementationSha256": {name: hashlib.sha256((Path(__file__).parent / name).read_bytes()).hexdigest()
                                            for name in ("engine.py", "semantic.py", "evaluate_semantic.py")},
                   "environment": {"python": platform.python_version(), "platform": platform.platform(),
                                   "machine": platform.machine(), "processor": platform.processor(),
                                   "packages": {dist.metadata['Name']: dist.version
                                                for dist in importlib.metadata.distributions()}}})
    report["costs"].update({"modelLoadAndOptionalDownloadMs": load_ms, "processPeakRssMiB": peak_rss_mib()})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "output": str(args.output),
                      "thresholds": report["thresholds"], "decision": report["decision"]}, indent=2))
    return 0 if report["status"] == "COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
