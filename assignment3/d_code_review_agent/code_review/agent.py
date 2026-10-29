"""Code review agent: review a Python file, then fix it in a capped loop.

    SequentialAgent
      1. reviewer  (LlmAgent, 3 FunctionTools)  -> review_findings
      2. LoopAgent [fixer]  max_iterations=3    -> fix_result
           fixer calls propose_patch, reads checks_pass, calls exit_loop
      3. summariser (LlmAgent)                  -> final_summary
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from google.adk.agents import LlmAgent, LoopAgent, SequentialAgent
from google.adk.models.google_llm import Gemini
from google.adk.tools import FunctionTool, exit_loop
from google.genai import types

from .prompt import FIXER_INSTRUCTION, REVIEWER_INSTRUCTION, SUMMARY_INSTRUCTION
from .tools import (
    check_style,
    measure_complexity,
    parse_python_file,
    propose_patch,
)

AGENT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = AGENT_DIR.parent
load_dotenv(AGENT_DIR / ".env")
load_dotenv(PROJECT_DIR / ".env")

if not os.environ.get("GOOGLE_API_KEY") and os.environ.get("GEMINI_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "FALSE")

MODEL_NAME = os.environ.get("CODE_REVIEW_MODEL", "gemini-2.5-flash")

RETRY_OPTIONS = types.HttpRetryOptions(
    attempts=8,
    initial_delay=20.0,
    max_delay=75.0,
    exp_base=1.5,
    jitter=0.3,
    http_status_codes=[429, 503, 504],
)

MAX_FIX_ATTEMPTS = int(os.environ.get("CODE_REVIEW_MAX_FIX_ATTEMPTS", "3"))


def make_model() -> Gemini:
    return Gemini(model=MODEL_NAME, retry_options=RETRY_OPTIONS)


reviewer_agent = LlmAgent(
    name="CodeReviewer",
    model=make_model(),
    description="Reviews a Python file on disk and reports findings by severity.",
    instruction=REVIEWER_INSTRUCTION,
    tools=[
        FunctionTool(parse_python_file),
        FunctionTool(check_style),
        FunctionTool(measure_complexity),
    ],
    output_key="review_findings",
)

fixer_agent = LlmAgent(
    name="CodeFixer",
    model=make_model(),
    description=(
        "Proposes a patch, gets a unified diff and re-run checks back, and "
        "exits the loop once the checks pass."
    ),
    instruction=FIXER_INSTRUCTION,
    tools=[FunctionTool(propose_patch), exit_loop],
    output_key="fix_result",
)

fix_loop = LoopAgent(
    name="FixLoop",
    description="Re-patches until the checks pass or the attempt cap is reached.",
    max_iterations=MAX_FIX_ATTEMPTS,
    sub_agents=[fixer_agent],
)

summariser_agent = LlmAgent(
    name="ReviewSummariser",
    model=make_model(),
    description="Writes the final verdict and shows the unified diff.",
    instruction=SUMMARY_INSTRUCTION,
    output_key="final_summary",
)


root_agent = SequentialAgent(
    name="code_review_pipeline",
    description=(
        "Reviews a Python file given its path: AST structure, PEP 8 style and "
        "cyclomatic complexity, then fixes it in a capped loop and emits a "
        "unified diff of the patch."
    ),
    sub_agents=[reviewer_agent, fix_loop, summariser_agent],
)
