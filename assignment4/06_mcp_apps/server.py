"""Theme 06 - MCP Apps: another application hosts the surface.

    .\\.venv\\Scripts\\python.exe server.py            # host page at http://127.0.0.1:8006
    .\\.venv\\Scripts\\python.exe server.py --mode open_ended

Two roles in one process, kept apart:
  POST /mcp        the MCP SERVER (JSON-RPC 2.0: initialize, tools/*, resources/*)
  GET  /           a minimal HOST page (page/index.html + page/app.js) that
                   talks to /mcp exactly as a chat client would, and mounts
                   ui:// resources in a sandboxed iframe
"""
from __future__ import annotations

import argparse
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse

import mcp_server

PAGE = Path(__file__).parent / "page"
MODES = ("static", "declarative", "open_ended", "mixed")
DEFAULT = {"mode": "open_ended"}
app = FastAPI(title="theme 06 - MCP Apps")


@app.post("/mcp")
async def mcp(request: Request):
    body = await request.json()
    if isinstance(body, list):
        out = [r for r in (mcp_server.handle(x) for x in body) if r is not None]
        return JSONResponse(out)
    resp = mcp_server.handle(body)
    return JSONResponse(resp) if resp is not None else JSONResponse({}, status_code=202)


@app.post("/reset")
def reset():
    mcp_server.STATE["rooms"] = [dict(r) for r in mcp_server.data.ROOMS]
    return {"ok": True}


@app.get("/config")
def config():
    return {"default_mode": DEFAULT["mode"], "modes": MODES}


@app.get("/")
def index():
    return FileResponse(PAGE / "index.html")


@app.get("/app.js")
def app_js():
    return FileResponse(PAGE / "app.js", media_type="text/javascript")


if __name__ == "__main__":
    import uvicorn
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=MODES, default="open_ended")
    ap.add_argument("--port", type=int, default=8006)
    a = ap.parse_args()
    DEFAULT["mode"] = a.mode
    uvicorn.run(app, host="127.0.0.1", port=a.port, log_level="warning")
