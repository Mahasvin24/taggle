"""Predict fresh/rotten for a transparent fruit cutout with the saved pilot model."""

import argparse
import json
from pathlib import Path

import joblib
from run_experiment import extract_features

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("images", nargs="+", type=Path)
parser.add_argument(
    "--model",
    type=Path,
    default=Path(__file__).parent / "results/gameplay_gradient_boosting.joblib",
)
args = parser.parse_args()
# Only load the locally produced artifact; joblib/pickle models must be trusted.
bundle = joblib.load(args.model)
for path in args.images:
    features, names = extract_features(path)
    if names != bundle["feature_names"]:
        raise ValueError("Feature schema does not match trained model")
    probability = float(bundle["model"].predict_proba([features])[0, 1])
    print(
        json.dumps(
            {
                "image": str(path),
                "label": "rotten" if probability >= bundle["threshold"] else "fresh",
                "p_rotten_uncalibrated": probability,
                "training_snapshot_sha256": bundle["snapshot_sha256"],
            }
        )
    )
