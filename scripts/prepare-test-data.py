"""Prepare or restore a Sprint 2 dataset into a new isolated run directory."""

import argparse
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.tests.data_preparation import DATASET, prepare_run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True, help="New directory; existing paths are refused.")
    parser.add_argument("--dataset-dir", type=Path, default=DATASET)
    args = parser.parse_args()
    run = prepare_run(args.run_dir, dataset_directory=args.dataset_dir,
                      password=os.environ.get("SPRINT2_TEST_PASSWORD"))
    try:
        print(f"Prepared {run.report['datasetVersion']}: "
              f"{len(run.report['talents'])} talents, {len(run.report['opportunities'])} opportunities.")
        print("Starting state recorded in starting-state.json. Authorised real examples remain required.")
    finally:
        run.close()


if __name__ == "__main__":
    main()
