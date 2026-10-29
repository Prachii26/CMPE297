"""Wiring tests for agent E."""

from __future__ import annotations

import sys
from pathlib import Path

from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool import McpToolset


def test_root_agent_serves_everything_over_one_mcp_toolset():
    from shop_agent.agent import root_agent

    assert isinstance(root_agent, LlmAgent)
    assert root_agent.name == "meeple_market_assistant"
    assert len(root_agent.tools) == 1
    assert isinstance(root_agent.tools[0], McpToolset)


def test_toolset_exposes_exactly_the_five_required_tools():
    from shop_agent.agent import build_toolset

    assert sorted(build_toolset().tool_filter) == [
        "add_to_cart",
        "get_product",
        "order_status",
        "place_order",
        "search_products",
    ]


def test_stdio_server_is_our_module_with_a_pinned_cwd():
    from shop_agent.agent import PROJECT_DIR, build_toolset

    params = build_toolset()._connection_params.server_params
    assert params.command == sys.executable
    assert params.args == ["-m", "mcp_server.server"]
    assert Path(params.cwd) == PROJECT_DIR
    assert (Path(params.cwd) / "mcp_server" / "server.py").is_file()


def test_model_is_flash_with_rate_limit_retry():
    from shop_agent.agent import root_agent

    assert root_agent.model.model == "gemini-2.5-flash"
    assert 429 in root_agent.model.retry_options.http_status_codes


def test_instruction_teaches_ownership_and_the_alternatives_flow():
    from shop_agent.prompt import AGENT_INSTRUCTION

    lowered = AGENT_INSTRUCTION.lower()
    # Ownership: the model must refuse to act as another user.
    assert "user_id" in AGENT_INSTRUCTION
    assert "refuse" in lowered
    assert "private to" in lowered
    # Alternatives: never a dead end.
    assert "alternatives" in lowered
    assert "never present an alternative as if it were" in lowered
    # And it must confirm before spending money.
    assert "confirm" in lowered


def test_package_exposes_root_agent_for_adk_web():
    import shop_agent

    assert hasattr(shop_agent.agent, "root_agent")
