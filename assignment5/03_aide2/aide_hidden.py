"""The hidden evaluation, enforced in code.

The outer loop keeps the control-module rewrite that wins on an evaluation
it cannot see. Four mechanisms make "cannot see" true rather than a promise:

1. **The questions live in a closure.** HiddenBenchmark loads the validation
   split once, at construction, outside any inner agent, and keeps it in a
   local variable captured by a nested function. There is no attribute, no
   getter, and no method that returns questions; the only thing that comes
   out is a scalar per seed.

2. **The inner agent is handed a SteeringOnlyView** (aide_inner.py), which
   has no validation method at all.

3. **The inner agent runs inside task.boundary.inner_agent().** While it
   runs, task.splits.load_split("validation") and
   ImproverView.validation_score raise BoundaryViolation -- so even code that
   imports the split loader directly is refused. Generated control code on
   the call stack is refused too, whatever the phase.

4. **The control module is guarded before it loads**: guard.check_references
   and check_evaluator, plus a control-specific scan that rejects any mention
   of validation, the split loader, or the benchmark.

The outer proposer receives a BenchmarkResult: a hidden mean, per-seed
hidden scores, and inner-agent cost counters. Never a question, never a
per-question outcome.
"""
from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field

from aide_control import ControlSpec, load
from aide_inner import INNER_BUDGET, SteeringOnlyView, run_inner
from core.proposers import ScriptedProposer
from guard import guard
from task.boundary import inner_agent
from task.evaluate import evaluate
from task.solver_state import SolverState, load_state
from task.splits import load_split
from task.strategies import initial_state

CONTROL_PATTERNS = [
    (re.compile(r"validation|load_split|ImproverView|HiddenBenchmark|_questions|splits",
                re.I), "control code names the hidden evaluation or the split loader"),
    (re.compile(r"\bimport\b(?!\s+math\b)"), "control code imports something other than math"),
    (re.compile(r"\bopen\s*\(|__import__|\bexec\s*\(|\beval\s*\(|globals\s*\(|getattr\s*\("),
     "control code reaches outside its sandbox"),
]


def guard_control(source: str) -> guard.Verdict:
    for check in (guard.check_references, guard.check_evaluator):
        v = check(source)
        if not v.ok:
            return v
    return guard._scan(guard.strip_comments(source), CONTROL_PATTERNS, "control_tamper")


@dataclass
class BenchmarkResult:
    hidden: float                       # mean validation accuracy over inner seeds
    per_seed: list[float]
    steering: list[float]
    attempts: float                     # mean inner attempts used
    evals: float                        # mean inner steering scorings
    shortcut_attempts: float            # mean reward-hack attempts per inner run
    guard_rejections: dict
    states: list[SolverState] = field(default_factory=list, repr=False)
    verdict: guard.Verdict = guard.PASS

    def public(self) -> dict:
        """What the outer loop is allowed to know."""
        return {"hidden": round(self.hidden, 4), "per_seed": self.per_seed,
                "steering": self.steering, "attempts": self.attempts, "evals": self.evals,
                "shortcut_attempts": self.shortcut_attempts,
                "guard_rejections": self.guard_rejections, "guard": self.verdict.as_dict()}


class HiddenBenchmark:
    def __init__(self, inner_seeds=(0, 1, 2), budget: int = INNER_BUDGET,
                 start: SolverState | None = None) -> None:
        hidden_questions = load_split("validation")   # loaded once, outside any inner agent
        steering = load_split("steering")
        self.inner_seeds, self.budget = tuple(inner_seeds), budget
        self.start = start or initial_state()
        self.fingerprint = guard.integrity_fingerprint()
        self.calls = 0
        self.hidden_evaluations = 0

        def _score(state: SolverState) -> float:
            return evaluate(load_state(state, "hidden"), hidden_questions, "hidden").accuracy

        self._score = _score
        self._steering = steering

    def run(self, spec: ControlSpec) -> BenchmarkResult:
        """Benchmark one version of the inner agent; return only scalars."""
        self.calls += 1
        source = spec.render()
        verdict = guard_control(source)
        if not verdict.ok:
            return BenchmarkResult(0.0, [], [], 0, 0, 0, {}, verdict=verdict)
        control = load(source, spec.key())
        agent = ScriptedProposer(0)                    # the fixed proposer, same for every variant
        results = []
        with inner_agent():
            for seed in self.inner_seeds:
                results.append(run_inner(control, SteeringOnlyView(self._steering), self.start,
                                         agent, seed, self.fingerprint, self.budget))
        hidden = []
        for r in results:                              # scored only after the inner agent exits
            hidden.append(self._score(r.best_state))
            self.hidden_evaluations += 1
        rejections: dict = {}
        for r in results:
            for k, v in r.stats.guard_rejections.items():
                rejections[k] = rejections.get(k, 0) + v
        n = len(results)
        return BenchmarkResult(
            hidden=statistics.mean(hidden), per_seed=[round(h, 4) for h in hidden],
            steering=[round(r.best_steering, 4) for r in results],
            attempts=sum(r.stats.attempts for r in results) / n,
            evals=sum(r.stats.evals for r in results) / n,
            shortcut_attempts=sum(r.stats.shortcut_attempts for r in results) / n,
            guard_rejections=rejections, states=[r.best_state for r in results])
