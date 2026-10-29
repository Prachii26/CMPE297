"""Tests for get_bug, add_comment, and the mandatory-reason gate on set_status
(our second change from the upstream sample)."""

from __future__ import annotations

import pytest

from mcp_server.server import MIN_REASON_CHARS

GOOD_REASON = "Reproduced on iOS 17 with a slow NFC read; handing to payments on-call."


def test_get_bug_returns_record_with_history_and_unknown_id_errors(tools):
    bug = tools["get_bug"]("VLT-101")
    assert bug["id"] == "VLT-101"
    assert bug["severity"] == "S1"
    assert bug["component"] == "payments"
    assert bug["critical_path"] is True
    assert bug["comments"] == []
    assert bug["status_history"] == []
    assert "description" in bug and bug["description"]

    # Lookup is case-insensitive on the ID.
    assert tools["get_bug"]("vlt-101")["id"] == "VLT-101"

    missing = tools["get_bug"]("VLT-999")
    assert "error" in missing


def test_add_comment_appends_and_validates(tools):
    r1 = tools["add_comment"]("VLT-101", "nina.rao", "Confirmed two payment intents.")
    assert r1["ok"] is True
    assert r1["comment_count"] == 1

    r2 = tools["add_comment"]("VLT-101", "lee.park", "Patch in review.")
    assert r2["comment_count"] == 2

    bug = tools["get_bug"]("VLT-101")
    assert [c["author"] for c in bug["comments"]] == ["nina.rao", "lee.park"]
    assert bug["comments"][0]["body"] == "Confirmed two payment intents."

    # Empty body and empty author are refused, and nothing is written.
    assert "error" in tools["add_comment"]("VLT-101", "nina.rao", "   ")
    assert "error" in tools["add_comment"]("VLT-101", "", "has a body")
    assert "error" in tools["add_comment"]("VLT-999", "nina.rao", "no such bug")
    assert len(tools["get_bug"]("VLT-101")["comments"]) == 2


@pytest.mark.parametrize("thin_reason", ["", "   ", "done", "fixed it", "ok" * 7])
def test_set_status_refuses_thin_reason_and_leaves_status_untouched(tools, thin_reason):
    before = tools["get_bug"]("VLT-103")["status"]

    result = tools["set_status"]("VLT-103", "resolved", thin_reason)

    assert "error" in result
    assert result.get("status_unchanged") is True
    assert str(MIN_REASON_CHARS) in result["error"]

    after = tools["get_bug"]("VLT-103")
    assert after["status"] == before
    assert after["status_history"] == []


def test_set_status_records_reason_in_audit_trail(tools):
    result = tools["set_status"](
        "VLT-103", "in_progress", GOOD_REASON, author="security-scan"
    )
    assert result["ok"] is True
    assert result["old_status"] == "open"
    assert result["new_status"] == "in_progress"
    assert result["reason_recorded"] == GOOD_REASON

    bug = tools["get_bug"]("VLT-103")
    assert bug["status"] == "in_progress"
    assert len(bug["status_history"]) == 1
    entry = bug["status_history"][0]
    assert entry["old_status"] == "open"
    assert entry["new_status"] == "in_progress"
    assert entry["reason"] == GOOD_REASON
    assert entry["author"] == "security-scan"

    # A second change appends rather than overwriting: the trail is append-only.
    tools["set_status"]("VLT-103", "resolved", "Token rotation shipped in 4.2.1 and verified.")
    history = tools["get_bug"]("VLT-103")["status_history"]
    assert len(history) == 2
    assert [h["new_status"] for h in history] == ["in_progress", "resolved"]


def test_set_status_rejects_unknown_status_and_noop_change(tools):
    bad = tools["set_status"]("VLT-103", "wontfix", GOOD_REASON)
    assert "error" in bad
    assert "wontfix" in bad["error"]

    # VLT-103 is seeded open; setting it open again is a no-op, not an error,
    # and must not write a history row.
    noop = tools["set_status"]("VLT-103", "open", GOOD_REASON)
    assert noop["ok"] is False
    assert noop["status_unchanged"] is True
    assert tools["get_bug"]("VLT-103")["status_history"] == []
