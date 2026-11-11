"""Small helpers shared by the method run scripts."""
from __future__ import annotations

import json
import os
import statistics
from pathlib import Path

from rich.console import Console
from rich.table import Table

RESULTS_DIR = Path(os.environ.get("RSI_RESULTS_DIR",
                                  Path(__file__).resolve().parents[1] / "docs" / "results"))
console = Console(width=200)


def mean_sd(values) -> str:
    values = list(values)
    if len(values) == 1:
        return f"{values[0]:.3f}"
    return f"{statistics.mean(values):.3f} ± {statistics.stdev(values):.3f}"


def table(title: str, columns: list[str], rows: list[list]) -> None:
    t = Table(title=title)
    for c in columns:
        t.add_column(c)
    for r in rows:
        t.add_row(*[str(x) for x in r])
    console.print(t)


def save(name: str, payload: dict) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / f"{name}.json"
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return path
