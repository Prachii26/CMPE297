"""End-to-end test of the real MCP path with only the model stubbed.

Exercises McpToolset -> StdioConnectionParams -> python -m mcp_server.server
-> FastMCP -> SQLite and back, so a wiring fault (wrong cwd, bad tool_filter,
a schema MCP rejects) fails here rather than in front of a live model.

No network, no API key, no quota.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import AsyncGenerator

import pytest
from google.adk.agents import LlmAgent
from google.adk.runners import InMemoryRunner
from google.genai import types

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))


def make_tool_calling_model(steps: list[dict]):
    """Replays a fixed sequence: {"call": (name, args)} or {"text": "..."}."""
    from google.adk.models.base_llm import BaseLlm
    from google.adk.models.llm_response import LlmResponse

    class _Scripted(BaseLlm):
        model: str = "gemini-scripted-mcp"

        def __init__(self, **kw):
            super().__init__(**kw)
            object.__setattr__(self, "_steps", list(steps))
            object.__setattr__(self, "_i", 0)

        @classmethod
        def supported_models(cls) -> list[str]:
            return [r"gemini-scripted-.*"]

        async def generate_content_async(
            self, llm_request, stream: bool = False
        ) -> AsyncGenerator:
            i = self._i
            object.__setattr__(self, "_i", i + 1)
            step = self._steps[i] if i < len(self._steps) else {"text": "done"}
            if "call" in step:
                name, args = step["call"]
                part = types.Part(
                    function_call=types.FunctionCall(name=name, args=args)
                )
            else:
                part = types.Part(text=step["text"])
            yield LlmResponse(content=types.Content(role="model", parts=[part]))

    return _Scripted()


async def _run(agent, text, app="mcp_c"):
    runner = InMemoryRunner(agent=agent, app_name=app)
    session = await runner.session_service.create_session(app_name=app, user_id="u")
    msg = types.Content(role="user", parts=[types.Part(text=text)])
    events = []
    async for ev in runner.run_async(
        user_id="u", session_id=session.id, new_message=msg
    ):
        events.append(ev)
    return events


def _tool_results(events):
    out = []
    for ev in events:
        for p in (ev.content.parts if ev.content else []) or []:
            if p.function_response:
                out.append((p.function_response.name, p.function_response.response))
    return out


@pytest.mark.asyncio
async def test_mcp_toolset_lists_our_four_tools_over_stdio():
    from bug_assistant.agent import build_toolset

    toolset = build_toolset()
    try:
        names = sorted(t.name for t in await toolset.get_tools())
        assert names == ["add_comment", "get_bug", "search_bugs", "set_status"]
    finally:
        await toolset.close()


@pytest.mark.asyncio
async def test_triage_ordering_survives_the_mcp_round_trip():
    from bug_assistant.agent import build_toolset

    model = make_tool_calling_model([
        {"call": ("search_bugs", {"status": "open", "limit": 5})},
        {"text": "Here is the triage queue."},
    ])
    toolset = build_toolset()
    agent = LlmAgent(name="bug_test", model=model, instruction="t", tools=[toolset])

    try:
        events = await _run(agent, "What should I pick up first?")
    finally:
        await toolset.close()

    results = _tool_results(events)
    assert results, "no tool result came back over MCP"
    payload = results[0][1].get("structuredContent") or results[0][1]

    bugs = payload["bugs"]
    assert bugs, "expected open bugs"
    # Still a queue after the round trip: scores non-increasing, S1 on a
    # critical-path component first.
    scores = [b["triage_score"] for b in bugs]
    assert scores == sorted(scores, reverse=True)
    assert bugs[0]["severity"] == "S1"
    assert bugs[0]["critical_path"] is True
    assert "by_severity" in payload["triage_summary"]


@pytest.mark.asyncio
async def test_set_status_reason_gate_survives_the_mcp_round_trip():
    """A thin reason must be refused through MCP too, and leave the bug alone."""
    from bug_assistant.agent import build_toolset

    model = make_tool_calling_model([
        {"call": ("set_status", {
            "bug_id": "VLT-103", "new_status": "resolved", "reason": "done",
        })},
        {"call": ("get_bug", {"bug_id": "VLT-103"})},
        {"text": "The change was refused."},
    ])
    toolset = build_toolset()
    agent = LlmAgent(name="bug_test2", model=model, instruction="t", tools=[toolset])

    try:
        events = await _run(agent, "Close VLT-103", app="mcp_c2")
    finally:
        await toolset.close()

    results = _tool_results(events)
    assert len(results) >= 2

    refusal = results[0][1].get("structuredContent") or results[0][1]
    assert "error" in refusal
    assert refusal["status_unchanged"] is True

    after = results[1][1].get("structuredContent") or results[1][1]
    assert after["status"] == "open"
    assert after["status_history"] == []
