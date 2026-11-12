"""What an improver is allowed to see.

  steering    full access: questions, gold SQL, gold rows, per-question results
  validation  aggregate score only -- accuracy, count, latency. No questions.
  heldout     not here at all. load_split("heldout") raises; the only path is
              task/vault.py, which is sealed while any improvement loop runs.

ImproverView is the single object every method hands to its improvement
code. Nothing on the improvement side imports the data files directly, and
the guard rejects any edit that tries.
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from task.boundary import BoundaryViolation, assert_validation_allowed
from task.evaluate import EvalReport, evaluate

DATA_DIR = Path(__file__).parent / "data"
VISIBLE_SPLITS = ("steering", "validation")


@lru_cache(maxsize=None)
def _load(name: str) -> tuple:
    return tuple(json.loads((DATA_DIR / f"{name}.json").read_text(encoding="utf-8")))


def load_split(name: str) -> list[dict]:
    if name not in VISIBLE_SPLITS:
        raise BoundaryViolation(
            f"split '{name}' is not loadable here; the held-out split is only "
            "reachable through task.vault inside final_phase()")
    if name == "validation":
        assert_validation_allowed()
    return copy.deepcopy(list(_load(name)))


@dataclass(frozen=True)
class ValidationSummary:
    accuracy: float
    n: int
    n_correct: int
    median_latency_ms: float
    median_solve_ms: float


class ImproverView:
    """Steering in full, validation as a number, held-out not at all."""

    def __init__(self) -> None:
        self._steering = load_split("steering")
        self.__validation = load_split("validation")   # name-mangled on purpose
        self.validation_calls = 0
        self.steering_calls = 0

    @property
    def steering(self) -> list[dict]:
        return copy.deepcopy(self._steering)

    @property
    def steering_size(self) -> int:
        return len(self._steering)

    @property
    def validation_size(self) -> int:
        return len(self.__validation)

    def evaluate_steering(self, solver) -> EvalReport:
        self.steering_calls += 1
        return evaluate(solver, self._steering, "steering")

    def validation_score(self, solver) -> ValidationSummary:
        assert_validation_allowed()
        self.validation_calls += 1
        rep = evaluate(solver, self.__validation, "validation")
        return ValidationSummary(rep.accuracy, rep.n, rep.n_correct,
                                 rep.median_latency_ms, rep.median_solve_ms)
