"""Computes the AUTHORITATIVE metric on the held-out split.

Never edited by the optimization loop, never invoked by train.py, and
never given to the model that proposes edits -- only the autoresearch
plugin's own driver code calls this, as a separate subprocess, after
train.py has already finished and exited. train.py has no code path that
could reach this file or the held-out data it reads.

Usage: python harness/evaluate.py
Prints one line of JSON to stdout: {"accuracy": <float>, "n_heldout": <int>}
"""
import json
import os
import sys

import joblib
import numpy as np
from sklearn.metrics import accuracy_score

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from harness.data import load_heldout  # noqa: E402

ARTIFACT_PATH = os.path.join(os.path.dirname(__file__), "..", "artifacts", "model.joblib")


def main():
    X_held, y_held = load_heldout()
    model = joblib.load(ARTIFACT_PATH)
    y_pred = model.predict(X_held)
    accuracy = accuracy_score(y_held, y_pred)

    # A quick, honest sanity check that print()'s to stderr (never parsed
    # by the loop) rather than silently trusting a suspicious number: with
    # flip_y=0.03 baked into the dataset (harness/data.py), the Bayes-
    # optimal ceiling on this held-out set is well under 100%. The plugin's
    # guard treats an accuracy this high as a memorization/leakage signal,
    # not a result to celebrate -- see plugins/autoresearch/src/guard.js.
    if accuracy > 0.99:
        print(
            f"[evaluate.py] WARNING: accuracy {accuracy:.4f} is suspiciously "
            "close to 1.0 given 3% label noise in the dataset.",
            file=sys.stderr,
        )

    print(json.dumps({"accuracy": float(accuracy), "n_heldout": int(len(y_held))}))


if __name__ == "__main__":
    main()
