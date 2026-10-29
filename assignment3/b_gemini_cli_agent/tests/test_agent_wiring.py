"""Wiring tests for agent B."""

from __future__ import annotations

import sys
from pathlib import Path

from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))


def test_root_agent_exposes_both_tools():
    from gemini_cli_agent.agent import root_agent

    assert isinstance(root_agent, LlmAgent)
    assert root_agent.name == "codebase_qa_agent"
    names = sorted(t.name for t in root_agent.tools)
    assert names == ["gemini_cli", "list_sandbox"]
    assert all(isinstance(t, FunctionTool) for t in root_agent.tools)


def test_model_is_flash_with_rate_limit_retry():
    from gemini_cli_agent.agent import root_agent

    assert root_agent.model.model == "gemini-flash-latest"
    assert 429 in root_agent.model.retry_options.http_status_codes


def test_instruction_demands_the_structured_summary():
    """Returning a structured summary rather than raw CLI stdout is our change
    from the reference."""
    from gemini_cli_agent.prompt import AGENT_INSTRUCTION

    for section in ("**Folder:**", "**Summary:**", "**Components:**", "**Caveats:**"):
        assert section in AGENT_INSTRUCTION
    # And it must not invent file descriptions when the tool fails.
    assert "ok` is false" in AGENT_INSTRUCTION or "ok` is False" in AGENT_INSTRUCTION
    assert "read-only" in AGENT_INSTRUCTION


def test_package_exposes_root_agent_for_adk_web():
    import gemini_cli_agent

    assert hasattr(gemini_cli_agent.agent, "root_agent")
