"""Runs the whole pipeline end to end against a scripted fake model, so the
state chain is exercised for real without a single network call."""

from __future__ import annotations

import pytest
from google.adk.runners import InMemoryRunner
from google.genai import types

from tests.conftest import make_scripted_model

SCRIPT = {
    # Keyed on a distinctive phrase from each agent's instruction.
    "B2B lead research planner": (
        "ICP: industrial IoT, Nordics, 200-1000 employees\n"
        "MARKET: query 1; query 2\nFIRMOGRAPHIC: query 3\nSIGNALS: query 4"
    ),
    "MARKET researcher": "Northwind Sensors (https://example.com/northwind)",
    "FIRMOGRAPHIC researcher": "Northwind Sensors ~400 staff (https://example.com/nw-size)",
    "SIGNALS researcher": "Northwind hiring 3 platform engineers (https://example.com/nw-jobs)",
    "assemble and score the lead list": (
        "COMPANY: Northwind Sensors\nFIT_SCORE: 5\nWHY: exact industrial IoT, "
        "Nordics, 400 staff\nSIGNALS: hiring platform engineers\n"
        "SOURCES: https://example.com/northwind"
    ),
    "evidence critic": "APPROVED",
    "write the final lead report": (
        "## Leads\n\n| Company | Fit (1-5) | Why they fit | Buying signals | Sources |\n"
        "|---|---|---|---|---|\n| Northwind Sensors | 5 | Exact ICP match | "
        "Hiring | [src](https://example.com/northwind) |"
    ),
}


def _rebuild_with_fake_model(root, fake):
    """Deep-copy the agent tree and swap every model for the scripted one.

    The copy matters: `root_agent` is a module-level singleton, so mutating it
    in place would leak the fake model into every other test in the session.
    """
    import copy

    from google.adk.tools.agent_tool import AgentTool

    root = copy.deepcopy(root)

    def walk(agent):
        yield agent
        for sub in getattr(agent, "sub_agents", []) or []:
            yield from walk(sub)
        for t in getattr(agent, "tools", []) or []:
            if isinstance(t, AgentTool):
                yield from walk(t.agent)

    for agent in walk(root):
        if hasattr(agent, "model"):
            agent.model = fake
    return root


@pytest.mark.asyncio
async def test_full_pipeline_runs_and_populates_every_state_key():
    from lead_research.agent import root_agent

    fake = make_scripted_model(SCRIPT, default="(unscripted)")
    pipeline = _rebuild_with_fake_model(root_agent, fake)

    runner = InMemoryRunner(agent=pipeline, app_name="leadtest")
    session = await runner.session_service.create_session(
        app_name="leadtest", user_id="u"
    )

    msg = types.Content(
        role="user",
        parts=[
            types.Part(
                text="ICP: industrial IoT, Nordics, 200-1000 employees"
            )
        ],
    )
    authors = []
    async for ev in runner.run_async(
        user_id="u", session_id=session.id, new_message=msg
    ):
        authors.append(ev.author)

    final = await runner.session_service.get_session(
        app_name="leadtest", user_id="u", session_id=session.id
    )
    state = final.state

    # Every stage wrote its key, which means every stage actually ran and the
    # templates downstream of it had something to read.
    for key in (
        "research_plan",
        "research_market",
        "research_firmographic",
        "research_signals",
        "scored_leads",
        "critique",
        "final_report",
    ):
        assert key in state, f"{key} missing; state keys were {sorted(state)}"
        assert state[key].strip(), f"{key} is empty"

    # The stages ran in pipeline order.
    assert "IcpPlanner" in authors
    assert authors.index("IcpPlanner") < authors.index("ReportWriter")

    # All three researchers contributed.
    for name in ("MarketResearcher", "FirmographicResearcher", "SignalResearcher"):
        assert name in authors

    # The final report is the writer's markdown table.
    assert "| Company | Fit (1-5) |" in state["final_report"]


@pytest.mark.asyncio
async def test_parallel_researchers_all_run_within_one_invocation():
    """A ParallelAgent should fan out, not drop siblings."""
    from lead_research.agent import root_agent

    fake = make_scripted_model(SCRIPT, default="(unscripted)")
    pipeline = _rebuild_with_fake_model(root_agent, fake)

    runner = InMemoryRunner(agent=pipeline, app_name="leadtest2")
    session = await runner.session_service.create_session(
        app_name="leadtest2", user_id="u"
    )
    msg = types.Content(role="user", parts=[types.Part(text="ICP: x, y, z")])

    seen = set()
    async for ev in runner.run_async(
        user_id="u", session_id=session.id, new_message=msg
    ):
        seen.add(ev.author)

    assert {
        "MarketResearcher",
        "FirmographicResearcher",
        "SignalResearcher",
    } <= seen
