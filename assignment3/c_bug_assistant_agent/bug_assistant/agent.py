"""Root agent for the VoltLoop bug triage assistant.

The agent owns no tools of its own. Everything it can do arrives over MCP from
the FastMCP server in ../mcp_server, launched as a stdio subprocess by
McpToolset. Running the server out of process is the point of the exercise: the
agent and the tracker could live on different machines without code changes.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams
from google.genai import types
from mcp.client.stdio import StdioServerParameters

from .prompt import AGENT_INSTRUCTION

AGENT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = AGENT_DIR.parent

# Load .env from the agent package first, then the agent folder. ADK also does
# this, but the explicit call keeps `pytest` and direct imports working.
load_dotenv(AGENT_DIR / ".env")
load_dotenv(PROJECT_DIR / ".env")

MODEL = os.environ.get("BUG_ASSISTANT_MODEL", "gemini-3-flash-preview")

# The AI Studio free tier rate-limits per minute and per day. Retrying 429 with
# long jittered backoff is what keeps a multi-tool turn from dying mid-way.
RETRY_OPTIONS = types.HttpRetryOptions(
    attempts=8,
    initial_delay=20.0,
    max_delay=75.0,
    exp_base=1.5,
    jitter=0.3,
    http_status_codes=[429, 503, 504],
)


def _map_api_key() -> None:
    """Accept GEMINI_API_KEY as a source for GOOGLE_API_KEY.

    The environment here already has GEMINI_API_KEY; ADK's AI Studio path reads
    GOOGLE_API_KEY. Map one onto the other rather than asking for the key twice.
    """
    if not os.environ.get("GOOGLE_API_KEY") and os.environ.get("GEMINI_API_KEY"):
        os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]
    os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "FALSE")


_map_api_key()


def build_toolset() -> McpToolset:
    """Wire McpToolset to our FastMCP server over stdio.

    The server is started as `python -m mcp_server.server` with cwd pinned to the
    project folder, so its relative DB path resolves the same way whether the
    agent is launched by `adk web` or by a test.
    """
    return McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command=sys.executable,
                args=["-m", "mcp_server.server"],
                cwd=str(PROJECT_DIR),
                env={
                    **os.environ,
                    # Keep the child's stdout clean; MCP speaks JSON-RPC on it.
                    "PYTHONUNBUFFERED": "1",
                    "PYTHONIOENCODING": "utf-8",
                },
            ),
            # The first call pays for interpreter startup plus DB seeding.
            timeout=60.0,
        ),
        tool_filter=["search_bugs", "get_bug", "add_comment", "set_status"],
    )


root_agent = LlmAgent(
    model=Gemini(model=MODEL, retry_options=RETRY_OPTIONS),
    name="voltloop_bug_assistant",
    description=(
        "Triages VoltLoop scooter-platform bugs by severity and component, "
        "reads bug history, records findings, and moves bugs through the "
        "workflow with an audited reason."
    ),
    instruction=AGENT_INSTRUCTION,
    tools=[build_toolset()],
)
