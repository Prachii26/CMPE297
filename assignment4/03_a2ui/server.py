"""Theme 03 - A2UI: structure and data as two streams.

    .\\.venv\\Scripts\\python.exe server.py            # http://127.0.0.1:8003
    .\\.venv\\Scripts\\python.exe server.py --mode mixed

POST /a2ui/run     body {mode, clientCapabilities: {catalog: [component names]}}
                   -> JSON Lines of A2UI messages, validated against the
                   catalog THE CLIENT ADVERTISED
POST /a2ui/action  body {mode, userAction: {...}} -> JSON Lines that patch
                   the existing surface
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

import a2ui
import agent
from security import CSP, SANDBOX

PAGE = Path(__file__).parent / "page"
MODES = ("static", "declarative", "open_ended", "mixed")
DEFAULT = {"mode": "static"}
app = FastAPI(title="theme 03 - A2UI")


class RunRequest(BaseModel):
    mode: str = "declarative"
    clientCapabilities: dict = {}
    delay: float = 0.08


class ActionRequest(BaseModel):
    mode: str = "declarative"
    userAction: dict
    clientCapabilities: dict = {}
    delay: float = 0.05


def advertised(caps: dict) -> dict:
    """Only components the client advertised AND we know how to describe."""
    names = caps.get("catalog", [])
    known = {**a2ui.CATALOG, **a2ui.HTML_ARTIFACT}
    return {n: known[n] for n in names if n in known}


async def stream(msgs, catalog, delay):
    for m in msgs:
        errors = a2ui.validate_message(m, catalog)
        if errors:     # never send a component the client cannot render
            yield json.dumps({"error": {"rejected": errors}}) + "\n"
            continue
        await asyncio.sleep(delay)
        yield a2ui.jsonl(m)


@app.post("/a2ui/run")
def run(req: RunRequest):
    return StreamingResponse(stream(agent.run(req.mode), advertised(req.clientCapabilities),
                                    req.delay), media_type="application/jsonl")


@app.post("/a2ui/action")
def action(req: ActionRequest):
    msgs = agent.act(req.mode, req.userAction.get("userAction", req.userAction))
    return StreamingResponse(stream(msgs, advertised(req.clientCapabilities), req.delay),
                             media_type="application/jsonl")


@app.get("/config")
def config():
    return {"default_mode": DEFAULT["mode"], "modes": MODES, "sandbox": SANDBOX, "csp": CSP,
            "advertise": {m: sorted(c) for m, c in a2ui.ADVERTISED.items()}}


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
    ap.add_argument("--port", type=int, default=8003)
    a = ap.parse_args()
    DEFAULT["mode"] = a.mode
    uvicorn.run(app, host="127.0.0.1", port=a.port, log_level="warning")
