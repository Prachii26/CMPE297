"""Wiring tests for agent D. No model is constructed beyond the config object,
and nothing here reaches the network."""

from __future__ import annotations

import sys
from pathlib import Path

from google.adk.agents import LlmAgent, LoopAgent, SequentialAgent
from google.adk.tools import FunctionTool

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))


def test_pipeline_is_reviewer_then_fix_loop_then_summary():
    from code_review.agent import root_agent

    assert isinstance(root_agent, SequentialAgent)
    reviewer, loop, summariser = root_agent.sub_agents
    assert isinstance(reviewer, LlmAgent) and reviewer.name == "CodeReviewer"
    assert isinstance(loop, LoopAgent)
    assert isinstance(summariser, LlmAgent)


def test_reviewer_holds_exactly_the_three_analysis_tools():
    from code_review.agent import root_agent

    reviewer = root_agent.sub_agents[0]
    names = sorted(t.name for t in reviewer.tools)
    assert names == ["check_style", "measure_complexity", "parse_python_file"]
    assert all(isinstance(t, FunctionTool) for t in reviewer.tools)


def test_fixer_can_patch_and_can_exit_the_loop():
    from code_review.agent import root_agent

    loop = root_agent.sub_agents[1]
    fixer = loop.sub_agents[0]
    names = {
        getattr(t, "name", None) or getattr(t, "__name__", "") for t in fixer.tools
    }
    assert "propose_patch" in names
    assert "exit_loop" in names

    # The fixer must NOT be able to run the analysis tools directly; the whole
    # point is that propose_patch re-runs them, so the model cannot cherry-pick
    # a passing check.
    assert "check_style" not in names
    assert "measure_complexity" not in names


def test_fix_loop_is_capped_at_three_attempts():
    from code_review.agent import MAX_FIX_ATTEMPTS, root_agent

    loop = root_agent.sub_agents[1]
    assert loop.max_iterations == MAX_FIX_ATTEMPTS
    assert MAX_FIX_ATTEMPTS == 3


def test_state_chain_reviewer_to_fixer_to_summary():
    from code_review.agent import root_agent

    reviewer, loop, summariser = root_agent.sub_agents
    fixer = loop.sub_agents[0]

    assert reviewer.output_key == "review_findings"
    assert fixer.output_key == "fix_result"
    assert summariser.output_key == "final_summary"

    # The fixer reads the review; the summariser reads both.
    assert "{review_findings}" in fixer.instruction
    assert "{review_findings}" in summariser.instruction
    # fix_result is optional: if the loop exits on iteration 1 before writing,
    # a required key would raise KeyError.
    assert "{fix_result?}" in summariser.instruction


def test_instructions_demand_a_unified_diff():
    """Emitting the diff is our second change from the reference."""
    from code_review.prompt import FIXER_INSTRUCTION, SUMMARY_INSTRUCTION

    assert "unified diff" in FIXER_INSTRUCTION.lower()
    assert "```diff" in FIXER_INSTRUCTION
    assert "```diff" in SUMMARY_INSTRUCTION


def test_reviewer_instruction_requires_severities_and_a_path():
    from code_review.prompt import REVIEWER_INSTRUCTION

    for sev in ("BLOCKER", "MAJOR", "MINOR"):
        assert sev in REVIEWER_INSTRUCTION
    assert "FILE PATH" in REVIEWER_INSTRUCTION
    # Must not invent tool output.
    assert "did not come from a tool" in REVIEWER_INSTRUCTION


def test_every_model_carries_rate_limit_retry():
    from code_review.agent import root_agent

    def walk(a):
        yield a
        for s in getattr(a, "sub_agents", []) or []:
            yield from walk(s)

    n = 0
    for agent in walk(root_agent):
        m = getattr(agent, "model", None)
        if m is None or isinstance(m, str):
            continue
        n += 1
        assert m.retry_options is not None
        assert 429 in m.retry_options.http_status_codes
    assert n == 3


def test_package_exposes_root_agent_for_adk_web():
    import code_review

    assert hasattr(code_review.agent, "root_agent")
