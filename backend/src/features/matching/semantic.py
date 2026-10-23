"""Offline US-13 interest experiment. No model or network work on API imports.

Callers supply *already permitted* fields (e.g. team_repository.visible_profiles).
Similarity is an interest relevance signal, never evidence of a qualification.
"""

import hashlib
import math
from pathlib import Path
import re
import unicodedata


VERSION = "minilm-interest-onnx-v1"


def normalise(text):
    return " ".join(unicodedata.normalize("NFKC", text).split())


def interest_input(fields, labels):
    """One text per profile, with stable field/record references and deduplication.

    Text is primary; distinct shared/personal labels supply additional context.
    Repeated labels or labels already present in the text add no extra weight.
    No resume, skills, education, provenance or other profile fields are read.
    """
    text = normalise(fields.get("researchInterestText", ""))
    pieces = [text] if text else []
    sources = ([{"field": "researchInterestText", "recordId": None}]
               if text else [])
    seen = set()
    proposals = [(key, labels[key], "researchInterests")
                 for key in fields.get("researchInterests", [])]
    proposals += [(tag["id"], tag["label"], "customInterestTags")
                  for tag in fields.get("customInterestTags", [])]
    for record_id, label, field in proposals:
        label = normalise(label)
        key = label.casefold()
        if not key or key in seen:
            continue
        seen.add(key)
        # Word boundaries avoid treating "AI" as already present in "rain".
        if re.search(r"(?<!\w)" + re.escape(key) + r"(?!\w)", text.casefold()):
            continue
        pieces.append(label)
        sources.append({"field": field, "recordId": record_id})
    return {"text": "\n".join(pieces), "sources": sources}


def opportunity_input(opportunity):
    """Only the published opportunity's research area and INTEREST requirements."""
    content = opportunity["content"]
    pieces, sources, seen = [], [], set()
    entries = [(content.get("researchArea", ""), "researchArea", None)]
    entries += [(req["label"], "requirements", req["id"])
                for req in content["requirements"] if req["kind"] == "INTEREST"]
    for text, field, record_id in entries:
        text = normalise(text)
        if (text and text.casefold() not in seen
                and not any(re.search(r"(?<!\w)" + re.escape(text.casefold()) + r"(?!\w)", piece.casefold())
                            for piece in pieces)):
            seen.add(text.casefold())
            pieces.append(text)
            sources.append({"field": field, "recordId": record_id})
    return {"text": "\n".join(pieces), "sources": sources}


def cosine(left, right):
    if len(left) != len(right) or not left:
        raise ValueError("Embedding dimensions must be equal and nonempty.")
    if not all(math.isfinite(float(v)) for v in (*left, *right)):
        raise ValueError("Embedding values must be finite.")
    denominator = math.sqrt(sum(float(v) ** 2 for v in left)
                            * sum(float(v) ** 2 for v in right))
    if not denominator:
        raise ValueError("A zero embedding has no cosine similarity.")
    return max(-1.0, min(1.0, sum(float(a) * float(b)
                                for a, b in zip(left, right)) / denominator))


def relevance(similarity, thresholds):
    if similarity is None:
        return "UNKNOWN"
    if similarity >= thresholds["relevant"]:
        return "RELEVANT"
    if similarity >= thresholds["partial"]:
        return "PARTIAL"
    return "UNRELATED"


class MiniLMEncoder:
    """Pinned public ONNX export, masked mean pooling and L2 normalisation."""

    def __init__(self, model_dir, config):
        # Check identity before executing the ONNX graph. No automatic downloads.
        self.artifact_bytes = 0
        for name, expected in config["artifacts"].items():
            path = Path(model_dir) / name
            if not path.is_file():
                raise RuntimeError(f"Missing model artifact: {name}. Run --download-model.")
            data = path.read_bytes()
            if hashlib.sha256(data).hexdigest() != expected:
                raise RuntimeError(f"Model artifact checksum mismatch: {name}.")
            self.artifact_bytes += len(data)
        try:
            import numpy as np
            import onnxruntime as ort
            from tokenizers import Tokenizer
        except ImportError as error:
            raise RuntimeError("Install backend/requirements-semantic.txt to run US-13.") from error
        self.np = np
        options = ort.SessionOptions()
        options.intra_op_num_threads = config["threads"]
        options.inter_op_num_threads = 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        self.session = ort.InferenceSession(
            str(Path(model_dir) / "onnx/model.onnx"), sess_options=options,
            providers=["CPUExecutionProvider"],
        )
        self.tokenizer = Tokenizer.from_file(str(Path(model_dir) / "tokenizer.json"))
        self.tokenizer.enable_truncation(max_length=config["maxTokens"])
        self.tokenizer.enable_padding(pad_id=0, pad_token="[PAD]")
        self.truncated_texts = 0
        self.encoded_texts = 0

    def encode(self, texts):
        if not texts or any(not text.strip() for text in texts):
            raise ValueError("Encode a nonempty batch of nonempty interest texts.")
        encoded = self.tokenizer.encode_batch(texts)
        self.truncated_texts += sum(bool(item.overflowing) for item in encoded)
        self.encoded_texts += len(encoded)
        arrays = {
            "input_ids": [item.ids for item in encoded],
            "attention_mask": [item.attention_mask for item in encoded],
            "token_type_ids": [item.type_ids for item in encoded],
        }
        inputs = {item.name: self.np.asarray(arrays[item.name], dtype="int64")
                  for item in self.session.get_inputs()}
        tokens = self.session.run(None, inputs)[0]
        mask = inputs["attention_mask"][:, :, None]
        pooled = (tokens * mask).sum(axis=1) / mask.sum(axis=1).clip(min=1)
        norms = self.np.linalg.norm(pooled, axis=1, keepdims=True)
        vectors = pooled / norms.clip(min=1e-12)
        if vectors.shape != (len(texts), 384) or not self.np.isfinite(vectors).all():
            raise RuntimeError("Unexpected or non-finite MiniLM output.")
        return vectors.tolist()
