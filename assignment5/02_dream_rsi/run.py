"""Run Dream-RSI and Recursive Fixed Exploration on the same seeds.

    .\\.venv\\Scripts\\python.exe 02_dream_rsi\\run.py                     # 10 seeds, 10 rounds x 6 calls
    .\\.venv\\Scripts\\python.exe 02_dream_rsi\\run.py --rounds 8 --budget 6

Four arms per seed: "dream" (the designed method), "fixed" (Recursive Fixed
Exploration, the paper's controlled baseline), and two POST-HOC variants
added after the designed arm failed on seed 0 -- "dream_context" (tests a
first diagnosis that turned out wrong) and "dream_support" (tests the
corrected one). Post-hoc arms are reported separately, never mixed into the
designed result.
"""
from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(Path(__file__).parent)]

from core.cli import mean_sd, save, table  # noqa: E402
import dream_loop  # noqa: E402


def compare(arm_run: dict, fixed: dict) -> dict:
    target = fixed["validation_final"]
    reach = dream_loop.calls_to_reach(arm_run["curve"], target)
    fixed_reach = dream_loop.calls_to_reach(fixed["curve"], target)
    return {"target_validation": target, "fixed_calls_to_target": fixed_reach,
            "calls_to_target": reach,
            "calls_saved": (fixed_reach - reach) if reach is not None else None}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=list(range(10)))
    ap.add_argument("--rounds", type=int, default=10)
    ap.add_argument("--budget", type=int, default=6, help="live discovery calls per round")
    args = ap.parse_args()

    pairs = []
    for seed in args.seeds:
        runs = {}
        for arm in dream_loop.ARMS:
            name = f"02_dream_rsi_{arm}_scripted_seed{seed}"
            print(f"seed {seed} {arm}: {args.rounds} rounds x {args.budget} calls -> {name}.jsonl")
            runs[arm] = dream_loop.run_arm(arm, seed=seed, rounds=args.rounds,
                                           budget=args.budget, ledger_name=name)
        pairs.append({"seed": seed, **runs,
                      "dream_vs_fixed": compare(runs["dream"], runs["fixed"]),
                      "context_vs_fixed": compare(runs["dream_context"], runs["fixed"]),
                      "support_vs_fixed": compare(runs["dream_support"], runs["fixed"])})

    table("02_dream_rsi vs Recursive Fixed Exploration (same seed, budget, start policy)",
          ["seed", "fixed val", "dream val", "context val", "support val",
           "fixed calls to its final", "dream saved", "context saved", "support saved"],
          [[p["seed"], p["fixed"]["validation_final"], p["dream"]["validation_final"],
            p["dream_context"]["validation_final"], p["dream_support"]["validation_final"],
            p["dream_vs_fixed"]["fixed_calls_to_target"], p["dream_vs_fixed"]["calls_saved"],
            p["context_vs_fixed"]["calls_saved"], p["support_vs_fixed"]["calls_saved"]]
           for p in pairs])

    def saved(key):
        return [p[key]["calls_saved"] for p in pairs if p[key]["calls_saved"] is not None]

    agg = {}
    for arm in dream_loop.ARMS:
        agg[f"{arm}_heldout"] = mean_sd(p[arm]["heldout_final"] for p in pairs)
        agg[f"{arm}_validation"] = mean_sd(p[arm]["validation_final"] for p in pairs)
    agg["fixed_calls_to_its_final"] = mean_sd(p["dream_vs_fixed"]["fixed_calls_to_target"]
                                              for p in pairs)
    for key, label in (("dream_vs_fixed", "dream"), ("context_vs_fixed", "dream_context"),
                       ("support_vs_fixed", "dream_support")):
        s = saved(key)
        agg[f"{label}_calls_saved_where_reached"] = mean_sd(s) if s else "n/a"
        agg[f"{label}_reached_fixed_final"] = f"{len(s)}/{len(pairs)}"
    print("aggregate:", agg)
    out = save("02_dream_rsi_scripted", {
        "method": "02_dream_rsi", "proposer": "scripted", "rounds": args.rounds,
        "budget_per_round": args.budget, "seeds": args.seeds, "aggregate": agg,
        "pairs": pairs,
        **{f"{arm}_heldout_mean": statistics.mean(p[arm]["heldout_final"] for p in pairs)
           for arm in dream_loop.ARMS}})
    print("summary ->", out)


if __name__ == "__main__":
    main()
