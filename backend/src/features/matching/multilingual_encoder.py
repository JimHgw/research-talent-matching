"""Application encoder; the frozen US-13 encoder remains independently reproducible."""

import hashlib
from pathlib import Path

from .semantic import MiniLMEncoder


class MultilingualEncoder(MiniLMEncoder):
    """Use the existing mean-pooling implementation with pinned multilingual assets."""

    def __init__(self, model_dir, config):
        self.artifact_bytes = 0
        for name, expected in config["artifacts"].items():
            data = (Path(model_dir) / name).read_bytes()
            if hashlib.sha256(data).hexdigest() != expected:
                raise RuntimeError("Semantic model artifact checksum mismatch.")
            self.artifact_bytes += len(data)
        import numpy as np
        import onnxruntime as ort
        from tokenizers import Tokenizer

        self.np = np
        options = ort.SessionOptions()
        options.intra_op_num_threads = config["threads"]
        options.inter_op_num_threads = 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        self.session = ort.InferenceSession(
            str(Path(model_dir) / config["modelFile"]), sess_options=options,
            providers=["CPUExecutionProvider"],
        )
        self.tokenizer = Tokenizer.from_file(str(Path(model_dir) / "tokenizer.json"))
        self.tokenizer.enable_truncation(max_length=config["maxTokens"])
        self.tokenizer.enable_padding(pad_id=config["padId"], pad_token=config["padToken"])
        self.truncated_texts = 0
        self.encoded_texts = 0

    def encode(self, texts):
        # Dynamic int8 activation ranges depend on the other texts in a batch.
        # Isolate inference so list/detail scores cannot change with pool size,
        # pagination, or another person's visible text. Runtime still deduplicates
        # the whole request and calls this encoder under its shared lock.
        if not texts:
            raise ValueError("Encode a nonempty batch of nonempty texts.")
        encode_one = super().encode
        return [encode_one([text])[0] for text in texts]
