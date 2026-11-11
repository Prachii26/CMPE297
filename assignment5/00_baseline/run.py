"""Run the naive RSI baseline.

    .\\.venv\\Scripts\\python.exe 00_baseline\\run.py                      # 5 seeds x 20 iterations, scripted
    .\\.venv\\Scripts\\python.exe 00_baseline\\run.py --proposer llm --seeds 0 --iterations 8
"""
from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(Path(__file__).parent)]

from core.cli import mean_sd, save, table  # noqa: E402
from core.ledger import LEDGER_DIR  # noqa: E402
from core.proposers import LLMProposer, ScriptedProposer  # noqa: E402
import naive_loop  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2, 3, 4])
    ap.add_argument("--iterations", type=int, default=20)
    ap.add_argument("--proposer", choices=["scripted", "llm"], default="scripted")
    ap.add_argument("--model", default=None)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    summaries = []
    for seed in args.seeds:
        if args.proposer == "llm":
            proposer = LLMProposer(args.model, max_calls=args.iterations,
                                   transcript=LEDGER_DIR / f"00_baseline_llm_transcript.jsonl")
            name = "00_baseline_llm"
        else:
            proposer = ScriptedProposer(seed)
            name = f"00_baseline_scripted_seed{seed}"
        print(f"seed {seed}: {proposer.name}, {args.iterations} iterations -> {name}.jsonl")
        summaries.append(naive_loop.run(proposer, iterations=args.iterations, seed=seed,
                                        ledger_name=name, verbose=args.verbose))

    table("00_baseline - naive RSI", ["seed", "proposer", "held-out start", "held-out final",
                                      "val final", "kept", "blind repeats", "oscillations",
                                      "zero-progress", "guard rejections", "wall s"],
          [[s["seed"], s["proposer"], s["heldout_start"], s["heldout_final"],
            s["validation_final"], s["keep"], s["blind_repeats"], s["oscillations"],
            s["zero_progress"], s["guard_rejections"], s["wall_clock_s"]] for s in summaries])
    agg = {k: mean_sd(s[k] for s in summaries) for k in
           ("heldout_final", "validation_final", "repeated_fix_attempts", "blind_repeats",
            "oscillations", "zero_progress", "keep")}
    print("mean over seeds:", agg)
    out = save(f"00_baseline_{args.proposer}", {
        "method": "00_baseline", "proposer": args.proposer, "iterations": args.iterations,
        "seeds": args.seeds, "aggregate": agg, "runs": summaries,
        "heldout_final_mean": statistics.mean(s["heldout_final"] for s in summaries)})
    print("summary ->", out)


if __name__ == "__main__":
    main()
