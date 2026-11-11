"""Naive RSI: propose, evaluate, keep if validation improved, else revert.

This is the control. It has no memory beyond the current solver, no
diagnosis, and a fixed proposer; whatever the three methods add is measured
against it.
"""
from __future__ import annotations

import time

from core.ledger import Ledger, new_run_id
from core.loop import Harness, heldout, save_solver
from core.metrics import behaviour
from core.proposers import ProposalContext, ProposerError
from task.boundary import improvement_phase
from task.splits import ImproverView
from task.strategies import initial_state

METHOD = "00_baseline"


def run(proposer, *, iterations: int, seed: int, ledger_name: str,
        method: str = METHOD, verbose: bool = False) -> dict:
    run_id = new_run_id(method)
    ledger = Ledger(ledger_name, run_id=run_id, method=method, proposer=proposer.name,
                    meta={"seed": seed, "iterations": iterations,
                          "keep_rule": "strict validation improvement"})
    view = ImproverView()
    t_run = time.perf_counter()
    with improvement_phase(method):
        h = Harness(view, ledger)
        cur = h.start(initial_state())
        ledger.note({"type": "start_state", "steering": cur.steer.accuracy,
                     "validation": cur.val.accuracy,
                     "median_latency_ms": round(cur.median_latency_ms, 4)})
        for it in range(1, iterations + 1):
            t0 = time.perf_counter()
            ctx = ProposalContext(cur.state, cur.steer, view.steering, ledger.entries)
            try:
                proposal = proposer.propose(ctx)
            except ProposerError as exc:
                h.record(it, cur, None, "proposer_error", str(exc), t0)
                continue
            trial = h.try_proposal(cur, proposal)
            decision, reason = h.judge(cur, trial)
            h.record(it, cur, trial, decision, reason, t0)
            if verbose:
                print(f"  it {it:2d} {proposal.strategy_id:28s} {decision:8s} {reason[:70]}")
            if decision == "keep":
                cur = h.accept(trial)
        evaluations = h.evaluations
    start = heldout(initial_state(), method=method, run_id=run_id, label="start",
                    proposer=proposer.name)
    final = heldout(cur.state, method=method, run_id=run_id, label="final",
                    proposer=proposer.name)
    solver_path = save_solver(cur.state, ledger_name)
    summary = {
        "seed": seed, "proposer": proposer.name, "run_id": run_id,
        "validation_final": round(cur.val.accuracy, 4),
        "steering_final": round(cur.steer.accuracy, 4),
        "heldout_start": round(start.accuracy, 4), "heldout_final": round(final.accuracy, 4),
        "heldout_median_latency_ms": round(final.median_latency_ms, 4),
        "evaluations": evaluations, "wall_clock_s": round(time.perf_counter() - t_run, 3),
        "final_solver": str(solver_path.name), "final_components": cur.state.cids(),
        "final_flags": dict(cur.state.flags),
        **behaviour(ledger.entries),
    }
    ledger.close(summary)
    return summary
