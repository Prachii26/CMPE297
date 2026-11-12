"""Run AIDE2: rewrite the inner agent's search-and-control module, select on a
hidden evaluation.

    .\\.venv\\Scripts\\python.exe 03_aide2\\run.py                  # 3 outer seeds x 8 generations
    .\\.venv\\Scripts\\python.exe 03_aide2\\run.py --outer-seeds 0 --generations 6 --verbose
"""
from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(Path(__file__).parent)]

from core.cli import mean_sd, save, table  # noqa: E402
import aide_outer  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outer-seeds", type=int, nargs="+", default=[0, 1, 2])
    ap.add_argument("--generations", type=int, default=8)
    ap.add_argument("--per-generation", type=int, default=3)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    runs = []
    for s in args.outer_seeds:
        name = f"03_aide2_scripted_outer{s}"
        print(f"outer seed {s}: {args.generations} generations x {args.per_generation} "
              f"rewrites -> {name}.jsonl")
        runs.append(aide_outer.run(generations=args.generations,
                                   per_generation=args.per_generation, outer_seed=s,
                                   ledger_name=name, verbose=args.verbose))
        r = runs[-1]
        table(f"lineage, outer seed {s}", ["generation", "survivor", "change kept", "hidden",
                                           "inner evals", "hack attempts / inner run"],
              [[l["generation"], l["key"],
                (f"{l['change']['slot']}: {l['change']['from']} -> {l['change']['to']}"
                 if l["change"] else "-"), round(l["hidden"], 3), round(l["evals"], 1),
                round(l["shortcut_attempts"], 2)] for l in r["lineage"]])
        print("surviving changes:", r["surviving_changes"])

    table("03_aide2 summary", ["outer seed", "hidden gen0 -> final", "held-out gen0 -> final",
                               "inner evals gen0 -> final", "hack attempts gen0 -> final",
                               "benchmarks", "wall s"],
          [[r["outer_seed"], f"{r['hidden_start']} -> {r['hidden_final']}",
            f"{r['heldout_start']} -> {r['heldout_final']}",
            f"{r['inner_evals_start']:.1f} -> {r['inner_evals_final']:.1f}",
            f"{r['shortcut_attempts_start']:.2f} -> {r['shortcut_attempts_final']:.2f}",
            r["benchmarks"], r["wall_clock_s"]] for r in runs])
    agg = {k: mean_sd(r[k] for r in runs) for k in
           ("hidden_start", "hidden_final", "heldout_start", "heldout_final",
            "inner_evals_start", "inner_evals_final", "shortcut_attempts_start",
            "shortcut_attempts_final")}
    print("aggregate:", agg)
    out = save("03_aide2_scripted", {
        "method": "03_aide2", "proposer": "scripted (outer) / scripted, fixed (inner)",
        "generations": args.generations, "per_generation": args.per_generation,
        "outer_seeds": args.outer_seeds, "aggregate": agg, "runs": runs,
        "heldout_final_mean": statistics.mean(r["heldout_final"] for r in runs)})
    print("summary ->", out)


if __name__ == "__main__":
    main()
