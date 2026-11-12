"""Dream-RSI rounds, and the controlled baseline.

Each round: (1) the current exploration policy drives `budget` live
discovery calls from the best solver found so far; (2) the round's discovery
tree is added to the replay simulator pool; (3) Dream-RSI dreams a better
policy against the pool and redeploys it.

Recursive Fixed Exploration is the same function with arm="fixed": same base
agent, same per-round budget, same starting policy, same random numbers --
it records the pool too, but never dreams, so its policy never changes.
Both arms are seeded identically, so round 1 is the same discovery tree in
both; any difference after that comes from the policy update.
"""
from __future__ import annotations

import time

import numpy as np

from core.ledger import Ledger, new_run_id
from core.loop import Harness, heldout, save_solver
from core.proposers import ScriptedProposer
from dream_dreaming import improve
from dream_online import explore
from dream_policy import DESIGNED, THETA0, WITH_CONTEXT, Policy
from dream_simulator import ReplaySimulator
from task.boundary import improvement_phase
from task.splits import ImproverView
from task.strategies import initial_state

METHOD = "02_dream_rsi"
ARMS = ("dream", "fixed", "dream_context", "dream_support")
POST_HOC = ("dream_context", "dream_support")   # added after seeing the designed arm fail


def run_arm(arm: str, *, seed: int, rounds: int, budget: int, ledger_name: str) -> dict:
    assert arm in ARMS
    run_id = new_run_id(METHOD)
    agent = ScriptedProposer(seed, include_shortcuts=False)    # the base agent: its edit pool
    ledger = Ledger(ledger_name, run_id=run_id, method=METHOD, proposer=agent.name,
                    meta={"arm": arm, "seed": seed, "rounds": rounds,
                          "budget_per_round": budget})
    view = ImproverView()
    rng = np.random.default_rng(seed)
    policy = Policy(THETA0.copy(),
                    active=(WITH_CONTEXT if arm == "dream_context" else DESIGNED).copy())
    sim = ReplaySimulator()
    curve: list[tuple[int, float]] = []
    dream_steps = dream_candidates = 0
    dream_wall = 0.0
    t_run = time.perf_counter()
    with improvement_phase(METHOD):
        h = Harness(view, ledger)
        best = h.start(initial_state())
        state = {"calls": 0, "best": best.val.accuracy}
        curve.append((0, best.val.accuracy))

        def on_call(rec, tree):
            if rec["live_call"]:
                state["calls"] += 1
                if rec["guard"]["ok"]:
                    state["best"] = max(state["best"], rec["val_after"])
                curve.append((state["calls"], state["best"]))
            ledger.append({"iteration": len(ledger.entries) + 1, **rec,
                           "decision": "explore", "arm": arm, "policy": policy.label,
                           "cumulative_calls": state["calls"],
                           "best_val_so_far": state["best"]})

        for r in range(1, rounds + 1):
            tree = explore(policy, best, h, agent, budget, rng, r, on_call)
            sim.add_tree(tree)
            top = tree.best()
            if top.val > best.val.accuracy:
                best = top.snap
            note = {"type": "round_end", "round": r, "arm": arm,
                    "cumulative_calls": state["calls"], "best_val": best.val.accuracy,
                    "tree_nodes": len(tree.nodes), "pool_nodes": len(sim.nodes),
                    "pool_edges": sim.n_edges, "policy": policy.as_dict()}
            if arm != "fixed" and r < rounds:
                t0 = time.perf_counter()
                res = improve(policy, sim, steps=budget, seed=seed * 1000 + r, round_=r,
                              support_only=arm == "dream_support")
                dream_wall += time.perf_counter() - t0
                dream_steps += res.steps_simulated
                dream_candidates += res.candidates_evaluated
                note["dream"] = {"adopted": res.adopted,
                                 "current_score": round(res.current_score, 4),
                                 "best_score": round(res.best_score, 4),
                                 "candidates": res.candidates_evaluated,
                                 "steps_simulated": res.steps_simulated,
                                 "searched_features": res.searched,
                                 "new_policy": res.policy.as_dict()}
                policy = res.policy
            ledger.note(note)
        live_calls = state["calls"]
    start = heldout(initial_state(), method=METHOD, run_id=run_id, label="start",
                    proposer=agent.name)
    final = heldout(best.state, method=METHOD, run_id=run_id, label=f"final-{arm}",
                    proposer=agent.name)
    save_solver(best.state, ledger_name)
    summary = {"arm": arm, "seed": seed, "run_id": run_id, "proposer": agent.name,
               "rounds": rounds, "budget_per_round": budget, "live_calls": live_calls,
               "validation_final": round(best.val.accuracy, 4),
               "heldout_start": round(start.accuracy, 4),
               "heldout_final": round(final.accuracy, 4),
               "heldout_median_latency_ms": round(final.median_latency_ms, 4),
               "curve": curve, "final_policy": policy.as_dict(),
               "dream_candidates": dream_candidates, "dream_steps_simulated": dream_steps,
               "dream_wall_s": round(dream_wall, 3), "pool_nodes": len(sim.nodes),
               "pool_edges": sim.n_edges,
               "wall_clock_s": round(time.perf_counter() - t_run, 3)}
    ledger.close({k: v for k, v in summary.items() if k != "curve"})
    return summary


def calls_to_reach(curve: list[tuple[int, float]], target: float) -> int | None:
    for calls, best in curve:
        if best >= target - 1e-9:
            return calls
    return None
