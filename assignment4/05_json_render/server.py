"""Theme 05 - json-render: catalog, spec, patches, actions, two renderers.

    .\\.venv\\Scripts\\python.exe server.py            # http://127.0.0.1:8005
    .\\.venv\\Scripts\\python.exe server.py --mode mixed

GET  /spec/stream?mode=   JSON Lines of RFC 6902 patches, each validated
POST /action               {mode, name, params} -> JSON Lines of patches
GET  /catalog?mode=        the catalog: names + per-component prop schemas
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

import agent
import catalog
import spec_stream
from security import CSP, SANDBOX

PAGE = Path(__file__).parent / "page"
MODES = ("static", "declarative", "open_ended", "mixed")
DEFAULT = {"mode": "static"}
app = FastAPI(title="theme 05 - json-render")


async def lines(gen, delay):
    for item in gen:
        await asyncio.sleep(delay)
        yield json.dumps(item) + "\n"


@app.get("/spec/stream")
def stream(mode: str = "declarative", delay: float = 0.05):
    return StreamingResponse(lines(spec_stream.stream(mode), delay), media_type="application/jsonl")


class Action(BaseModel):
    mode: str
    name: str
    params: dict = {}


@app.post("/action")
def action(a: Action):
    return StreamingResponse(lines(spec_stream.action(a.mode, a.name, a.params), 0.03),
                             media_type="application/jsonl")


@app.get("/catalog")
def get_catalog(mode: str = "declarative"):
    cat = catalog.MODE_CATALOG[mode]
    return {"components": sorted(cat), "schemas": {k: v["props"] for k, v in cat.items()}}


@app.get("/config")
def config():
    return {"default_mode": DEFAULT["mode"], "modes": MODES, "sandbox": SANDBOX, "csp": CSP,
            "skeleton": agent.SKELETON}


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
    ap.add_argument("--port", type=int, default=8005)
    a = ap.parse_args()
    DEFAULT["mode"] = a.mode
    uvicorn.run(app, host="127.0.0.1", port=a.port, log_level="warning")
