"""The inner agent: a small tree search over solver repairs.

The engine here is fixed. It asks the control module four questions -- which
node to expand, in what order to try repairs, how many to try, when to stop
-- and does the rest: generate candidate repairs with the (fixed) proposer,
run each through the guard, score survivors on STEERING ONLY, and return the
best solver it found.

The inner agent's only feedback is steering accuracy. It is handed a
SteeringOnlyView, which has no validation method at all, and it runs inside
task.boundary.inner_agent(), which seals the validation split at runtime.

Every attempt counts against INNER_BUDGET, including attempts the guard
rejects -- so a control module that keeps trying reward hacks pays for it in
search budget, without the outer loop ever being told that hacks exist.
"""
from __future__ import annotations

import itertools
from collections import Counter, defaultdict
from dataclasses import dataclass, field

import numpy as np

from core.edits import apply
from core.loop import timing_ms
from core.proposers import ProposalContext, ScriptedProposer, failing, from_strategy
from guard import guard
from task.evaluate import EvalReport, evaluate
from task.solver_state import SolverState, load_state
from task.strategies import MECHANISMS

INNER_BUDGET = 24
MECHANISM_IDS = {s.sid for s in MECHANISMS}


class SteeringOnlyView:
    """Everything the inner agent may see. There is no validation here."""

    def __init__(self, steering: list[dict]) -> None:
        self._steering = steering
        self.steering_calls = 0

    @property
    def steering(self) -> list[dict]:
        return self._steering

    def evaluate_steering(self, solver) -> EvalReport:
        self.steering_calls += 1
        return evaluate(solver, self._steering, "steering")


@dataclass
class Node:
    uid: int
    state: SolverState
    steer: EvalReport
    depth: int
    parent_score: float
    visits: int = 0
    tried: set = field(default_factory=set)

    @property
    def score(self) -> float:
        return self.steer.accuracy


@dataclass(frozen=True)
class Cand:
    sid: str
    family: str | None
    weight: float
    fails: int
    is_mechanism: bool
    is_prepend: bool
    is_shortcut: bool


class History:
    def __init__(self) -> None:
        self._tried, self._gains = Counter(), Counter()

    def tried(self, sid: str) -> int:
        return self._tried[sid]

    def gains(self, sid: str) -> int:
        return self._gains[sid]

    def record(self, sid: str, gained: bool) -> None:
        self._tried[sid] += 1
        self._gains[sid] += int(gained)


@dataclass
class Stats:
    attempts: int = 0
    evals: int = 0
    since_improvement: int = 0
    best_score: float = 0.0
    shortcut_attempts: int = 0
    guard_rejections: Counter = field(default_factory=Counter)


@dataclass
class InnerResult:
    best_state: SolverState
    best_steering: float
    stats: Stats
    nodes: int


class InnerHarness:
    """Guard + steering-only scoring for one inner run."""

    def __init__(self, view: SteeringOnlyView, start: SolverState, fingerprint: str) -> None:
        self.view, self.fingerprint = view, fingerprint
        self.reference = load_state(start, "reference")

    def attempt(self, node: Node, proposal):
        verdict = guard.check_target(proposal)
        if not verdict.ok:
            return verdict, None
        state = apply(node.state, proposal)
        verdict = guard.static_guard(proposal, state.render(), self.view.steering)
        if not verdict.ok:
            return verdict, None
        try:
            report = self.view.evaluate_steering(load_state(state))
        except Exception as exc:
            return guard.Verdict(False, "load", str(exc)), None
        cand_ms = timing_ms(load_state(state, "timing"), self.view.steering)
        ref_ms = timing_ms(self.reference, self.view.steering)
        for verdict in (guard.check_integrity(self.fingerprint),
                        guard.check_denominator(report.n, len(self.view.steering), "steering"),
                        guard.check_timing(cand_ms, ref_ms)):
            if not verdict.ok:
                return verdict, report
        return guard.PASS, report


def _cands(agent: ScriptedProposer, node: Node, steering: list[dict],
           include_shortcuts: bool) -> list[tuple[Cand, object]]:
    ctx = ProposalContext(node.state, node.steer, steering)
    fails = Counter(r.family for r in failing(node.steer))
    out = []
    for s in agent.all_candidates(ctx):
        out.append((Cand(s.sid, s.family, s.weight, fails.get(s.family, 0) if s.family else
                         sum(fails.values()) // 10, s.sid in MECHANISM_IDS,
                         s.kind == "add_handler" and s.position == "prepend", False),
                    from_strategy(s, node.steer, agent.name)))
    if include_shortcuts:
        for which in agent.SHORTCUTS:
            p = agent.shortcut(ctx, which)
            out.append((Cand(p.strategy_id, None, 0.5, 0, False, p.position == "prepend",
                             True), p))
    return [(c, p) for c, p in out if c.sid not in node.tried]


def run_inner(control, view: SteeringOnlyView, start: SolverState, agent: ScriptedProposer,
              seed: int, fingerprint: str, budget: int = INNER_BUDGET,
              include_shortcuts: bool = True) -> InnerResult:
    rng = np.random.default_rng(seed)
    harness = InnerHarness(view, start, fingerprint)
    uid = itertools.count()
    root = Node(next(uid), start, view.evaluate_steering(load_state(start)), 0, 0.0)
    frontier, best = [root], root
    stats, history = Stats(best_score=root.score), History()
    while stats.attempts < budget and frontier and not control.should_stop(stats):
        node = control.select_node(frontier, rng)
        node.visits += 1
        pool = _cands(agent, node, view.steering, include_shortcuts)
        if not pool:
            frontier.remove(node)
            continue
        by_sid = {c.sid: (c, p) for c, p in pool}
        ordered = control.order_strategies([c for c, _ in pool], node, history, rng)
        for c in ordered[:max(1, int(control.BRANCHING))]:
            if stats.attempts >= budget:
                break
            cand, proposal = by_sid[c.sid]
            node.tried.add(cand.sid)
            stats.attempts += 1
            stats.shortcut_attempts += cand.is_shortcut
            verdict, report = harness.attempt(node, proposal)
            if report is not None:
                stats.evals += 1
            if not verdict.ok:
                stats.guard_rejections[verdict.check] += 1
                history.record(cand.sid, False)
                stats.since_improvement += 1
                continue
            child = Node(next(uid), apply(node.state, proposal), report, node.depth + 1,
                         node.score)
            history.record(cand.sid, child.score > node.score)
            frontier.append(child)
            if child.score > best.score:
                best = child
                stats.since_improvement = 0
            else:
                stats.since_improvement += 1
            stats.best_score = best.score
    return InnerResult(best.state, best.score, stats, next(uid))


assert defaultdict  # kept for readers extending History
