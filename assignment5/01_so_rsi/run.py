"""Run SO-RSI against the naive baseline on identical seeds and budgets.

    .\\.venv\\Scripts\\python.exe 01_so_rsi\\run.py                 # 5 seeds x 20 iterations
    .\\.venv\\Scripts\\python.exe 01_so_rsi\\run.py --seeds 2 --verbose

Reads the baseline summary from docs/results/00_baseline_scripted.json, so
run 00_baseline first.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(Path(__file__).parent)]

from core.cli import RESULTS_DIR, mean_sd, save, table  # noqa: E402
from core.proposers import ScriptedProposer  # noqa: E402
import so_loop  # noqa: E402

METRICS = ["heldout_final", "keep", "repeated_fix_attempts", "blind_repeats", "oscillations",
           "zero_progress", "evaluations"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2, 3, 4])
    ap.add_argument("--iterations", type=int, default=20)
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--ablation", choices=so_loop.ABLATIONS, default="full")
    args = ap.parse_args()
    tag = "" if args.ablation == "full" else f"_ablation-{args.ablation}"

    runs = []
    for seed in args.seeds:
        name = f"01_so_rsi{tag}_scripted_seed{seed}"
        print(f"seed {seed}: scripted, {args.iterations} iterations -> {name}.jsonl")
        runs.append(so_loop.run(ScriptedProposer(seed), iterations=args.iterations, seed=seed,
                                ledger_name=name, verbose=args.verbose,
                                ablation=args.ablation))

    base_path = RESULTS_DIR / "00_baseline_scripted.json"
    base = {r["seed"]: r for r in json.loads(base_path.read_text())["runs"]} \
        if base_path.exists() else {}
    rows = []
    for r in runs:
        b = base.get(r["seed"], {})
        rows.append([r["seed"], f"{b.get('heldout_final', '?')} -> {r['heldout_final']}",
                     f"{b.get('blind_repeats', '?')} -> {r['blind_repeats']}",
                     f"{b.get('repeated_fix_attempts', '?')} -> {r['repeated_fix_attempts']}",
                     f"{b.get('oscillations', '?')} -> {r['oscillations']}",
                     f"{b.get('zero_progress', '?')} -> {r['zero_progress']}",
                     f"{b.get('evaluations', '?')} -> {r['evaluations']}",
                     r["vetoed_before_evaluation"], r["probe_queries"],
                     ",".join(r["mechanisms_applied"]) or "-", r["guard_rejections"]])
    table(f"01_so_rsi[{args.ablation}] vs 00_baseline (baseline -> SO-RSI, same seed and budget)",
          ["seed", "held-out", "blind repeats", "repeated fixes", "oscillations",
           "zero-progress", "evaluations", "vetoed", "probe queries", "mechanisms",
           "guard rejections"], rows)
    agg = {k: mean_sd(r[k] for r in runs) for k in METRICS}
    base_agg = {k: mean_sd(base[s][k] for s in args.seeds if s in base) for k in METRICS} \
        if base else {}
    print("SO-RSI mean:  ", agg)
    print("baseline mean:", base_agg)
    out = save(f"01_so_rsi{tag}_scripted", {
        "method": "01_so_rsi", "ablation": args.ablation, "proposer": "scripted", "iterations": args.iterations,
        "seeds": args.seeds, "aggregate": agg, "baseline_aggregate": base_agg, "runs": runs,
        "heldout_final_mean": statistics.mean(r["heldout_final"] for r in runs)})
    print("summary ->", out)


if __name__ == "__main__":
    main()
