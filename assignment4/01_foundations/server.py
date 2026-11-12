"""Theme 01 - the four generation modes with no library at all.

    .\\.venv\\Scripts\\python.exe server.py            # http://127.0.0.1:8001
    .\\.venv\\Scripts\\python.exe server.py --mode declarative --port 8001

One SSE endpoint, four modes. What changes between modes is only what the
scripted agent is allowed to emit and how the page turns that into pixels.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

import agent
import catalog
import data

PAGE = Path(__file__).parent / "page"
MODES = ("static", "declarative", "open_ended", "mixed")
CHUNK = 40                     # characters per streamed chunk of a declarative document

# The security boundary for anything open-ended. The server owns it: the CSP
# is injected into the generated HTML here, whatever the agent wrote, and the
# sandbox token list is sent to the page, which applies it verbatim.
SANDBOX = "allow-scripts"      # no allow-same-origin, no forms, no popups, no top navigation
CSP = ("default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
       "img-src data:; base-uri 'none'; form-action 'none'")

app = FastAPI(title="theme 01 - foundations")
DEFAULT_MODE = {"mode": "static"}


def sandboxed(html: str) -> str:
    meta = f'<meta http-equiv="Content-Security-Policy" content="{CSP}">'
    return html.replace("<head>", "<head>" + meta, 1) if "<head>" in html else meta + html


def sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


async def run(mode: str, shape: str, delay: float):
    yield sse("run_started", {"mode": mode, "prompt": agent.PROMPT})
    if mode == "static":
        for item in agent.static():
            await asyncio.sleep(delay * 8)
            yield sse("component", item)
    elif mode in ("declarative", "mixed"):
        mixed = mode == "mixed"
        shape = "flat" if mixed else shape
        text = agent.declarative_text(shape, mixed)
        yield sse("spec_start", {"shape": shape, "chunk_size": CHUNK, "length": len(text)})
        for i in range(0, len(text), CHUNK):
            await asyncio.sleep(delay)
            yield sse("chunk", {"i": i // CHUNK, "text": text[i:i + CHUNK]})
        spec = json.loads(text)
        errors = catalog.validate_flat(spec, mixed) if shape == "flat" else []
        if shape == "nested":
            import jsonschema
            errors = [e.message[:120] for e in
                      jsonschema.Draft202012Validator(catalog.nested_schema()).iter_errors(spec)]
        yield sse("validation", {"ok": not errors, "errors": errors,
                                 "sandbox": SANDBOX, "csp": CSP})
    elif mode == "open_ended":
        html = agent.open_ended()
        for i in range(0, len(html), CHUNK * 4):
            await asyncio.sleep(delay)
            yield sse("html_chunk", {"bytes": min(i + CHUNK * 4, len(html)), "total": len(html)})
        yield sse("html", {"html": sandboxed(html), "sandbox": SANDBOX, "csp": CSP})
    yield sse("run_finished", {"mode": mode})


@app.get("/")
def index():
    return FileResponse(PAGE / "index.html")


@app.get("/app.js")
def app_js():
    return FileResponse(PAGE / "app.js", media_type="text/javascript")


@app.get("/config")
def config():
    return {"default_mode": DEFAULT_MODE["mode"], "modes": MODES, "sandbox": SANDBOX,
            "csp": CSP}


@app.get("/catalog")
def get_catalog(mixed: bool = False):
    return {"components": sorted(catalog.catalog(mixed)), "flat_schema": catalog.flat_schema(mixed)}


@app.get("/stream")
def stream(mode: str = "static", shape: str = "flat", delay: float = 0.06):
    if mode not in MODES:
        return JSONResponse({"error": f"unknown mode {mode}"}, status_code=400)
    return StreamingResponse(run(mode, shape, delay), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache"})


@app.get("/sandboxed_html")
def sandboxed_html(which: str = "floor_map"):
    """The mixed region's HTML with the CSP already injected."""
    return {"html": sandboxed(agent.floor_map_html()), "sandbox": SANDBOX, "csp": CSP}


class Action(BaseModel):
    action: str
    room: str = ""
    slot: str = ""


@app.post("/action")
def action(a: Action):
    if a.action not in ("confirm_booking", "book"):
        return JSONResponse({"ok": False, "message": f"unknown action {a.action}"}, status_code=400)
    return data.book(a.room, a.slot)


if __name__ == "__main__":
    import uvicorn
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=MODES, default="static",
                    help="mode the page opens in (all four stay selectable)")
    ap.add_argument("--port", type=int, default=8001)
    args = ap.parse_args()
    DEFAULT_MODE["mode"] = args.mode
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")
