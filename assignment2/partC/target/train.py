"""THE OPTIMIZABLE TARGET. This is the one file the autoresearch loop is
allowed to edit.

Contract:
  - Read training data ONLY via harness.data.load_train() -- there is no
    other data path available from here, and no held-out data ever
    reaches this file.
  - Train a model on that data, however this file wants to.
  - Save the trained model as a plain scikit-learn estimator to
    artifacts/model.joblib via joblib.dump -- that is the ONLY channel
    the harness reads back. Nothing this file prints is treated as the
    metric; harness/evaluate.py computes the real number, later, in a
    separate process, against data this file never saw.

Must finish in well under 60 seconds on CPU -- the baseline below trains
in a fraction of a second.
"""
import os
import sys
import time

import joblib
from sklearn.ensemble import ExtraTreesClassifier

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from harness.data import load_train  # noqa: E402

ARTIFACT_PATH = os.path.join(os.path.dirname(__file__), "..", "artifacts", "model.joblib")


def main():
    start = time.time()
    X_train, y_train = load_train()

    # An extra-trees ensemble averages trees with randomized thresholds,
    # reducing variance further than a standard random forest.
    model = ExtraTreesClassifier(n_estimators=300, random_state=0, n_jobs=-1)
    model.fit(X_train, y_train)

    os.makedirs(os.path.dirname(ARTIFACT_PATH), exist_ok=True)
    joblib.dump(model, ARTIFACT_PATH)

    elapsed = time.time() - start
    train_accuracy = model.score(X_train, y_train)
    print(f"[train.py] trained ExtraTreesClassifier(n_estimators=300) on {X_train.shape[0]} rows")
    print(f"[train.py] train-set accuracy (NOT the real metric): {train_accuracy:.4f}")
    print(f"[train.py] elapsed: {elapsed:.3f}s")


if __name__ == "__main__":
    main()