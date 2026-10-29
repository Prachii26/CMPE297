"""Each test gets a throwaway shop database and no credentials."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setenv("SHOP_DB_PATH", str(tmp_path / "test_shop.db"))
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    yield


@pytest.fixture
def shop():
    """The five MCP tools, unwrapped from their FastMCP decorators."""
    from mcp_server import server

    def unwrap(t):
        return getattr(t, "fn", None) or getattr(t, "_fn", None) or t

    return {
        name: unwrap(getattr(server, name))
        for name in (
            "search_products",
            "get_product",
            "add_to_cart",
            "place_order",
            "order_status",
        )
    }
