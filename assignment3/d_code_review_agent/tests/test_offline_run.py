"""Runs the review -> fix-loop -> summary pipeline end to end against a
scripted fake model. Catches prompt-template and state-chain bugs (a missing
`?` on an optional key raises KeyError and kills the whole run) without
spending any API quota."""

from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import AsyncGenerator

import pytest
from google.adk.runners import InMemoryRunner
from google.genai import types

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))


def make_scripted_model(script: dict[str, str], default: str = "(unscripted)"):
    """A BaseLlm that answers from `script`, keyed on the system instruction."""
    from google.adk.models.base_llm import BaseLlm
    from google.adk.models.llm_response import LlmResponse

    class _Scripted(BaseLlm):
        model: str = "gemini-scripted-test-model"

        def __init__(self, **kw):
            super().__init__(**kw)
            object.__setattr__(self, "_script", dict(script))
            object.__setattr__(self, "_default", default)
            object.__setattr__(self, "_seen", [])

        @property
        def seen(self):
            return self._seen

        @classmethod
        def supported_models(cls) -> list[str]:
            return [r"gemini-scripted-.*"]

        async def generate_content_async(
            self, llm_request, stream: bool = False
        ) -> AsyncGenerator:
            si = (
                (llm_request.config.system_instruction or "")
                if llm_request.config
                else ""
            )
            self._seen.append(si[:60])
            text = self._default
            for key, value in self._script.items():
                if key in si:
                    text = value
                    break
            yield LlmResponse(
                content=types.Content(role="model", parts=[types.Part(text=text)])
            )

    return _Scripted()


SCRIPT = {
    "You are a Python code reviewer": (
        "BLOCKER line 40: bare except swallows real errors.\n"
        "MAJOR line 11: get_discount complexity 16, over the limit.\n"
        "MINOR: 24 PEP 8 violations.\n"
        "Verdict: BLOCKER, 24 style violations, max complexity 16."
    ),
    "You fix the file the reviewer just reviewed": (
        "```diff\n--- a/buggy_module.py\n+++ b/buggy_module.py\n"
        "@@ -1 +1 @@\n-import os, sys\n+import os\n```\nChecks pass."
    ),
    "Write the final summary of this review and fix": (
        "**Verdict** - fixes landed.\n\n**The patch**\n```diff\n"
        "--- a/buggy_module.py\n+++ b/buggy_module.py\n```"
    ),
}


def _with_fake_model(root, fake):
    """Deep-copy the tree so the module-level singleton is not mutated."""
    root = copy.deepcopy(root)

    def walk(a):
        yield a
        for s in getattr(a, "sub_agents", []) or []:
            yield from walk(s)

    for agent in walk(root):
        if hasattr(agent, "model"):
            agent.model = fake
    return root


@pytest.mark.asyncio
async def test_pipeline_runs_without_a_template_keyerror():
    """The fixer reads {review_findings} and the summariser reads {fix_result?}.
    If either key is missing or wrongly marked required, ADK raises KeyError
    and the run dies; this test is what proves it does not."""
    from code_review.agent import root_agent

    fake = make_scripted_model(SCRIPT)
    pipeline = _with_fake_model(root_agent, fake)

    runner = InMemoryRunner(agent=pipeline, app_name="rev")
    session = await runner.session_service.create_session(
        app_name="rev", user_id="u"
    )
    msg = types.Content(
        role="user", parts=[types.Part(text="Review samples/buggy_module.py")]
    )

    authors = []
    async for ev in runner.run_async(
        user_id="u", session_id=session.id, new_message=msg
    ):
        authors.append(ev.author)

    final = await runner.session_service.get_session(
        app_name="rev", user_id="u", session_id=session.id
    )

    assert "CodeReviewer" in authors
    assert "ReviewSummariser" in authors
    assert authors.index("CodeReviewer") < authors.index("ReviewSummariser")

    assert final.state["review_findings"].strip()
    assert final.state["final_summary"].strip()
    assert "```diff" in final.state["final_summary"]


@pytest.mark.asyncio
async def test_fix_loop_stops_at_the_cap_when_the_model_never_exits():
    """A fixer that never calls exit_loop must still terminate."""
    from code_review.agent import MAX_FIX_ATTEMPTS, root_agent

    fake = make_scripted_model(SCRIPT)
    pipeline = _with_fake_model(root_agent, fake)

    runner = InMemoryRunner(agent=pipeline, app_name="rev2")
    session = await runner.session_service.create_session(
        app_name="rev2", user_id="u"
    )
    msg = types.Content(role="user", parts=[types.Part(text="Review it")])

    authors = []
    async for ev in runner.run_async(
        user_id="u", session_id=session.id, new_message=msg
    ):
        authors.append(ev.author)

    # The scripted fixer never calls exit_loop, so the loop should run exactly
    # the capped number of times and then hand off to the summariser.
    assert authors.count("CodeFixer") == MAX_FIX_ATTEMPTS
    assert "ReviewSummariser" in authors
