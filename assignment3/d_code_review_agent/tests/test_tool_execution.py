"""Drives the real FunctionTools through a real agent, with only the model
stubbed, so the diff and the exit_loop handshake are exercised for real."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import AsyncGenerator

import pytest
from google.adk.agents import LlmAgent
from google.adk.runners import InMemoryRunner
from google.genai import types

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from code_review.tools import SANDBOX_ROOT  # noqa: E402

CLEAN = '''"""Tidy."""


def add(a, b):
    """Add."""
    return a + b
'''


def make_tool_calling_model(steps: list[dict]):
    from google.adk.models.base_llm import BaseLlm
    from google.adk.models.llm_response import LlmResponse

    class _Scripted(BaseLlm):
        model: str = "gemini-scripted-tools"

        def __init__(self, **kw):
            super().__init__(**kw)
            object.__setattr__(self, "_steps", list(steps))
            object.__setattr__(self, "_i", 0)

        @classmethod
        def supported_models(cls) -> list[str]:
            return [r"gemini-scripted-.*"]

        async def generate_content_async(
            self, llm_request, stream: bool = False
        ) -> AsyncGenerator:
            i = self._i
            object.__setattr__(self, "_i", i + 1)
            step = self._steps[i] if i < len(self._steps) else {"text": "done"}
            if "call" in step:
                name, args = step["call"]
                part = types.Part(
                    function_call=types.FunctionCall(name=name, args=args)
                )
            else:
                part = types.Part(text=step["text"])
            yield LlmResponse(content=types.Content(role="model", parts=[part]))

    return _Scripted()


async def _run(agent, text, app, state=None):
    """Run one agent standalone.

    `state` seeds session state. The fixer reads {review_findings}, which the
    reviewer writes upstream in the real pipeline; running it in isolation
    without seeding that key raises KeyError, which is correct behaviour and
    not something to paper over in the agent.
    """
    runner = InMemoryRunner(agent=agent, app_name=app)
    s = await runner.session_service.create_session(
        app_name=app, user_id="u", state=state or {}
    )
    msg = types.Content(role="user", parts=[types.Part(text=text)])
    events = []
    async for ev in runner.run_async(user_id="u", session_id=s.id, new_message=msg):
        events.append(ev)
    return events


def _results(events):
    out = []
    for ev in events:
        for p in (ev.content.parts if ev.content else []) or []:
            if p.function_response:
                out.append((p.function_response.name, p.function_response.response))
    return out


@pytest.fixture
def scratch_file():
    p = SANDBOX_ROOT / "samples" / "_tmp_agent_patch.py"
    p.write_text("import os,sys\ndef add( a,b ):\n    return a+b\n", encoding="utf-8")
    yield p
    p.unlink(missing_ok=True)
    p.with_suffix(".fixed.py").unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_reviewer_tools_run_for_real_against_the_buggy_sample():
    from code_review.agent import reviewer_agent

    model = make_tool_calling_model([
        {"call": ("check_style", {"file_path": "samples/buggy_module.py"})},
        {"call": ("measure_complexity", {"file_path": "samples/buggy_module.py"})},
        {"text": "BLOCKER: bare except. MAJOR: complexity."},
    ])
    agent = reviewer_agent.model_copy(update={"model": model})

    events = await _run(agent, "Review samples/buggy_module.py", "rev_tools")
    results = dict(_results(events))

    assert "check_style" in results
    assert results["check_style"]["violation_count"] > 15
    assert any(v["code"] == "E722" for v in results["check_style"]["serious"])

    assert "measure_complexity" in results
    assert "get_discount" in results["measure_complexity"]["over_warn"]


@pytest.mark.asyncio
async def test_fixer_gets_a_real_unified_diff_back_through_the_agent(scratch_file):
    """The whole point of agent D: propose_patch returns a diff the model can
    show the user."""
    from code_review.agent import fixer_agent

    model = make_tool_calling_model([
        {"call": ("propose_patch", {
            "file_path": "samples/_tmp_agent_patch.py",
            "fixed_source": CLEAN,
        })},
        {"text": "Patched; checks pass."},
    ])
    agent = fixer_agent.model_copy(update={"model": model})

    events = await _run(agent, "Fix it", "fix_tools",
                        state={"review_findings": "MINOR: style issues."})
    results = dict(_results(events))

    assert "propose_patch" in results
    r = results["propose_patch"]

    diff = r["unified_diff"]
    assert diff.startswith("---")
    assert "+++ b/_tmp_agent_patch.py" in diff
    assert "@@" in diff
    assert r["patch_parses"] is True
    assert r["checks_pass"] is True
    assert "exit_loop" in r["next_step"]

    # The original is untouched; the candidate went to a sibling file.
    assert scratch_file.read_text(encoding="utf-8").startswith("import os,sys")
    assert scratch_file.with_suffix(".fixed.py").exists()


@pytest.mark.asyncio
async def test_a_failing_patch_tells_the_fixer_to_try_again(scratch_file):
    from code_review.agent import fixer_agent

    model = make_tool_calling_model([
        {"call": ("propose_patch", {
            "file_path": "samples/_tmp_agent_patch.py",
            "fixed_source": ("import os,sys\ndef add( a,b ):\n    x=1\n    return a+b\n"),
        })},
        {"text": "Still failing."},
    ])
    agent = fixer_agent.model_copy(update={"model": model})

    events = await _run(agent, "Fix it", "fix_tools2",
                        state={"review_findings": "MINOR: style issues."})
    r = dict(_results(events))["propose_patch"]

    assert r["patch_parses"] is True
    assert r["api_preserved"] is True
    assert r["checks_pass"] is False
    assert r["style_after"]["violation_count"] > 0
    assert "propose_patch again" in r["next_step"]
