"""An LlmAgent that answers questions about a code folder via the Gemini CLI."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from google.adk.tools import FunctionTool
from google.genai import types

from .cli_tool import gemini_cli, list_sandbox
from .prompt import AGENT_INSTRUCTION

AGENT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = AGENT_DIR.parent
load_dotenv(AGENT_DIR / ".env")
load_dotenv(PROJECT_DIR / ".env")

if not os.environ.get("GOOGLE_API_KEY") and os.environ.get("GEMINI_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]
# The CLI subprocess reads GEMINI_API_KEY; the ADK agent reads GOOGLE_API_KEY.
# Keep both populated from whichever one the operator set.
if not os.environ.get("GEMINI_API_KEY") and os.environ.get("GOOGLE_API_KEY"):
    os.environ["GEMINI_API_KEY"] = os.environ["GOOGLE_API_KEY"]
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "FALSE")

MODEL_NAME = os.environ.get("GEMINI_CLI_AGENT_MODEL", "gemini-3.5-flash-lite")

RETRY_OPTIONS = types.HttpRetryOptions(
    attempts=8,
    initial_delay=20.0,
    max_delay=75.0,
    exp_base=1.5,
    jitter=0.3,
    http_status_codes=[429, 503, 504],
)


root_agent = LlmAgent(
    model=Gemini(model=MODEL_NAME, retry_options=RETRY_OPTIONS),
    name="codebase_qa_agent",
    description=(
        "Answers questions about a sandboxed code folder by delegating the "
        "reading to the Gemini CLI, and returns a structured summary."
    ),
    instruction=AGENT_INSTRUCTION,
    tools=[FunctionTool(gemini_cli), FunctionTool(list_sandbox)],
)
