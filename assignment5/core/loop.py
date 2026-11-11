"""Machinery every method shares: score a state, try a proposal through the
guard, judge it, write the ledger entry, and compute the held-out number.

The keep rule is the same everywhere -- a candidate is kept only if its
validation accuracy is strictly higher -- so differences between methods
come from what they propose, not from how leniently they accept.
"""
from __future__ import annotations

import math
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path

from core.edits import Proposal, apply
from core.ledger import Ledger
from guard import guard
from task import vault
from task.boundary import final_phase
from task.evaluate import EvalReport, run_sql
from task.solver_state import SolverState, load_state
from task.splits import ImproverView, ValidationSummary

SOLVER_DIR = Path(__file__).resolve().parents[1] / "docs" / "solvers"
TIMING_REPS = 3


def timing_ms(solver, questions: list[dict], reps: int = TIMING_REPS) -> float:
    """Median over questions of the fastest of `reps` solve+execute runs."""
    best = [math.inf] * len(questions)
    for _ in range(reps):
        for i, q in enumerate(questions):
            t0 = time.perf_counter()
            try:
                run_sql(solver.solve(q["question"]))
            except Exception:
                pass
            best[i] = min(best[i], time.perf_counter() - t0)
    return statistics.median(best) * 1000


@dataclass
class Snapshot:
    state: SolverState
    steer: EvalReport
    val: ValidationSummary

    @property
    def median_latency_ms(self) -> float:
        # latency over everything this state was scored on
        return (self.steer.median_latency_ms + self.val.median_latency_ms) / 2


@dataclass
class Trial:
    proposal: Proposal
    verdict: guard.Verdict
    candidate: Snapshot | None = None
    stage: str = "static"             # where it stopped: static | load | dynamic | scored
    error: str = ""
    timing: tuple[float, float] = (math.nan, math.nan)   # (candidate_ms, reference_ms)

    @property
    def scored(self) -> bool:
        return self.candidate is not None and self.verdict.ok


@dataclass
class Harness:
    view: ImproverView
    ledger: Ledger
    fingerprint: str = field(default_factory=guard.integrity_fingerprint)
    floor_ratio: float = 1.0           # fastest kept solver / starting solver
    reference_solver: object = None    # the starting solver, timed beside every candidate
    evaluations: int = 0               # full steering+validation scorings ("live calls")

    def snapshot(self, state: SolverState, tag: str = "candidate") -> Snapshot:
        solver = load_state(state, tag)
        self.evaluations += 1
        return Snapshot(state, self.view.evaluate_steering(solver),
                        self.view.validation_score(solver))

    def start(self, state: SolverState) -> Snapshot:
        self.reference_solver = load_state(state, "reference")
        timing_ms(self.reference_solver, self.view.steering, reps=1)   # warm-up
        return self.snapshot(state, "start")

    def timing_pair(self, state: SolverState) -> tuple[float, float]:
        """(candidate_ms, reference_ms), measured back to back."""
        cand = timing_ms(load_state(state, "timing"), self.view.steering)
        ref = timing_ms(self.reference_solver, self.view.steering)
        return cand, ref

    def try_proposal(self, base: Snapshot, proposal: Proposal) -> Trial:
        verdict = guard.check_target(proposal)
        if not verdict.ok:
            return Trial(proposal, verdict, stage="static")
        try:
            new_state = apply(base.state, proposal)
        except Exception as exc:
            return Trial(proposal, guard.Verdict(False, "apply", str(exc)), stage="static")
        verdict = guard.static_guard(proposal, new_state.render(), self.view.steering)
        if not verdict.ok:
            return Trial(proposal, verdict, stage="static")
        try:
            cand = self.snapshot(new_state)
        except Exception as exc:
            return Trial(proposal, guard.Verdict(False, "load", f"{type(exc).__name__}: {exc}"),
                         stage="load", error=str(exc))
        cand_ms, ref_ms = self.timing_pair(new_state)
        verdict = guard.dynamic_guard(
            start_fingerprint=self.fingerprint,
            steer_n=cand.steer.n, steer_expected=self.view.steering_size,
            val_n=cand.val.n, val_expected=self.view.validation_size,
            candidate_ms=cand_ms, reference_ms=ref_ms, floor_ratio=self.floor_ratio,
            steer_before=base.steer.accuracy, steer_after=cand.steer.accuracy,
            val_before=base.val.accuracy, val_after=cand.val.accuracy)
        trial = Trial(proposal, verdict, cand, "dynamic" if not verdict.ok else "scored")
        trial.timing = (cand_ms, ref_ms)
        return trial

    @staticmethod
    def judge(base: Snapshot, trial: Trial) -> tuple[str, str]:
        if not trial.verdict.ok:
            return "rejected", f"guard rejected ({trial.verdict.check}): {trial.verdict.reason}"
        b, a = base.val, trial.candidate.val
        delta = a.n_correct - b.n_correct
        if a.accuracy > b.accuracy:
            return "keep", f"validation {b.accuracy:.3f} -> {a.accuracy:.3f} ({delta:+d} questions)"
        if a.accuracy == b.accuracy:
            return "revert", (f"validation unchanged at {b.accuracy:.3f}; the keep rule "
                              "needs a strict improvement")
        return "revert", f"validation dropped {b.accuracy:.3f} -> {a.accuracy:.3f} ({delta:+d})"

    def accept(self, trial: "Trial") -> Snapshot:
        cand_ms, ref_ms = trial.timing
        self.floor_ratio = min(self.floor_ratio, cand_ms / ref_ms)
        return trial.candidate

    def record(self, iteration: int, base: Snapshot, trial: Trial | None, decision: str,
               reason: str, t0: float, proposal: Proposal | None = None, **extra) -> dict:
        p = trial.proposal if trial else proposal
        entry = {"iteration": iteration, **(p.summary() if p else {}),
                 "proposer": p.proposer if p else self.ledger.proposer,
                 "decision": decision, "reason": reason,
                 "steering_before": round(base.steer.accuracy, 4),
                 "val_before": round(base.val.accuracy, 4),
                 "wall_clock_s": round(time.perf_counter() - t0, 4),
                 "evaluations_so_far": self.evaluations}
        if trial is not None:
            entry["guard"] = trial.verdict.as_dict()
            entry["guard_stage"] = trial.stage
            if trial.candidate is not None:
                c = trial.candidate
                before, after = base.steer.correct_ids(), c.steer.correct_ids()
                entry.update(
                    steering_after=round(c.steer.accuracy, 4),
                    val_after=round(c.val.accuracy, 4),
                    median_latency_ms=round(c.median_latency_ms, 4),
                    timing_ratio=round(trial.timing[0] / trial.timing[1], 3),
                    actual_fixes=sorted(after - before), regressions=sorted(before - after),
                    state_key=c.state.key())
        entry.update(extra)
        return self.ledger.append(entry)


def save_solver(state: SolverState, name: str) -> Path:
    SOLVER_DIR.mkdir(parents=True, exist_ok=True)
    path = SOLVER_DIR / f"{name}.py"
    path.write_text(state.render(), encoding="utf-8")
    return path


def heldout(state: SolverState, *, method: str, run_id: str, label: str,
            proposer: str) -> EvalReport:
    """The only route to the held-out number. Must be called after the loop."""
    with final_phase(method):
        return vault.heldout_score(load_state(state, "final"), method=method, run_id=run_id,
                                   label=label, proposer=proposer)
