"""Tests for the pipeline wiring: agent types, the output_key state chain, the
critic loop cap, and the google_search tool-conflict invariant."""

from __future__ import annotations

from google.adk.agents import LlmAgent, LoopAgent, ParallelAgent, SequentialAgent
from google.adk.tools import FunctionTool
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools.google_search_tool import GoogleSearchTool


def test_pipeline_is_sequential_parallel_loop_writer():
    from lead_research.agent import root_agent

    assert isinstance(root_agent, SequentialAgent)
    kinds = [type(s) for s in root_agent.sub_agents]
    assert kinds == [LlmAgent, ParallelAgent, LoopAgent, LlmAgent]

    planner, parallel, loop, writer = root_agent.sub_agents
    assert planner.name == "IcpPlanner"
    assert len(parallel.sub_agents) == 3
    assert [type(a) for a in loop.sub_agents] == [LlmAgent, LlmAgent]
    assert writer.name == "ReportWriter"


def test_state_flows_planner_to_researchers_to_scorer_to_writer():
    """Every key a downstream prompt reads must be written by an upstream
    output_key, or the template renders empty and the stage runs blind."""
    from lead_research.agent import root_agent

    planner, parallel, loop, writer = root_agent.sub_agents
    scorer, critic = loop.sub_agents

    assert planner.output_key == "research_plan"
    assert sorted(a.output_key for a in parallel.sub_agents) == [
        "research_firmographic",
        "research_market",
        "research_signals",
    ]
    assert scorer.output_key == "scored_leads"
    assert critic.output_key == "critique"
    assert writer.output_key == "final_report"

    # Researchers consume the planner's key.
    for a in parallel.sub_agents:
        assert "{research_plan}" in a.instruction

    # The scorer consumes all three researcher keys plus the critique.
    for key in ("research_market", "research_firmographic", "research_signals"):
        assert "{" + key + "}" in scorer.instruction

    # critique must be OPTIONAL: on the first loop iteration the critic has not
    # run, so a required {critique} would raise KeyError and kill the pipeline.
    assert "{critique?}" in scorer.instruction
    assert "{critique}" not in scorer.instruction

    # The critic reads the scorer's output; the writer reads both.
    assert "{scored_leads}" in critic.instruction
    assert "{scored_leads}" in writer.instruction
    assert "{critique?}" in writer.instruction


def _walk(agent):
    yield agent
    for sub in getattr(agent, "sub_agents", []) or []:
        yield from _walk(sub)
    for t in getattr(agent, "tools", []) or []:
        if isinstance(t, AgentTool):
            yield from _walk(t.agent)


def test_no_agent_uses_the_builtin_google_search_tool():
    """Search grounding is metered on its own quota, separate from the model's,
    and it is exhausted on this key: a plain request succeeds while the same
    request carrying google_search returns 429. The researchers use a
    FunctionTool-backed web_search instead.

    The invariant still matters: ADK 2.13.0 sends the default google_search
    singleton as a raw built-in, which Gemini rejects alongside function
    declarations. If anyone reintroduces it, this fails.
    """
    from lead_research.agent import root_agent

    for agent in _walk(root_agent):
        tools = getattr(agent, "tools", []) or []
        offenders = [t for t in tools if isinstance(t, GoogleSearchTool)]
        assert not offenders, (
            f"{agent.name} uses the built-in google_search; use the "
            "web_search FunctionTool, or hold it as the agent's only tool"
        )


def test_every_researcher_can_search_the_web():
    from lead_research.agent import root_agent

    _, parallel, _, _ = root_agent.sub_agents
    for a in parallel.sub_agents:
        names = [t.name for t in a.tools]
        assert names == ["web_search"], f"{a.name} tools: {names}"


def test_the_critics_search_agent_also_uses_web_search():
    from lead_research.agent import root_agent

    _, _, loop, _ = root_agent.sub_agents
    _, critic = loop.sub_agents
    inner = [t.agent for t in critic.tools if isinstance(t, AgentTool)]
    assert inner, "critic lost its wrapped search agent"
    assert [t.name for t in inner[0].tools] == ["web_search"]


def test_critic_has_exit_loop_and_a_wrapped_search_tool():
    from lead_research.agent import root_agent

    _, _, loop, _ = root_agent.sub_agents
    scorer, critic = loop.sub_agents

    names = []
    for t in critic.tools:
        names.append(getattr(t, "name", None) or getattr(t, "__name__", type(t).__name__))
    assert "exit_loop" in names

    # Its search capability is wrapped, not built in.
    assert any(isinstance(t, AgentTool) for t in critic.tools)
    assert not any(isinstance(t, GoogleSearchTool) for t in critic.tools)

    # The scorer owns the scoring function tool, and only that.
    assert len(scorer.tools) == 1
    assert isinstance(scorer.tools[0], FunctionTool)
    assert scorer.tools[0].name == "score_lead_fit"


def test_loop_is_capped_so_a_stubborn_critic_cannot_spin():
    from lead_research.agent import MAX_CRITIC_LOOPS, root_agent

    _, _, loop, _ = root_agent.sub_agents
    assert isinstance(loop, LoopAgent)
    assert loop.max_iterations == MAX_CRITIC_LOOPS
    assert 1 <= loop.max_iterations <= 3


def test_every_model_carries_rate_limit_retry():
    """The free tier allows 5 calls/minute and this pipeline bursts past that."""
    from lead_research.agent import root_agent

    def walk(agent):
        yield agent
        for sub in getattr(agent, "sub_agents", []) or []:
            yield from walk(sub)
        for t in getattr(agent, "tools", []) or []:
            if isinstance(t, AgentTool):
                yield from walk(t.agent)

    seen = 0
    for agent in walk(root_agent):
        model = getattr(agent, "model", None)
        if model is None or isinstance(model, str):
            continue
        seen += 1
        assert model.retry_options is not None, f"{agent.name} has no retry"
        assert 429 in model.retry_options.http_status_codes
    assert seen >= 6


def test_package_exposes_root_agent_for_adk_web():
    import lead_research

    assert hasattr(lead_research.agent, "root_agent")
