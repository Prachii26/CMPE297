"""Tests for the DDG-backed web_search tool. The network is stubbed, so these
run offline and spend nothing."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from lead_research import search_tool  # noqa: E402
from lead_research.search_tool import web_search  # noqa: E402


class FakeDDGS:
    """Stands in for ddgs.DDGS as a context manager."""

    rows: list[dict] = []
    raises: Exception | None = None
    calls: list[tuple[str, int]] = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def text(self, query, max_results=5):
        FakeDDGS.calls.append((query, max_results))
        if FakeDDGS.raises is not None:
            raise FakeDDGS.raises
        return list(FakeDDGS.rows)


@pytest.fixture(autouse=True)
def fast_and_stubbed(monkeypatch):
    """No real network, no real sleeping."""
    FakeDDGS.rows, FakeDDGS.raises, FakeDDGS.calls = [], None, []
    monkeypatch.setattr(search_tool, "_MIN_GAP_SECONDS", 0.0)
    monkeypatch.setattr(search_tool.time, "sleep", lambda s: None)

    import types

    fake_module = types.ModuleType("ddgs")
    fake_module.DDGS = FakeDDGS
    monkeypatch.setitem(sys.modules, "ddgs", fake_module)
    yield


def test_results_are_normalised_to_title_url_snippet():
    FakeDDGS.rows = [
        {"title": "Top sensor makers", "href": "https://example.com/a",
         "body": "Nordic industrial IoT companies."},
        {"title": "Registry", "href": "https://example.com/b", "body": "Headcount data."},
    ]
    r = web_search("industrial IoT Nordics", max_results=2)

    assert r["ok"] is True
    assert r["result_count"] == 2
    assert r["results"][0] == {
        "title": "Top sensor makers",
        "url": "https://example.com/a",
        "snippet": "Nordic industrial IoT companies.",
    }
    assert all({"title", "url", "snippet"} == set(x) for x in r["results"])


def test_results_without_a_url_are_dropped():
    """A result with no URL is unusable: the critic rejects unsourced claims."""
    FakeDDGS.rows = [
        {"title": "No link", "href": "", "body": "x"},
        {"title": "Good", "href": "https://example.com/ok", "body": "y"},
        {"title": "Missing key", "body": "z"},
    ]
    r = web_search("q")
    assert r["result_count"] == 1
    assert r["results"][0]["url"] == "https://example.com/ok"


def test_max_results_is_clamped_and_passed_through():
    FakeDDGS.rows = []
    web_search("q", max_results=99)
    assert FakeDDGS.calls[-1][1] == search_tool.MAX_RESULTS_CAP
    web_search("q", max_results=0)
    assert FakeDDGS.calls[-1][1] == 1
    web_search("q", max_results="not a number")  # type: ignore[arg-type]
    assert FakeDDGS.calls[-1][1] == 5


def test_empty_query_is_refused_without_searching():
    assert web_search("")["ok"] is False
    assert web_search("   ")["ok"] is False
    assert FakeDDGS.calls == []


def test_long_snippets_are_truncated():
    FakeDDGS.rows = [{"title": "t", "href": "https://e.com", "body": "x" * 5000}]
    r = web_search("q")
    assert len(r["results"][0]["snippet"]) == search_tool.SNIPPET_CHARS


def test_no_results_is_a_success_with_guidance_not_an_error():
    FakeDDGS.rows = []
    r = web_search("something very obscure")
    assert r["ok"] is True
    assert r["result_count"] == 0
    assert "broader" in r["note"]


def test_transport_failure_is_retried_then_reported_not_raised():
    FakeDDGS.raises = RuntimeError("ratelimit 202")
    r = web_search("q")
    assert r["ok"] is False
    assert "search failed after" in r["error"]
    assert "ratelimit 202" in r["error"]
    assert r["results"] == []
    # It really did retry rather than giving up on the first error.
    assert len(FakeDDGS.calls) == search_tool.RETRY_ATTEMPTS


def test_a_later_attempt_can_succeed():
    calls = {"n": 0}
    rows = [{"title": "t", "href": "https://e.com/x", "body": "b"}]

    class Flaky(FakeDDGS):
        def text(self, query, max_results=5):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("transient")
            return list(rows)

    import types

    m = types.ModuleType("ddgs")
    m.DDGS = Flaky
    sys.modules["ddgs"] = m

    r = web_search("q")
    assert r["ok"] is True
    assert r["results"][0]["url"] == "https://e.com/x"
    assert calls["n"] == 2


def test_missing_dependency_is_reported_as_a_string(monkeypatch):
    monkeypatch.setitem(sys.modules, "ddgs", None)
    r = web_search("q")
    assert r["ok"] is False
    assert "pip install ddgs" in r["error"]


def test_the_tool_tells_the_model_not_to_invent_urls():
    FakeDDGS.rows = [{"title": "t", "href": "https://e.com", "body": "b"}]
    r = web_search("q")
    assert "do not invent URLs" in r["note"]
