"""Download and verify the pinned local interest encoder before serving requests."""

import argparse
import os
from pathlib import Path

from ...shared.paths import ROOT
from .evaluate_semantic import download_model
from .semantic import MiniLMEncoder
from .semantic_runtime import model_config


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path,
                        default=Path(os.getenv("SEMANTIC_MODEL_DIR", str(ROOT / "data/us13/model"))))
    args = parser.parse_args(argv)
    directory = args.model_dir if args.model_dir.is_absolute() else ROOT / args.model_dir
    config = model_config()
    download_model(directory, config)
    MiniLMEncoder(directory, config).encode(["Research interest matching"])
    print("Semantic interest model downloaded and verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
