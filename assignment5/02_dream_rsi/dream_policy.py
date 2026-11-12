"""The exploration policy -- the object Dream-RSI improves.

A policy scores every possible expansion (a node of the discovery tree, and
an edit the base agent could make there) with a linear function of seven
features, and samples one through a softmax. The base agent -- which edits
exist at a node, and how an expansion is scored -- never changes; only the
weights do.

Features of expanding node n with strategy s:
  node_value       validation accuracy of n
  family_failures  for a coverage edit, failing steering questions of its
                   family at n (0..1); for a mechanism, failing fraction overall
  is_mechanism     s changes a global mechanism (dispatch, linking, counting)
  novelty          s has not been expanded anywhere in this tree yet
  depth            depth of n / 10
  is_prepend       s inserts a handler at the front of the dispatch list
  is_undo          s reverses a flag or removes a handler
  mech_context     is_mechanism x (non-base handlers present at n / 15).
                   POST-HOC: added after the designed policy failed on seed 0
                   (see README). Inactive -- weight pinned at 0 and never
                   searched -- in the designed "dream" arm and the fixed arm;
                   searched only in the "dream_context" arm.

Everything a feature needs is recorded in the discovery tree, so the replay
simulator can compute the same features without running anything.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from task import strategies as lib

FEATURES = ("node_value", "family_failures", "is_mechanism", "novelty", "depth",
            "is_prepend", "is_undo", "mech_context")
DESIGNED = np.array([1, 1, 1, 1, 1, 1, 1, 0], dtype=bool)
WITH_CONTEXT = np.ones(len(FEATURES), dtype=bool)
MECHANISMS = {"shadowing", "value_linking", "duplicate_counting"}

# The starting policy: climb from the best node, target the family that
# fails most. Indifferent to everything else -- including whether an edit
# can even be reached under first-match dispatch.
THETA0 = np.array([2.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
TEMPERATURE = 0.5


def strategy(sid: str) -> lib.Strategy:
    if sid.startswith("remove:"):
        return lib.removal(sid.split(":", 1)[1])
    return lib.BY_ID[sid]


def features(node_value: float, fail_by_family: dict[str, int], depth: int,
             s: lib.Strategy, novel: bool, n_handlers: int = 0) -> np.ndarray:
    total_fail = sum(fail_by_family.values())
    if s.kind == "add_handler":
        fam = fail_by_family.get(s.family, 0) / 2.0
    elif s.mechanism in MECHANISMS:
        fam = total_fail / 40.0
    else:
        fam = 0.0
    is_mech = float(s.mechanism in MECHANISMS)
    return np.array([
        node_value, fam, is_mech, float(novel), depth / 10.0,
        float(s.kind == "add_handler" and s.position == "prepend"),
        float(s.mechanism == "undo"), is_mech * n_handlers / 15.0,
    ])


@dataclass
class Policy:
    theta: np.ndarray
    temperature: float = TEMPERATURE
    label: str = "theta0"
    active: np.ndarray = field(default_factory=lambda: DESIGNED.copy())

    def logits(self, feats: np.ndarray) -> np.ndarray:
        return feats @ self.theta / self.temperature

    def choose(self, feats: np.ndarray, rng: np.random.Generator) -> int:
        z = self.logits(feats)
        p = np.exp(z - z.max())
        p /= p.sum()
        return int(rng.choice(len(p), p=p))

    def as_dict(self) -> dict:
        return {"label": self.label, "temperature": self.temperature,
                "theta": {f: round(float(w), 3)
                          for f, w, a in zip(FEATURES, self.theta, self.active) if a}}
