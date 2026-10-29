"""Test fixtures. Every test runs against a throwaway SQLite file, never a
live model and never the developer's real tracker DB."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    """Point BUG_DB_PATH at a fresh file for each test.

    mcp_server.db.db_path() reads the env var on every call, so redirecting it
    here isolates the test from the seeded DB in the project folder.
    """
    target = tmp_path / "test_bugs.db"
    monkeypatch.setenv("BUG_DB_PATH", str(target))
    # Keep tests away from any real credential, so an accidental network call
    # fails loudly instead of silently billing the user's key.
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    yield target


@pytest.fixture
def tools():
    """The four MCP tool callables, unwrapped from their FastMCP decorators."""
    from mcp_server import server

    def unwrap(tool):
        return getattr(tool, "fn", None) or getattr(tool, "_fn", None) or tool

    return {
        "search_bugs": unwrap(server.search_bugs),
        "get_bug": unwrap(server.get_bug),
        "add_comment": unwrap(server.add_comment),
        "set_status": unwrap(server.set_status),
    }
