"""Request-scoped semantic ranking over current, audience-permitted interests.

The encoder is reused per application. Text and vectors are never retained across
requests, so a privacy or profile change takes effect on the very next request.
"""

import json
import math
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from threading import Lock
from time import monotonic

from flask import current_app, has_app_context

from ...shared.paths import ROOT
from .semantic import VERSION, MiniLMEncoder, cosine, interest_input, opportunity_input, relevance

CONFIG_PATH = Path(__file__).with_name("semantic_config.json")


def model_config():
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


class SemanticRuntime:
    """Load local, checksum-verified artifacts lazily; never download in a request."""

    def __init__(self, directory):
        self.directory = Path(directory)
        if not self.directory.is_absolute():
            self.directory = ROOT / self.directory
        self.config = model_config()
        self._encoder = None
        self._retry_at = 0
        self._lock = Lock()

    def encode(self, texts):
        # Tokenizer padding/truncation state and inference share one lock.
        with self._lock:
            if monotonic() < self._retry_at:
                raise RuntimeError("Semantic encoder temporarily unavailable.")
            try:
                if self._encoder is None:
                    self._encoder = MiniLMEncoder(self.directory, self.config)
                vectors = []
                for offset in range(0, len(texts), self.config["batchSize"]):
                    batch = texts[offset:offset + self.config["batchSize"]]
                    encoded = self._encoder.encode(batch)
                    if len(encoded) != len(batch):
                        raise ValueError("Unexpected semantic batch size.")
                    for vector in encoded:
                        if len(vector) != 384:
                            raise ValueError("Unexpected semantic vector dimensions.")
                        cosine(vector, vector)  # Reject zero or non-finite vectors.
                    vectors.extend(encoded)
                return vectors
            except Exception:
                self._encoder = None
                self._retry_at = monotonic() + 60
                raise


def configure_semantic(app):
    enabled = app.config["SEMANTIC_MATCHING_ENABLED"]
    if isinstance(enabled, str) and enabled.lower() in ("true", "false"):
        enabled = enabled.lower() == "true"
    if not isinstance(enabled, bool):
        raise ValueError("SEMANTIC_MATCHING_ENABLED must be true or false.")
    try:
        weight = float(app.config["SEMANTIC_MATCHING_WEIGHT"])
    except (ValueError, TypeError):
        raise ValueError("SEMANTIC_MATCHING_WEIGHT must be between 0 and 1.") from None
    if not math.isfinite(weight) or not 0 <= weight <= 1:
        raise ValueError("SEMANTIC_MATCHING_WEIGHT must be between 0 and 1.")
    app.config.update(SEMANTIC_MATCHING_ENABLED=enabled, SEMANTIC_MATCHING_WEIGHT=weight)
    app.extensions["semantic_matching"] = SemanticRuntime(app.config["SEMANTIC_MODEL_DIR"])


def profile_input(snapshot):
    return interest_input({
        "researchInterestText": snapshot.get("researchInterestText", ""),
        "researchInterests": list(snapshot["researchInterests"]),
        "customInterestTags": snapshot.get("customInterestTags", []),
    }, snapshot["researchInterests"])


def rounded(value):
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def enrich_matches(pairs):
    """Enrich (opportunity, permitted snapshot, summary) tuples as one atomic batch.

    Structured coverage/status/evidence remain intact. Only recommendationScore
    combines coverage and semantic interest; missing input/model uses coverage.
    """
    if not pairs or not has_app_context() or not current_app.config["SEMANTIC_MATCHING_ENABLED"]:
        return
    inputs = [(profile_input(profile), opportunity_input(opportunity))
              for opportunity, profile, _ in pairs]
    texts = list(dict.fromkeys(item["text"] for left, right in inputs
                               if left["text"] and right["text"] for item in (left, right)))
    runtime = current_app.extensions["semantic_matching"]
    vectors = {}
    similarities = []
    try:
        if texts:
            vectors = dict(zip(texts, runtime.encode(texts), strict=True))
        similarities = [cosine(vectors[left["text"]], vectors[right["text"]])
                        if left["text"] and right["text"] else None for left, right in inputs]
    except Exception as error:
        # Diagnostics must never contain profile text, identifiers or file paths.
        current_app.logger.warning("Semantic matching unavailable (%s); using evidence coverage.",
                                   type(error).__name__)
        similarities = [None] * len(pairs)
    for (_, _, summary), (left, right), similarity in zip(pairs, inputs, similarities, strict=True):
        status = ("MISSING_EVIDENCE" if not left["text"] or not right["text"]
                  else "UNAVAILABLE" if similarity is None else "AVAILABLE")
        semantic_score = max(0, similarity) * 100 if similarity is not None else None
        coverage = summary["score"]
        weight = current_app.config["SEMANTIC_MATCHING_WEIGHT"]
        if coverage is None and weight > 0:
            weight = 1.0
        if semantic_score is None or weight == 0:
            weight = 0.0
            ranking_score = coverage
        else:
            ranking_score = rounded((1 - weight) * (coverage or 0) + weight * semantic_score)
        summary.update({
            "recommendationScore": ranking_score,
            "rankingAlgorithmVersion": "hybrid-interest-v1",
            "semanticInterest": {
                "status": status,
                "similarity": similarity,
                "score": rounded(semantic_score) if semantic_score is not None else None,
                "relevance": relevance(similarity, runtime.config["thresholds"]),
                "weight": weight,
                "modelVersion": VERSION,
            },
        })
