"""Fixtures for agent A. Nothing here touches the network."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import AsyncGenerator

import pytest

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))


@pytest.fixture(autouse=True)
def no_credentials(monkeypatch):
    """Strip keys so an accidental real call fails loudly instead of billing."""
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)


class ScriptedLlm:
    """A stand-in for a Gemini model that replays canned responses.

    Subclasses BaseLlm at runtime (imported lazily so that collecting this file
    does not depend on import order). Each agent name maps to the text the fake
    model should return for it, which lets a whole pipeline run offline.
    """

    def __init__(self, script: dict[str, str], default: str = "(no script)"):
        self.script = script
        self.default = default
        self.calls: list[str] = []


def make_scripted_model(script: dict[str, str], default: str = "(no script)"):
    """Build a BaseLlm subclass instance that answers from `script`.

    The key is matched against the agent name found in the request's system
    instruction, falling back to call order.
    """
    from google.adk.models.base_llm import BaseLlm
    from google.adk.models.llm_response import LlmResponse
    from google.genai import types

    class _Scripted(BaseLlm):
        # Named gemini-* on purpose: GoogleSearchTool refuses to attach itself
        # to a model whose id does not look like Gemini, and the researchers
        # carry google_search. The stub still makes no network call.
        model: str = "gemini-scripted-test-model"

        # Pydantic model, so recording state lives in a plain class attribute.
        def __init__(self, **kw):
            super().__init__(**kw)
            object.__setattr__(self, "_script", dict(script))
            object.__setattr__(self, "_default", default)
            object.__setattr__(self, "_calls", [])

        @property
        def calls(self):
            return self._calls

        @classmethod
        def supported_models(cls) -> list[str]:
            return [r"gemini-scripted-.*"]

        async def generate_content_async(
            self, llm_request, stream: bool = False
        ) -> AsyncGenerator:
            si = (llm_request.config.system_instruction or "") if llm_request.config else ""
            matched = self._default
            for key, text in self._script.items():
                if key in si:
                    matched = text
                    break
            self._calls.append(si[:80])
            yield LlmResponse(
                content=types.Content(
                    role="model", parts=[types.Part(text=matched)]
                )
            )

    return _Scripted()
