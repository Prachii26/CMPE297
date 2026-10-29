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

Search backend: the researchers use a `web_search` FunctionTool backed by
DuckDuckGo, not the built-in `google_search`. Gemini's Search grounding is
metered on a quota dimension separate from the model's own and is exhausted on
this key, which stopped the parallel stage dead whichever models were used. See
`search_tool.py` and the README.

A side effect worth noting: `google_search` is a built-in tool that Gemini
refuses to accept alongside function declarations, which is why the critic's
search capability is wrapped in `AgentTool`. A FunctionTool has no such
restriction, so that wrapper is no longer strictly required — it is kept
because it is the composition the assignment asks to demonstrate, and because
it keeps the critic's verification on its own budget.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from google.adk.agents import LlmAgent, LoopAgent, ParallelAgent, SequentialAgent
from google.adk.models.google_llm import Gemini
from google.adk.tools import FunctionTool, exit_loop
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
from .search_tool import web_search

AGENT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = AGENT_DIR.parent
load_dotenv(AGENT_DIR / ".env")
load_dotenv(PROJECT_DIR / ".env")

if not os.environ.get("GOOGLE_API_KEY") and os.environ.get("GEMINI_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "FALSE")

MODEL_NAME = os.environ.get("LEAD_RESEARCH_MODEL", "gemini-3-flash-preview")

# One model per stage.
#
# Free-tier quota is 20 requests/day PER MODEL, so a pipeline this size cannot
# live on one model. Two separate pressures:
#
#   - The three researchers run SIMULTANEOUSLY inside the ParallelAgent, so
#     they must never share a model: three concurrent calls is an instant 429
#     on the per-minute limit as well as the daily one.
#   - The sequential stages do not contend with each other, but they do share
#     the daily budget, so spreading them widens the ceiling for a whole run.
#
# Every stage therefore has its own override. Defaults use the four models that
# had quota when this was last run; `gemini-flash-latest` and
# `gemini-3.5-flash` were exhausted. Check with the probe in the README before
# a demo run, and re-point any stage whose bucket is dry.
PLANNER_MODEL = os.environ.get(
    "LEAD_RESEARCH_PLANNER_MODEL", "gemini-3-flash-preview")
SCORER_MODEL = os.environ.get(
    "LEAD_RESEARCH_SCORER_MODEL", "gemini-3.5-flash-lite")
CRITIC_MODEL = os.environ.get(
    "LEAD_RESEARCH_CRITIC_MODEL", "gemini-3.1-flash-lite")
CRITIC_SEARCH_MODEL = os.environ.get(
    "LEAD_RESEARCH_CRITIC_SEARCH_MODEL", "gemini-flash-lite-latest")
WRITER_MODEL = os.environ.get(
    "LEAD_RESEARCH_WRITER_MODEL", "gemini-3-flash-preview")

RESEARCHER_MODELS = [
    m.strip()
    for m in os.environ.get(
        "LEAD_RESEARCH_RESEARCHER_MODELS",
        "gemini-3.5-flash-lite,gemini-3.1-flash-lite,gemini-flash-lite-latest",
    ).split(",")
    if m.strip()
]

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


# Milliseconds. Without this a model request can hang indefinitely and take the
# whole pipeline with it: a live run went silent for 23 minutes after a single
# request to gemini-flash-lite-latest never returned, with no error anywhere in
# the log. retry_options cannot help, because nothing ever fails. A timeout
# converts the hang into a failure the retry can act on.
REQUEST_TIMEOUT_MS = int(os.environ.get("LEAD_RESEARCH_REQUEST_TIMEOUT_MS", "90000"))


def make_model(model_name: str | None = None) -> Gemini:
    """A fresh model object per agent, with rate-limit retry and a hard
    per-request timeout."""
    return Gemini(
        model=model_name or MODEL_NAME,
        retry_options=RETRY_OPTIONS,
        client_kwargs={"http_options": types.HttpOptions(timeout=REQUEST_TIMEOUT_MS)},
    )


# How many times the scorer/critic pair may iterate. Each iteration costs two
# model calls, so this is the main quota dial.
MAX_CRITIC_LOOPS = int(os.environ.get("LEAD_RESEARCH_MAX_LOOPS", "2"))


# --------------------------------------------------------------------------
# 1. Planner
# --------------------------------------------------------------------------

planner_agent = LlmAgent(
    name="IcpPlanner",
    model=make_model(PLANNER_MODEL),
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


def _researcher(
    name: str, angle: str, focus: str, key: str, model_name: str | None = None
) -> LlmAgent:
    return LlmAgent(
        name=name,
        model=make_model(model_name),
        description=f"Researches the {angle} angle with Google Search.",
        instruction=researcher_instruction(angle, focus),
        tools=[FunctionTool(web_search)],
        output_key=key,
    )


def _researcher_model(i: int) -> str:
    return RESEARCHER_MODELS[i % len(RESEARCHER_MODELS)] if RESEARCHER_MODELS else MODEL_NAME


market_researcher = _researcher(
    "MarketResearcher", "MARKET", MARKET_FOCUS, "research_market", _researcher_model(0)
)
firmographic_researcher = _researcher(
    "FirmographicResearcher", "FIRMOGRAPHIC", FIRMOGRAPHIC_FOCUS,
    "research_firmographic", _researcher_model(1)
)
signal_researcher = _researcher(
    "SignalResearcher", "SIGNALS", SIGNALS_FOCUS, "research_signals",
    _researcher_model(2)
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
    model=make_model(SCORER_MODEL),
    description="Merges research into a lead list and scores each lead 1-5 via the scoring tool.",
    instruction=SCORER_INSTRUCTION,
    tools=[FunctionTool(score_lead_fit)],
    output_key="scored_leads",
)

# The critic's search capability is wrapped rather than built in, because the
# critic also carries exit_loop. See the module docstring.
critic_search_agent = LlmAgent(
    name="CriticSearchAgent",
    model=make_model(CRITIC_SEARCH_MODEL),
    description="Checks whether a specific claim or URL can be found on the web.",
    instruction=(
        "You verify one specific claim or URL with the web_search tool. "
        "Report only what you actually found, and say plainly if you found "
        "nothing."
    ),
    tools=[FunctionTool(web_search)],
)

critic_agent = LlmAgent(
    name="EvidenceCritic",
    model=make_model(CRITIC_MODEL),
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
    model=make_model(WRITER_MODEL),
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
