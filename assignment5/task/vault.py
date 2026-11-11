"""The only reader of the held-out split.

Every call goes through task.boundary.assert_heldout_allowed() first, so the
split is sealed during any improvement loop and never reachable from a
solver, a search-control module or a proposer. Every successful read is
appended to docs/ledgers/heldout_access.jsonl with who asked and why, so the
claim "the held-out number was computed once, after the loop" is checkable
from the ledger rather than taken on trust.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from task.boundary import assert_heldout_allowed, current_phase
from task.evaluate import EvalReport, evaluate

_HELDOUT_FILE = Path(__file__).parent / "data" / "heldout.json"
AUDIT_DIR = Path(os.environ.get("RSI_LEDGER_DIR",
                                Path(__file__).resolve().parents[1] / "docs" / "ledgers"))


def _audit(record: dict) -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    with open(AUDIT_DIR / "heldout_access.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")


def heldout_score(solver, *, method: str, run_id: str, label: str,
                  proposer: str) -> EvalReport:
    assert_heldout_allowed()
    questions = json.loads(_HELDOUT_FILE.read_text(encoding="utf-8"))
    report = evaluate(solver, questions, "heldout")
    _audit({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "phase": current_phase(),
            "method": method, "run_id": run_id, "label": label, "proposer": proposer,
            "n": report.n, "n_correct": report.n_correct,
            "accuracy": round(report.accuracy, 4),
            "median_latency_ms": round(report.median_latency_ms, 4)})
    return report
