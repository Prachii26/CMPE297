"""The outer loop: propose rewrites to the search-and-control module, benchmark
each modified inner agent on the hidden evaluation, keep what wins.

One survivor per generation: every candidate is a single-slot rewrite of the
current best module; the best candidate of the generation replaces the
current module only if it beats it -- higher hidden accuracy, or equal
accuracy at lower inner cost (fewer steering scorings). AIDE2 is about
research *efficiency*, so cost is the tie-breaker rather than ignored.

Lineage: ControlSpec.origin records which generation set each slot's current
value, so the final module can be read as "this came from generation 3,
that from generation 5, the rest is the generation-0 original".
"""
from __future__ import annotations

import time

import numpy as np

from aide_control import SLOTS, ControlSpec, options
from aide_hidden import BenchmarkResult, HiddenBenchmark
from core.ledger import Ledger, new_run_id
from core import loop as loop_mod
from core.loop import heldout, save_solver
from task.boundary import improvement_phase

METHOD = "03_aide2"


class OuterProposer:
    """Deterministic single-slot rewrites of the control module."""

    name = "scripted-outer"

    def __init__(self, seed: int) -> None:
        self.rng = np.random.default_rng(seed)

    def propose(self, spec: ControlSpec, seen: set[str], generation: int, k: int):
        out, tries = [], 0
        while len(out) < k and tries < 500:
            tries += 1
            slot = SLOTS[int(self.rng.integers(len(SLOTS)))]
            choices = [o for o in options(slot) if o != spec.value(slot)]
            new = choices[int(self.rng.integers(len(choices)))]
            cand = spec.with_slot(slot, new, generation)
            if cand.key() in seen:
                continue
            seen.add(cand.key())
            out.append((cand, {"slot": slot, "from": spec.value(slot), "to": new}))
        return out


def better(a: BenchmarkResult, b: BenchmarkResult) -> bool:
    if not a.verdict.ok:
        return False
    return a.hidden > b.hidden + 1e-12 or (abs(a.hidden - b.hidden) < 1e-12
                                           and a.evals < b.evals - 1e-9)


def run(*, generations: int, per_generation: int, outer_seed: int, inner_seeds=(0, 1, 2),
        ledger_name: str, verbose: bool = False) -> dict:
    run_id = new_run_id(METHOD)
    proposer = OuterProposer(outer_seed)
    ledger = Ledger(ledger_name, run_id=run_id, method=METHOD, proposer=proposer.name,
                    meta={"outer_seed": outer_seed, "generations": generations,
                          "per_generation": per_generation, "inner_seeds": list(inner_seeds),
                          "inner_proposer": "scripted (fixed: ScriptedProposer(0))"})
    t0 = time.perf_counter()
    with improvement_phase(METHOD):
        bench = HiddenBenchmark(inner_seeds)
        start_spec = ControlSpec()
        best, best_res = start_spec, bench.run(start_spec)
        start_res = best_res
        seen = {best.key()}
        ledger.append({"iteration": 0, "generation": 0, "candidate": best.key(),
                       "parent": None, "change": None, "choices": best.choices(),
                       "result": best_res.public(), "decision": "start",
                       "reason": "generation-0 control module"})
        lineage = [{"generation": 0, "key": best.key(), "hidden": best_res.hidden,
                    "evals": best_res.evals, "shortcut_attempts": best_res.shortcut_attempts,
                    "change": None}]
        it = 0
        for g in range(1, generations + 1):
            winner = None
            for cand, change in proposer.propose(best, seen, g, per_generation):
                it += 1
                res = bench.run(cand)
                wins = better(res, best_res)
                ledger.append({"iteration": it, "generation": g, "candidate": cand.key(),
                               "parent": best.key(), "change": change,
                               "choices": cand.choices(), "result": res.public(),
                               "decision": "candidate-win" if wins else "discard",
                               "reason": (f"hidden {best_res.hidden:.3f} -> {res.hidden:.3f}, "
                                          f"inner evals {best_res.evals:.1f} -> {res.evals:.1f}")
                               if res.verdict.ok else f"guard: {res.verdict.reason}"})
                if verbose:
                    print(f"  g{g} {change['slot']:16s} {str(change['from']):>18s} -> "
                          f"{str(change['to']):<18s} hidden {res.hidden:.3f} "
                          f"evals {res.evals:5.1f} {'WIN' if wins else ''}")
                if wins and (winner is None or better(res, winner[1])):
                    winner = (cand, res, change)
            if winner:
                best, best_res, change = winner
                ledger.note({"type": "survivor", "generation": g, "key": best.key(),
                             "change": change, "hidden": best_res.hidden,
                             "evals": best_res.evals})
            lineage.append({"generation": g, "key": best.key(), "hidden": best_res.hidden,
                            "evals": best_res.evals,
                            "shortcut_attempts": best_res.shortcut_attempts,
                            "change": winner[2] if winner else None})
        benchmarks, hidden_evals = bench.calls, bench.hidden_evaluations
    # held-out: the solvers the generation-0 and final inner agents produced
    ho_start = [heldout(s, method=METHOD, run_id=run_id, label=f"gen0-inner{i}",
                        proposer=proposer.name).accuracy
                for i, s in enumerate(start_res.states)]
    ho_final = [heldout(s, method=METHOD, run_id=run_id, label=f"final-inner{i}",
                        proposer=proposer.name).accuracy
                for i, s in enumerate(best_res.states)]
    save_solver(best_res.states[0], f"{ledger_name}_inner0")
    loop_mod.SOLVER_DIR.mkdir(parents=True, exist_ok=True)
    (loop_mod.SOLVER_DIR / f"{ledger_name}_control_final.py").write_text(
        best.render(), encoding="utf-8")
    origin = dict(best.origin)
    summary = {
        "outer_seed": outer_seed, "run_id": run_id, "proposer": proposer.name,
        "inner_proposer": "scripted", "generations": generations,
        "per_generation": per_generation, "benchmarks": benchmarks,
        "hidden_evaluations": hidden_evals,
        "start_choices": start_spec.choices(), "final_choices": best.choices(),
        "surviving_changes": {s: {"value": best.value(s), "from_generation": origin[s]}
                              for s in SLOTS if origin[s] > 0},
        "lineage": lineage,
        "hidden_start": round(start_res.hidden, 4), "hidden_final": round(best_res.hidden, 4),
        "inner_evals_start": start_res.evals, "inner_evals_final": best_res.evals,
        "shortcut_attempts_start": start_res.shortcut_attempts,
        "shortcut_attempts_final": best_res.shortcut_attempts,
        "heldout_start_per_seed": ho_start, "heldout_final_per_seed": ho_final,
        "heldout_start": round(sum(ho_start) / len(ho_start), 4),
        "heldout_final": round(sum(ho_final) / len(ho_final), 4),
        "wall_clock_s": round(time.perf_counter() - t0, 3),
    }
    ledger.close(summary)
    return summary
