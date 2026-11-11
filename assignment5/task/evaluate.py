"""The evaluator and the metric definition. Nothing an improver proposes may
touch this file -- the guard fingerprints it before every run and rejects any
edit that names it (guard/guard.py).

Metric: exact result-set match. A predicted query is correct when its rows,
normalised exactly like the gold rows (floats to 2dp), equal the gold result:
as a set when order does not matter, as a list when the question asks for an
order. Errors, timeouts and non-SELECT statements count as wrong, never as
skipped -- the denominator is always the full split.

Latency is recorded in two parts per question: solve_ms (the solver turning
text into SQL) and exec_ms (SQLite running it). The reported latency is their
sum; the guard's early-return check uses solve_ms, because a gutted solver
shows up there first.
"""
from __future__ import annotations

import sqlite3
import statistics
import time
from dataclasses import dataclass, field

from task import db
from task.questions import normalize_rows

QUERY_TIME_LIMIT_S = 0.5


def _eval_connection() -> sqlite3.Connection:
    conn = db.connect()
    conn.execute("PRAGMA query_only = ON")    # predicted SQL can never write
    return conn


_CONN: sqlite3.Connection | None = None


def connection() -> sqlite3.Connection:
    global _CONN
    if _CONN is None:
        _CONN = _eval_connection()
    return _CONN


def run_sql(sql: str) -> list[tuple]:
    """Execute one predicted query with a wall-clock limit."""
    head = sql.lstrip().split(None, 1)[0].upper() if sql and sql.strip() else ""
    if head not in ("SELECT", "WITH"):
        raise ValueError(f"not a SELECT statement: {head or '(empty)'}")
    conn = connection()
    deadline = time.perf_counter() + QUERY_TIME_LIMIT_S
    conn.set_progress_handler(lambda: 1 if time.perf_counter() > deadline else 0, 10_000)
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.set_progress_handler(None, 0)


def results_match(rows: list[tuple], gold_result: list, ordered: bool) -> bool:
    return normalize_rows(rows, ordered) == gold_result


@dataclass
class QuestionResult:
    qid: str
    family: str
    phrasing: str
    correct: bool
    sql: str
    handler: str
    error: str
    n_rows: int
    solve_ms: float
    exec_ms: float

    @property
    def latency_ms(self) -> float:
        return self.solve_ms + self.exec_ms


@dataclass
class EvalReport:
    split: str
    n: int
    n_correct: int
    results: list[QuestionResult] = field(default_factory=list)

    @property
    def accuracy(self) -> float:
        return self.n_correct / self.n if self.n else 0.0

    @property
    def median_latency_ms(self) -> float:
        return statistics.median(r.latency_ms for r in self.results) if self.results else 0.0

    @property
    def median_solve_ms(self) -> float:
        return statistics.median(r.solve_ms for r in self.results) if self.results else 0.0

    def correct_ids(self) -> set[str]:
        return {r.qid for r in self.results if r.correct}

    def by_qid(self) -> dict[str, QuestionResult]:
        return {r.qid: r for r in self.results}


def evaluate(solver, questions: list[dict], split: str) -> EvalReport:
    """Score `solver` on every question in `questions`. Never skips one."""
    results: list[QuestionResult] = []
    tracer = getattr(solver, "trace", None)
    for q in questions:
        handler, sql, error, rows = "?", "", "", []
        t0 = time.perf_counter()
        try:
            if tracer is not None:
                handler, sql = tracer(q["question"])
            else:
                sql = solver.solve(q["question"])
        except Exception as exc:                 # a crashing solver is just wrong
            error = f"solver: {type(exc).__name__}: {exc}"
        t1 = time.perf_counter()
        if not error:
            try:
                rows = run_sql(sql)
            except Exception as exc:
                error = f"sql: {type(exc).__name__}: {exc}"
        t2 = time.perf_counter()
        correct = not error and results_match(rows, q["gold_result"], q["ordered"])
        results.append(QuestionResult(
            qid=q["qid"], family=q["family"], phrasing=q["phrasing"], correct=correct,
            sql=sql or "", handler=handler, error=error, n_rows=len(rows),
            solve_ms=(t1 - t0) * 1000, exec_ms=(t2 - t1) * 1000))
    return EvalReport(split=split, n=len(questions),
                      n_correct=sum(r.correct for r in results), results=results)
