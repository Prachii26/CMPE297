"""Root agent for the Meeple Market shopping assistant.

All five tools arrive over MCP from the FastMCP server in ../mcp_server, which
McpToolset launches as a stdio subprocess.
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
load_dotenv(AGENT_DIR / ".env")
load_dotenv(PROJECT_DIR / ".env")

if not os.environ.get("GOOGLE_API_KEY") and os.environ.get("GEMINI_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "FALSE")

MODEL_NAME = os.environ.get("SHOP_AGENT_MODEL", "gemini-flash-latest")

RETRY_OPTIONS = types.HttpRetryOptions(
    attempts=8,
    initial_delay=20.0,
    max_delay=75.0,
    exp_base=1.5,
    jitter=0.3,
    http_status_codes=[429, 503, 504],
)

TOOL_NAMES = [
    "search_products",
    "get_product",
    "add_to_cart",
    "place_order",
    "order_status",
]


def build_toolset() -> McpToolset:
    """Start the Meeple Market MCP server over stdio."""
    return McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command=sys.executable,
                args=["-m", "mcp_server.server"],
                cwd=str(PROJECT_DIR),
                env={
                    **os.environ,
                    "PYTHONUNBUFFERED": "1",
                    "PYTHONIOENCODING": "utf-8",
                },
            ),
            timeout=60.0,
        ),
        tool_filter=list(TOOL_NAMES),
    )


root_agent = LlmAgent(
    model=Gemini(model=MODEL_NAME, retry_options=RETRY_OPTIONS),
    name="meeple_market_assistant",
    description=(
        "Board game shop assistant. Searches the catalogue, manages a "
        "per-user cart, places orders, and offers in-stock alternatives "
        "whenever something is unavailable."
    ),
    instruction=AGENT_INSTRUCTION,
    tools=[build_toolset()],
)
