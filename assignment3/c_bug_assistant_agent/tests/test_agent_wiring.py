"""Tests that the ADK agent is wired the way `adk web` expects, without
constructing a model client or making any network call."""

from __future__ import annotations

import sys
from pathlib import Path

from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool import McpToolset


def test_root_agent_is_an_llmagent_on_flash_with_one_mcp_toolset():
    from bug_assistant.agent import root_agent

    assert isinstance(root_agent, LlmAgent)
    assert root_agent.model.model == "gemini-3-flash-preview"
    assert 429 in root_agent.model.retry_options.http_status_codes
    assert root_agent.name == "voltloop_bug_assistant"

    # All capability arrives over MCP; the agent declares no local tools.
    assert len(root_agent.tools) == 1
    assert isinstance(root_agent.tools[0], McpToolset)


def test_package_exposes_root_agent_for_adk_web():
    """`adk web` imports the package and looks for `root_agent`."""
    import bug_assistant

    assert hasattr(bug_assistant, "agent")
    assert hasattr(bug_assistant.agent, "root_agent")


def test_stdio_connection_launches_our_server_with_a_pinned_cwd():
    from bug_assistant.agent import PROJECT_DIR, build_toolset

    toolset = build_toolset()
    params = toolset._connection_params.server_params

    assert params.command == sys.executable
    assert params.args == ["-m", "mcp_server.server"]
    # cwd must be the project folder so the server's relative DB path resolves.
    assert Path(params.cwd) == PROJECT_DIR
    assert (Path(params.cwd) / "mcp_server" / "server.py").is_file()


def test_toolset_is_filtered_to_our_four_tools():
    from bug_assistant.agent import build_toolset

    toolset = build_toolset()
    assert sorted(toolset.tool_filter) == [
        "add_comment",
        "get_bug",
        "search_bugs",
        "set_status",
    ]


def test_instruction_states_the_reason_requirement():
    """The reason gate is enforced server side; the prompt must also teach it,
    otherwise the model wastes a turn discovering the rejection."""
    from bug_assistant.prompt import AGENT_INSTRUCTION

    lowered = AGENT_INSTRUCTION.lower()
    assert "reason" in lowered
    assert "15 characters" in lowered
    assert "never invent a reason" in lowered
    # Triage policy must be stated, since the score is computed server side.
    assert "critical-path" in lowered or "critical path" in lowered
