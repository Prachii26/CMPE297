"""Tests for the triage ordering, which is our first change from the upstream
sample. The upstream search returns vector-similarity matches; ours returns a
severity + component ranked queue."""

from __future__ import annotations

from mcp_server.db import triage_score


def test_seed_creates_thirty_bugs(tools):
    result = tools["search_bugs"](limit=50)
    assert result["total_matches"] == 30
    assert result["triage_summary"]["by_severity"] == {
        "S1": 5,
        "S2": 9,
        "S3": 9,
        "S4": 7,
    }


def test_severity_dominates_then_critical_path_component(tools):
    """An S1 on payments must outrank an S1 on maps, and every S1 outranks S2."""
    result = tools["search_bugs"](limit=50)
    bugs = result["bugs"]

    # Scores are non-increasing, i.e. the list really is a queue.
    scores = [b["triage_score"] for b in bugs]
    assert scores == sorted(scores, reverse=True)

    # Every open S1 appears before every open S3/S4.
    first_s3 = next(i for i, b in enumerate(bugs) if b["severity"] == "S3")
    last_s1 = max(i for i, b in enumerate(bugs) if b["severity"] == "S1")
    assert last_s1 < first_s3

    # Critical-path boost is real: same severity, payments beats maps.
    assert triage_score("S2", "payments", 5, "open") > triage_score(
        "S2", "maps", 5, "open"
    )
    # ...and the boost never overcomes a whole severity step.
    assert triage_score("S2", "payments", 30, "open") < triage_score(
        "S1", "maps", 0, "open"
    )


def test_in_progress_is_damped_and_closed_sinks(tools):
    """The queue should point at untouched work, not at what someone owns."""
    assert triage_score("S1", "payments", 5, "in_progress") < triage_score(
        "S1", "payments", 5, "open"
    )
    assert triage_score("S1", "payments", 5, "closed") < triage_score(
        "S4", "maps", 0, "open"
    )

    result = tools["search_bugs"](limit=50)
    statuses = [b["status"] for b in result["bugs"]]
    # Resolved and closed bugs land at the very end of the queue.
    tail = statuses[-3:]
    assert set(tail) <= {"resolved", "closed"}


def test_component_and_severity_filters_combine(tools):
    payments = tools["search_bugs"](component="payments", limit=50)
    assert payments["total_matches"] == 3
    assert {b["component"] for b in payments["bugs"]} == {"payments"}

    s1_only = tools["search_bugs"](severity="s1", limit=50)  # case-insensitive
    assert s1_only["total_matches"] == 5
    assert {b["severity"] for b in s1_only["bugs"]} == {"S1"}

    both = tools["search_bugs"](component="payments", severity="S1", limit=50)
    assert both["total_matches"] == 2

    text = tools["search_bugs"](query="webhook", limit=50)
    assert text["total_matches"] == 1
    assert "webhook" in text["bugs"][0]["title"].lower()


def test_bad_filter_values_are_rejected_not_ignored(tools):
    assert "error" in tools["search_bugs"](severity="S9")
    assert "error" in tools["search_bugs"](status="wontfix")
