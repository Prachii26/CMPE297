"""End-to-end test of the real MCP path with only the model stubbed.

This exercises McpToolset -> StdioConnectionParams -> python -m mcp_server.server
-> FastMCP -> SQLite and back. Everything except the LLM is the real thing, so
it catches wiring faults (wrong cwd, bad tool_filter, a schema the MCP layer
rejects) that pure unit tests on the tool functions cannot.

No network, no API key, no quota.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import AsyncGenerator

import pytest
from google.adk.runners import InMemoryRunner
from google.genai import types

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))


def make_tool_calling_model(steps: list[dict]):
    """A BaseLlm that replays a fixed sequence of turns.

    Each step is either {"call": (tool_name, args)} or {"text": "..."}.
    """
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


async def _run(agent, text, app="mcp_e2e"):
    runner = InMemoryRunner(agent=agent, app_name=app)
    session = await runner.session_service.create_session(app_name=app, user_id="u")
    msg = types.Content(role="user", parts=[types.Part(text=text)])
    events = []
    async for ev in runner.run_async(
        user_id="u", session_id=session.id, new_message=msg
    ):
        events.append(ev)
    return events


def _tool_results(events) -> list[tuple[str, dict]]:
    out = []
    for ev in events:
        for p in (ev.content.parts if ev.content else []) or []:
            if p.function_response:
                out.append((p.function_response.name, p.function_response.response))
    return out


@pytest.mark.asyncio
async def test_mcp_toolset_lists_our_five_tools_over_stdio():
    """Proves the subprocess actually starts and the handshake completes."""
    from google.adk.agents.readonly_context import ReadonlyContext
    from shop_agent.agent import build_toolset

    toolset = build_toolset()
    try:
        tools = await toolset.get_tools()
        names = sorted(t.name for t in tools)
        assert names == [
            "add_to_cart",
            "get_product",
            "order_status",
            "place_order",
            "search_products",
        ]
    finally:
        await toolset.close()


@pytest.mark.asyncio
async def test_out_of_stock_alternatives_survive_the_mcp_round_trip():
    """The alternatives list has to cross the JSON-RPC boundary intact; this is
    the behaviour the whole agent is built around."""
    from shop_agent.agent import build_toolset
    from google.adk.agents import LlmAgent

    model = make_tool_calling_model([
        {"call": ("get_product", {"user_id": "u_ana", "product_id": "BG-002"})},
        {"text": "Terra Vineyards is out of stock; here are alternatives."},
    ])
    toolset = build_toolset()
    agent = LlmAgent(
        name="shop_test", model=model, instruction="test", tools=[toolset]
    )

    try:
        events = await _run(agent, "Is Terra Vineyards available?")
    finally:
        await toolset.close()

    results = _tool_results(events)
    assert results, "no tool result came back over MCP"
    name, response = results[0]
    assert name == "get_product"

    payload = response.get("structuredContent") or response
    assert payload["stock"] == 0
    assert payload["in_stock"] is False
    alts = payload["alternatives"]
    assert len(alts) >= 1
    assert all(a["stock"] > 0 for a in alts)
    assert alts[0]["id"] == "BG-003"


@pytest.mark.asyncio
async def test_ownership_denial_survives_the_mcp_round_trip():
    """Ben asking for Ana's order must come back as an error through MCP too,
    not as a leaked record."""
    from google.adk.agents import LlmAgent
    from shop_agent.agent import build_toolset

    model = make_tool_calling_model([
        {"call": ("order_status", {"user_id": "u_ben", "order_id": "ORD-1001"})},
        {"text": "That order is not yours."},
    ])
    toolset = build_toolset()
    agent = LlmAgent(
        name="shop_test2", model=model, instruction="test", tools=[toolset]
    )

    try:
        events = await _run(agent, "Show me order ORD-1001", app="mcp_e2e2")
    finally:
        await toolset.close()

    results = _tool_results(events)
    assert results
    payload = results[0][1].get("structuredContent") or results[0][1]
    assert "error" in payload
    assert "status" not in payload
    assert "total" not in payload
