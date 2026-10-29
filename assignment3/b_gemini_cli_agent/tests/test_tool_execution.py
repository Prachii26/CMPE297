"""Drives the real tools through a real agent with the model stubbed and the
CLI subprocess faked, so the tool contract is exercised the way ADK will
actually call it (JSON args in, dict out)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import AsyncGenerator

import pytest
from google.adk.runners import InMemoryRunner
from google.genai import types

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from gemini_cli_agent import cli_tool  # noqa: E402


def make_tool_calling_model(steps: list[dict]):
    from google.adk.models.base_llm import BaseLlm
    from google.adk.models.llm_response import LlmResponse

    class _Scripted(BaseLlm):
        model: str = "gemini-scripted-cli"

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


class FakeProc:
    def __init__(self, stdout="", stderr="", returncode=0):
        self._out, self._err, self.returncode = stdout, stderr, returncode
        self.pid = 999

    def communicate(self, timeout=None):
        return self._out, self._err

    def kill(self):
        pass


async def _run(agent, text, app):
    runner = InMemoryRunner(agent=agent, app_name=app)
    s = await runner.session_service.create_session(app_name=app, user_id="u")
    msg = types.Content(role="user", parts=[types.Part(text=text)])
    events = []
    async for ev in runner.run_async(user_id="u", session_id=s.id, new_message=msg):
        events.append(ev)
    return events


def _results(events):
    out = {}
    for ev in events:
        for p in (ev.content.parts if ev.content else []) or []:
            if p.function_response:
                out[p.function_response.name] = p.function_response.response
    return out


@pytest.mark.asyncio
async def test_agent_can_list_the_sandbox_without_touching_the_cli():
    """list_sandbox is the cheap tool; it must work with no CLI at all."""
    from gemini_cli_agent.agent import root_agent

    model = make_tool_calling_model([
        {"call": ("list_sandbox", {"subdir": ""})},
        {"text": "The sandbox holds a taskqueue package."},
    ])
    agent = root_agent.model_copy(update={"model": model})

    results = _results(await _run(agent, "What is in the sandbox?", "cli_list"))
    assert "list_sandbox" in results
    assert results["list_sandbox"]["ok"] is True
    assert "taskqueue" in results["list_sandbox"]["directories"]


@pytest.mark.asyncio
async def test_agent_invokes_the_cli_tool_and_gets_a_structured_result(monkeypatch):
    from gemini_cli_agent.agent import root_agent

    captured = {}

    def fake_popen(argv, **kw):
        captured["argv"] = argv
        captured["cwd"] = kw.get("cwd")
        captured["shell"] = kw.get("shell")
        return FakeProc(stdout="queue.py holds the priority queue; worker.py drains it.")

    monkeypatch.setattr(cli_tool.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(cli_tool, "find_gemini_executable", lambda: "C:/fake/gemini.cmd")

    model = make_tool_calling_model([
        {"call": ("gemini_cli", {
            "prompt": "List every module and say what each does.",
            "cwd": "taskqueue",
        })},
        {"text": "Structured summary follows."},
    ])
    agent = root_agent.model_copy(update={"model": model})

    results = _results(await _run(agent, "Explain taskqueue", "cli_run"))
    r = results["gemini_cli"]

    assert r["ok"] is True
    assert r["folder"] == "taskqueue"
    assert "queue.py" in r["files_visible"]
    assert "priority queue" in r["output"]
    assert r["truncated"] is False

    # And the invocation itself was safe.
    assert captured["shell"] is False
    i = captured["argv"].index("-p")
    assert captured["argv"][i + 1].startswith("List every module")
    assert Path(captured["cwd"]).name == "taskqueue"


@pytest.mark.asyncio
async def test_cli_failure_reaches_the_model_as_data_not_an_exception(monkeypatch):
    """A tool that raises kills the turn; this one must report instead."""
    from gemini_cli_agent.agent import root_agent

    monkeypatch.setattr(cli_tool, "find_gemini_executable", lambda: "C:/fake/gemini.cmd")
    monkeypatch.setattr(
        cli_tool.subprocess,
        "Popen",
        lambda argv, **kw: FakeProc(stderr="auth failed", returncode=55),
    )

    model = make_tool_calling_model([
        {"call": ("gemini_cli", {"prompt": "summarise", "cwd": ""})},
        {"text": "The CLI failed; I cannot answer."},
    ])
    agent = root_agent.model_copy(update={"model": model})

    events = await _run(agent, "Explain", "cli_fail")
    r = _results(events)["gemini_cli"]

    assert r["ok"] is False
    assert "exited 55" in r["error"]
    assert "auth failed" in r["error"]

    # The turn still completed and the model got its chance to respond.
    texts = [
        p.text
        for ev in events
        for p in (ev.content.parts if ev.content else []) or []
        if p.text
    ]
    assert any("cannot answer" in t for t in texts)
