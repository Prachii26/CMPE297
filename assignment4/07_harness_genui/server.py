"""Theme 07 - the browser surface for the stage 15 harness's render_ui tool.

    .\\.venv\\Scripts\\python.exe server.py --mode declarative           # http://127.0.0.1:8007
    .\\.venv\\Scripts\\python.exe server.py --mode mixed --prompt "Give me an interactive room picker"
    .\\.venv\\Scripts\\python.exe harness\\main.py --mode declarative --web   # REPL + browser

The harness (harness/main.py) attaches this module with `attach()`. From then
on every spec render_ui accepts is pushed to the browser over SSE, alongside
the terminal surface. A button or a click inside the sandboxed HtmlArtifact
comes back through POST /action and becomes the next user turn of the SAME
harness loop -- one agent, two surfaces.
"""
from __future__ import annotations

import asyncio
import json
import sys
import threading
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE / "harness"))
import render_ui as genui  # noqa: E402

STATE = {"spec": None, "mode": None, "version": 0, "reply": ""}
TURN = {"fn": None}
TURN_LOCK = threading.Lock()
app = FastAPI(title="theme 07 - harness GenUI web surface")


class WebSurface:
    name = "web"

    def show(self, spec: dict, mode: str) -> None:
        STATE.update(spec=spec, mode=mode, version=STATE["version"] + 1)


def attach(turn_fn, port: int = 8007) -> None:
    """Called by harness/main.py --web: add the surface and start serving."""
    TURN["fn"] = turn_fn
    if not any(isinstance(s, WebSurface) for s in genui.SURFACES):
        genui.SURFACES.append(WebSurface())
    import uvicorn
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    threading.Thread(target=uvicorn.Server(config).run, daemon=True).start()


def serve_forever() -> None:
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass


@app.get("/")
def index():
    return FileResponse(HERE / "page" / "index.html")


@app.get("/app.js")
def app_js():
    return FileResponse(HERE / "page" / "app.js", media_type="text/javascript")


@app.get("/config")
def config():
    return {"mode": genui.MODE, "sandbox": genui.SANDBOX, "csp": genui.CSP,
            "modes": ["static", "declarative", "open_ended", "mixed"]}


@app.get("/events")
async def events(once: bool = False):
    async def gen():
        seen = 0
        while True:
            if STATE["version"] > seen and STATE["spec"] is not None:
                seen = STATE["version"]
                yield f"data: {json.dumps({k: STATE[k] for k in ('spec', 'mode', 'version', 'reply')})}\n\n"
                if once:
                    return
            await asyncio.sleep(0.15)
    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


class Action(BaseModel):
    name: str
    params: dict = {}


@app.post("/action")
async def action(a: Action):
    if TURN["fn"] is None:
        return {"ok": False, "reply": "no harness attached"}
    text = (f"Book {a.params.get('room')} for {a.params.get('slot', '14:00-15:00')}"
            if a.name in ("confirm_booking", "book") else f"The user pressed {a.name}")

    def turn():
        with TURN_LOCK:                       # one turn at a time through the loop
            return TURN["fn"](text)
    reply = await run_in_threadpool(turn)
    STATE["reply"] = reply
    return {"ok": True, "user_turn": text, "reply": reply}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["static", "declarative", "open_ended", "mixed"], default="declarative")
    ap.add_argument("--port", default="8007")
    ap.add_argument("--prompt", default="Show me the study-room dashboard")
    a = ap.parse_args()
    sys.modules["server"] = sys.modules["__main__"]   # main.py's `import server` must get THIS module
    import main as harness_main
    harness_main.main(["--mode", a.mode, "--web", "--port", a.port, "--prompt", a.prompt])
