"""Append-only JSONL run ledger, ported from assignment2/partC/.../ledger.js.

One JSON object per line, so an interrupted run never corrupts the entries
before it and appending is a single write. Each run opens with a run_start
record and closes with a run_end record; several runs may share a file and
are told apart by run_id.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path

LEDGER_DIR = Path(os.environ.get(
    "RSI_LEDGER_DIR", Path(__file__).resolve().parents[1] / "docs" / "ledgers"))


def new_run_id(method: str) -> str:
    return f"{method}-{time.strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:6]}"


class Ledger:
    def __init__(self, name: str, *, run_id: str, method: str, proposer: str,
                 meta: dict | None = None, directory: Path | None = None) -> None:
        self.path = Path(directory or LEDGER_DIR) / f"{name}.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.run_id, self.method, self.proposer = run_id, method, proposer
        self.entries: list[dict] = []
        self._write({"type": "run_start", **(meta or {})})

    def _write(self, record: dict) -> dict:
        record = {"run_id": self.run_id, "method": self.method,
                  "ts": time.strftime("%Y-%m-%dT%H:%M:%S"), **record}
        record.setdefault("proposer", self.proposer)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, default=str) + "\n")
        return record

    def append(self, record: dict) -> dict:
        record = self._write({"type": "iteration", **record})
        self.entries.append(record)
        return record

    def note(self, record: dict) -> dict:
        return self._write(record)

    def close(self, summary: dict) -> dict:
        return self._write({"type": "run_end", **summary})


def read(path: Path, run_id: str | None = None) -> list[dict]:
    if not Path(path).exists():
        return []
    rows = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()
            if line.strip()]
    if run_id is None and rows:
        run_id = [r for r in rows if r["type"] == "run_start"][-1]["run_id"]
    return [r for r in rows if r["run_id"] == run_id]
