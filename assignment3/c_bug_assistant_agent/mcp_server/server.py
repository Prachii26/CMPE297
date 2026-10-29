"""FastMCP server exposing the VoltLoop bug tracker over stdio.

Four tools: search_bugs, get_bug, add_comment, set_status.

Two deliberate departures from the upstream sample (see README "Our changes"):

1. search_bugs is a triage queue, not a plain text search. Results are ordered
   by a severity + component score, and the response carries a triage summary
   broken down by severity and component.
2. set_status refuses to act without a substantive reason, and records that
   reason in an append-only status_history row.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any

from fastmcp import FastMCP

from .db import (
    CRITICAL_PATH,
    SEVERITIES,
    STATUSES,
    get_conn,
    triage_score,
)
from .seed import seed

mcp = FastMCP("voltloop-bug-tracker")

MIN_REASON_CHARS = 15


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _age_days(created_at: str) -> int:
    try:
        created = datetime.fromisoformat(created_at)
    except ValueError:
        return 0
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return max((datetime.now(timezone.utc) - created).days, 0)


def _connect() -> sqlite3.Connection:
    """Open the tracker DB, creating and seeding it on first use."""
    conn = get_conn()
    seed(conn)
    return conn


def _row_to_bug(row: sqlite3.Row) -> dict[str, Any]:
    bug = dict(row)
    age = _age_days(bug["created_at"])
    bug["age_days"] = age
    bug["triage_score"] = triage_score(
        bug["severity"], bug["component"], age, bug["status"]
    )
    bug["critical_path"] = bug["component"] in CRITICAL_PATH
    return bug


# --------------------------------------------------------------------------
# Tools
# --------------------------------------------------------------------------


@mcp.tool
def search_bugs(
    query: str = "",
    component: str = "",
    severity: str = "",
    status: str = "",
    limit: int = 10,
) -> dict[str, Any]:
    """Search VoltLoop bugs and return them as a triage-ordered queue.

    Results are sorted by triage score (severity first, then a boost for
    critical-path components like payments and auth, then age), so the first
    result is what an on-call engineer should pick up next.

    Args:
        query: Free text matched against title and description. Empty matches all.
        component: Exact component filter, e.g. payments, auth, dispatch-api,
            iot-firmware, docking-station, mobile-app, maps, billing-batch.
        severity: Exact severity filter, one of S1, S2, S3, S4.
        status: Exact status filter, one of open, in_progress, blocked,
            resolved, closed.
        limit: Maximum bugs to return, 1 to 50.

    Returns:
        A dict with the matched bugs, the total match count, and a triage
        summary counting matches by severity and by component.
    """
    severity = (severity or "").strip().upper()
    status = (status or "").strip().lower()
    component = (component or "").strip().lower()

    if severity and severity not in SEVERITIES:
        return {"error": f"severity must be one of {list(SEVERITIES)}, got {severity!r}"}
    if status and status not in STATUSES:
        return {"error": f"status must be one of {list(STATUSES)}, got {status!r}"}

    limit = max(1, min(int(limit or 10), 50))

    sql = "SELECT * FROM bugs WHERE 1=1"
    params: list[Any] = []
    if query.strip():
        sql += " AND (title LIKE ? OR description LIKE ?)"
        like = f"%{query.strip()}%"
        params += [like, like]
    if component:
        sql += " AND component = ?"
        params.append(component)
    if severity:
        sql += " AND severity = ?"
        params.append(severity)
    if status:
        sql += " AND status = ?"
        params.append(status)

    conn = _connect()
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()

    bugs = [_row_to_bug(r) for r in rows]
    bugs.sort(key=lambda b: (-b["triage_score"], b["id"]))

    by_severity: dict[str, int] = {}
    by_component: dict[str, int] = {}
    for b in bugs:
        by_severity[b["severity"]] = by_severity.get(b["severity"], 0) + 1
        by_component[b["component"]] = by_component.get(b["component"], 0) + 1

    top = bugs[:limit]
    return {
        "total_matches": len(bugs),
        "returned": len(top),
        "triage_summary": {
            "by_severity": dict(sorted(by_severity.items())),
            "by_component": dict(
                sorted(by_component.items(), key=lambda kv: (-kv[1], kv[0]))
            ),
            "critical_path_matches": sum(1 for b in bugs if b["critical_path"]),
        },
        "bugs": [
            {
                "id": b["id"],
                "title": b["title"],
                "component": b["component"],
                "severity": b["severity"],
                "status": b["status"],
                "assignee": b["assignee"],
                "age_days": b["age_days"],
                "triage_score": b["triage_score"],
                "critical_path": b["critical_path"],
            }
            for b in top
        ],
    }


@mcp.tool
def get_bug(bug_id: str) -> dict[str, Any]:
    """Fetch one bug in full, with its comments and status history.

    Args:
        bug_id: The bug identifier, e.g. VLT-101.

    Returns:
        The bug fields plus its comments and its status change history,
        or an error key if no such bug exists.
    """
    bug_id = (bug_id or "").strip().upper()
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM bugs WHERE id = ?", (bug_id,)).fetchone()
        if row is None:
            return {"error": f"no bug with id {bug_id!r}"}
        bug = _row_to_bug(row)
        bug["comments"] = [
            dict(c)
            for c in conn.execute(
                "SELECT author, body, created_at FROM comments "
                "WHERE bug_id = ? ORDER BY id",
                (bug_id,),
            ).fetchall()
        ]
        bug["status_history"] = [
            dict(h)
            for h in conn.execute(
                "SELECT old_status, new_status, reason, author, changed_at "
                "FROM status_history WHERE bug_id = ? ORDER BY id",
                (bug_id,),
            ).fetchall()
        ]
        return bug
    finally:
        conn.close()


@mcp.tool
def add_comment(bug_id: str, author: str, body: str) -> dict[str, Any]:
    """Append a comment to a bug.

    Args:
        bug_id: The bug identifier, e.g. VLT-101.
        author: Who is commenting, e.g. an engineer username.
        body: The comment text. Must not be empty.

    Returns:
        A confirmation with the new comment count, or an error key.
    """
    bug_id = (bug_id or "").strip().upper()
    if not (body or "").strip():
        return {"error": "comment body must not be empty"}
    if not (author or "").strip():
        return {"error": "author must not be empty"}

    conn = _connect()
    try:
        exists = conn.execute("SELECT 1 FROM bugs WHERE id = ?", (bug_id,)).fetchone()
        if exists is None:
            return {"error": f"no bug with id {bug_id!r}"}
        now = _now()
        conn.execute(
            "INSERT INTO comments (bug_id, author, body, created_at) VALUES (?,?,?,?)",
            (bug_id, author.strip(), body.strip(), now),
        )
        conn.execute("UPDATE bugs SET updated_at = ? WHERE id = ?", (now, bug_id))
        conn.commit()
        count = conn.execute(
            "SELECT COUNT(*) FROM comments WHERE bug_id = ?", (bug_id,)
        ).fetchone()[0]
        return {
            "ok": True,
            "bug_id": bug_id,
            "comment_count": count,
            "created_at": now,
        }
    finally:
        conn.close()


@mcp.tool
def set_status(
    bug_id: str, new_status: str, reason: str, author: str = "adk-agent"
) -> dict[str, Any]:
    """Change a bug's status. A substantive reason is mandatory.

    Unlike a plain status setter, this refuses the write unless `reason` is at
    least 15 characters of actual justification. The reason is stored in an
    append-only status_history row so the audit trail explains every change.

    Args:
        bug_id: The bug identifier, e.g. VLT-101.
        new_status: One of open, in_progress, blocked, resolved, closed.
        reason: Why the status is changing. At least 15 characters. Say what
            evidence or action justifies the change, not just "done".
        author: Who is making the change.

    Returns:
        A confirmation including the old and new status, or an error key
        describing why the change was refused.
    """
    bug_id = (bug_id or "").strip().upper()
    new_status = (new_status or "").strip().lower()
    reason = (reason or "").strip()

    if new_status not in STATUSES:
        return {
            "error": f"new_status must be one of {list(STATUSES)}, got {new_status!r}"
        }
    if len(reason) < MIN_REASON_CHARS:
        return {
            "error": (
                f"a reason of at least {MIN_REASON_CHARS} characters is required "
                f"to change status (got {len(reason)}). Explain what evidence or "
                "action justifies this change."
            ),
            "status_unchanged": True,
        }

    conn = _connect()
    try:
        row = conn.execute(
            "SELECT status FROM bugs WHERE id = ?", (bug_id,)
        ).fetchone()
        if row is None:
            return {"error": f"no bug with id {bug_id!r}"}
        old_status = row["status"]
        if old_status == new_status:
            return {
                "ok": False,
                "bug_id": bug_id,
                "message": f"{bug_id} is already {new_status}; nothing changed",
                "status_unchanged": True,
            }
        now = _now()
        conn.execute(
            "UPDATE bugs SET status = ?, updated_at = ? WHERE id = ?",
            (new_status, now, bug_id),
        )
        conn.execute(
            "INSERT INTO status_history (bug_id, old_status, new_status, reason,"
            " author, changed_at) VALUES (?,?,?,?,?,?)",
            (bug_id, old_status, new_status, reason, (author or "adk-agent").strip(), now),
        )
        conn.commit()
        return {
            "ok": True,
            "bug_id": bug_id,
            "old_status": old_status,
            "new_status": new_status,
            "reason_recorded": reason,
            "changed_at": now,
        }
    finally:
        conn.close()


def main() -> None:
    # Make sure the DB exists before the agent sends its first call.
    conn = _connect()
    conn.close()
    mcp.run()


if __name__ == "__main__":
    main()
