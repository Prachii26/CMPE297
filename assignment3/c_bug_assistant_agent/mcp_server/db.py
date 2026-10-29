"""SQLite storage for the VoltLoop bug tracker.

VoltLoop is a synthetic electric-scooter sharing platform. The schema is
deliberately small: bugs, free-text comments, and an append-only status
history so that every status change carries the reason that justified it.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

SEVERITIES = ("S1", "S2", "S3", "S4")
STATUSES = ("open", "in_progress", "blocked", "resolved", "closed")

# Components on the critical revenue/safety path get a triage boost, so a
# mid-severity payments bug can outrank a mid-severity maps bug.
CRITICAL_PATH = {"payments": 120, "auth": 120, "dispatch-api": 60, "iot-firmware": 60}

SEVERITY_WEIGHT = {"S1": 1000, "S2": 500, "S3": 200, "S4": 50}

DEFAULT_DB_NAME = "voltloop_bugs.db"


def db_path() -> Path:
    """Resolve the database file. BUG_DB_PATH wins, else alongside this package."""
    env = os.environ.get("BUG_DB_PATH")
    if env:
        return Path(env)
    return Path(__file__).resolve().parent.parent / DEFAULT_DB_NAME


def get_conn(path: str | Path | None = None) -> sqlite3.Connection:
    target = Path(path) if path is not None else db_path()
    if str(target) != ":memory:":
        target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS bugs (
    id           TEXT PRIMARY KEY,
    title        TEXT NOT NULL,
    description  TEXT NOT NULL,
    component    TEXT NOT NULL,
    severity     TEXT NOT NULL CHECK (severity IN ('S1','S2','S3','S4')),
    status       TEXT NOT NULL CHECK (status IN ('open','in_progress','blocked','resolved','closed')),
    reporter     TEXT NOT NULL,
    assignee     TEXT,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS comments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    bug_id     TEXT NOT NULL REFERENCES bugs(id),
    author     TEXT NOT NULL,
    body       TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS status_history (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    bug_id     TEXT NOT NULL REFERENCES bugs(id),
    old_status TEXT NOT NULL,
    new_status TEXT NOT NULL,
    reason     TEXT NOT NULL,
    author     TEXT NOT NULL,
    changed_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_bugs_component ON bugs(component);
CREATE INDEX IF NOT EXISTS idx_bugs_severity  ON bugs(severity);
CREATE INDEX IF NOT EXISTS idx_bugs_status    ON bugs(status);
"""


def triage_score(severity: str, component: str, age_days: int, status: str) -> int:
    """Deterministic triage ranking. Higher means "look at this sooner".

    severity dominates, component adds a critical-path boost, age adds a small
    capped nudge so stale bugs surface, and work already in progress is damped
    so the queue points at untouched bugs.
    """
    score = SEVERITY_WEIGHT.get(severity, 0)
    score += CRITICAL_PATH.get(component, 0)
    score += min(age_days, 30)
    if status == "in_progress":
        score -= 150
    elif status == "blocked":
        score -= 40
    elif status in ("resolved", "closed"):
        # Large enough that finished work always sorts below any live bug,
        # however severe it was. Max live score is S1 + critical path + age cap.
        score -= 5000
    return score
