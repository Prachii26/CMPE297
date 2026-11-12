"""Theme 02 - AG-UI: one event protocol, four generation modes.

    .\\.venv\\Scripts\\python.exe server.py            # http://127.0.0.1:8002
    .\\.venv\\Scripts\\python.exe server.py --mode mixed

POST /agent takes an AG-UI RunAgentInput (threadId, runId, state, messages,
forwardedProps) and streams the run back as AG-UI events over SSE.
"""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

import agent
from events import encode, new_id
from security import CSP, SANDBOX

PAGE = Path(__file__).parent / "page"
MODES = ("static", "declarative", "open_ended", "mixed")
DEFAULT = {"mode": "static"}

app = FastAPI(title="theme 02 - AG-UI")


class RunAgentInput(BaseModel):
    threadId: str = Field(default_factory=lambda: new_id("thread"))
    runId: str = Field(default_factory=lambda: new_id("run"))
    state: dict | None = None
    messages: list[dict] = []
    tools: list[dict] = []
    context: list[dict] = []
    forwardedProps: dict = {}


async def stream(inp: RunAgentInput):
    mode = inp.forwardedProps.get("mode", DEFAULT["mode"])
    delay = float(inp.forwardedProps.get("delay", 0.05))
    for ev in agent.run(mode, inp.state, inp.messages, inp.threadId, inp.runId):
        await asyncio.sleep(delay)
        yield encode(ev)


@app.post("/agent")
def run_agent(inp: RunAgentInput):
    return StreamingResponse(stream(inp), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache"})


@app.get("/config")
def config():
    return {"default_mode": DEFAULT["mode"], "modes": MODES, "sandbox": SANDBOX, "csp": CSP}


@app.get("/")
def index():
    return FileResponse(PAGE / "index.html")


@app.get("/app.js")
def app_js():
    return FileResponse(PAGE / "app.js", media_type="text/javascript")


if __name__ == "__main__":
    import uvicorn
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=MODES, default="static")
    ap.add_argument("--port", type=int, default=8002)
    a = ap.parse_args()
    DEFAULT["mode"] = a.mode
    uvicorn.run(app, host="127.0.0.1", port=a.port, log_level="warning")
