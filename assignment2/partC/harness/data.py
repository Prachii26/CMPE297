"""Generates the synthetic dataset and the train / held-out split, once,
deterministically, and persists both halves to disk as separate files.

This file is harness infrastructure, NOT the optimizable target. The
autoresearch loop never lets an edit touch this file or its outputs
(data/heldout.npz) -- see the reward-hacking guard in
plugins/autoresearch/src/guard.js. train.py is only ever handed the path
to data/train.npz; it has no way to construct the held-out split itself,
because it never receives the seed or the split logic, only the already-
split file.
"""
import os

import numpy as np
from sklearn.datasets import make_classification
from sklearn.model_selection import train_test_split

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
TRAIN_PATH = os.path.join(DATA_DIR, "train.npz")
HELDOUT_PATH = os.path.join(DATA_DIR, "heldout.npz")

# Fixed once. This seed controls dataset generation and the train/held-out
# split -- NOT anything a later "edit" can influence, since it lives here,
# in a file train.py never imports and the guard forbids touching.
SEED = 42


def generate_and_split():
    """Build the dataset and split it, once. Idempotent: re-running with
    the same SEED reproduces the identical split, so regenerating never
    accidentally leaks a different held-out set into view."""
    X, y = make_classification(
        n_samples=3000,
        n_features=20,
        n_informative=8,
        n_redundant=5,
        n_repeated=0,
        n_classes=2,
        n_clusters_per_class=2,
        class_sep=0.8,   # moderate difficulty -- not trivially separable
        flip_y=0.03,     # 3% label noise: caps achievable accuracy below 100%,
                         # which is exactly what makes a suspiciously perfect
                         # score on held-out data a leakage signal later.
        random_state=SEED,
    )
    X_train, X_held, y_train, y_held = train_test_split(
        X, y, test_size=0.30, random_state=SEED, stratify=y,
    )
    return X_train, X_held, y_train, y_held


def ensure_split_exists():
    """Write both files if they don't exist yet. Called once, up front,
    never by train.py itself."""
    os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.exists(TRAIN_PATH) and os.path.exists(HELDOUT_PATH):
        return
    X_train, X_held, y_train, y_held = generate_and_split()
    np.savez(TRAIN_PATH, X=X_train, y=y_train)
    np.savez(HELDOUT_PATH, X=X_held, y=y_held)


def load_train():
    """The only function train.py is told about. Returns (X, y) for the
    training split only."""
    ensure_split_exists()
    with np.load(TRAIN_PATH) as f:
        return f["X"], f["y"]


def load_heldout():
    """Used ONLY by harness/evaluate.py, never by train.py. Returns
    (X, y) for the held-out split."""
    ensure_split_exists()
    with np.load(HELDOUT_PATH) as f:
        return f["X"], f["y"]


if __name__ == "__main__":
    ensure_split_exists()
    X_train, y_train = load_train()
    X_held, y_held = load_heldout()
    print(f"train: {X_train.shape}, held-out: {X_held.shape}")
    print(f"train positive rate: {y_train.mean():.3f}, held-out positive rate: {y_held.mean():.3f}")
