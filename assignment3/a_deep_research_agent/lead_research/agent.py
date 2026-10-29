"""Deep research pipeline for B2B lead generation.

Shape:

    SequentialAgent
      1. planner            (LlmAgent)            -> research_plan
      2. ParallelAgent      (3 search-only agents)-> research_market
                                                     research_firmographic
                                                     research_signals
      3. LoopAgent          [scorer, critic]      -> scored_leads / critique
      4. writer             (LlmAgent)            -> final_report

State moves between stages only through `output_key`; each downstream prompt
pulls prior stages in by name with {braces}.

Tool-conflict note (ADK 2.13.0): the three researchers hold `google_search` as
their ONLY tool. The critic needs both a search capability and function tools,
so its search arrives wrapped in `AgentTool`. See README for why.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from google.adk.agents import LlmAgent, LoopAgent, ParallelAgent, SequentialAgent
from google.adk.models.google_llm import Gemini
from google.adk.tools import FunctionTool, exit_loop, google_search
from google.adk.tools.agent_tool import AgentTool
from google.genai import types

from .prompt import (
    CRITIC_INSTRUCTION,
    FIRMOGRAPHIC_FOCUS,
    MARKET_FOCUS,
    PLANNER_INSTRUCTION,
    SCORER_INSTRUCTION,
    SIGNALS_FOCUS,
    WRITER_INSTRUCTION,
    researcher_instruction,
)
from .scoring import score_lead_fit

AGENT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = AGENT_DIR.parent
load_dotenv(AGENT_DIR / ".env")
load_dotenv(PROJECT_DIR / ".env")

if not os.environ.get("GOOGLE_API_KEY") and os.environ.get("GEMINI_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "FALSE")

MODEL_NAME = os.environ.get("LEAD_RESEARCH_MODEL", "gemini-flash-latest")

# This pipeline fires 7-11 model calls per run. The AI Studio free tier allows
# 5 per minute, so without backoff the parallel stage alone would 429. Retry on
# the rate-limit and transient-server codes with long, jittered delays.
RETRY_OPTIONS = types.HttpRetryOptions(
    attempts=8,
    initial_delay=20.0,
    max_delay=75.0,
    exp_base=1.5,
    jitter=0.3,
    http_status_codes=[429, 503, 504],
)


def make_model() -> Gemini:
    """A fresh model object per agent, each with rate-limit retry."""
    return Gemini(model=MODEL_NAME, retry_options=RETRY_OPTIONS)


# How many times the scorer/critic pair may iterate. Each iteration costs two
# model calls, so this is the main quota dial.
MAX_CRITIC_LOOPS = int(os.environ.get("LEAD_RESEARCH_MAX_LOOPS", "2"))


# --------------------------------------------------------------------------
# 1. Planner
# --------------------------------------------------------------------------

planner_agent = LlmAgent(
    name="IcpPlanner",
    model=make_model(),
    description="Turns an ideal customer profile into three parallel search briefs.",
    instruction=PLANNER_INSTRUCTION,
    output_key="research_plan",
)


# --------------------------------------------------------------------------
# 2. Parallel researchers
#
# Each holds google_search and nothing else. Mixing the built-in search tool
# with any function tool on one agent is what breaks; a search-only agent is
# always safe.
# --------------------------------------------------------------------------


def _researcher(name: str, angle: str, focus: str, key: str) -> LlmAgent:
    return LlmAgent(
        name=name,
        model=make_model(),
        description=f"Researches the {angle} angle with Google Search.",
        instruction=researcher_instruction(angle, focus),
        tools=[google_search],
        output_key=key,
    )


market_researcher = _researcher(
    "MarketResearcher", "MARKET", MARKET_FOCUS, "research_market"
)
firmographic_researcher = _researcher(
    "FirmographicResearcher", "FIRMOGRAPHIC", FIRMOGRAPHIC_FOCUS, "research_firmographic"
)
signal_researcher = _researcher(
    "SignalResearcher", "SIGNALS", SIGNALS_FOCUS, "research_signals"
)

parallel_researchers = ParallelAgent(
    name="ParallelResearchers",
    description="Runs the market, firmographic, and buying-signal researchers at once.",
    sub_agents=[market_researcher, firmographic_researcher, signal_researcher],
)


# --------------------------------------------------------------------------
# 3. Critic loop: scorer proposes, critic checks, critic exits when clean
# --------------------------------------------------------------------------

scorer_agent = LlmAgent(
    name="LeadScorer",
    model=make_model(),
    description="Merges research into a lead list and scores each lead 1-5 via the scoring tool.",
    instruction=SCORER_INSTRUCTION,
    tools=[FunctionTool(score_lead_fit)],
    output_key="scored_leads",
)

# The critic's search capability is wrapped rather than built in, because the
# critic also carries exit_loop. See the module docstring.
critic_search_agent = LlmAgent(
    name="CriticSearchAgent",
    model=make_model(),
    description="Checks whether a specific claim or URL can be found on the web.",
    instruction=(
        "You verify one specific claim or URL with Google Search. Report only "
        "what you actually found, and say plainly if you found nothing."
    ),
    tools=[google_search],
)

critic_agent = LlmAgent(
    name="EvidenceCritic",
    model=make_model(),
    description="Rejects leads that are unsourced, implausible, or wrongly scored.",
    instruction=CRITIC_INSTRUCTION,
    tools=[AgentTool(agent=critic_search_agent), exit_loop],
    output_key="critique",
)

critic_loop = LoopAgent(
    name="EvidenceCriticLoop",
    description="Scores leads and re-scores them until the critic approves or the cap is hit.",
    max_iterations=MAX_CRITIC_LOOPS,
    sub_agents=[scorer_agent, critic_agent],
)


# --------------------------------------------------------------------------
# 4. Report writer
# --------------------------------------------------------------------------

report_writer = LlmAgent(
    name="ReportWriter",
    model=make_model(),
    description="Writes the final markdown lead table with fit scores and sources.",
    instruction=WRITER_INSTRUCTION,
    output_key="final_report",
)


root_agent = SequentialAgent(
    name="lead_research_pipeline",
    description=(
        "Takes an ideal customer profile (industry, region, company size) and "
        "returns a sourced markdown lead table where every lead carries a 1-5 "
        "fit score produced by a deterministic scoring tool."
    ),
    sub_agents=[
        planner_agent,
        parallel_researchers,
        critic_loop,
        report_writer,
    ],
)
