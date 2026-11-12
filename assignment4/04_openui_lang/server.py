"""Theme 04 - OpenUI Lang: a compact, streaming-first UI language.

    .\\.venv\\Scripts\\python.exe server.py            # http://127.0.0.1:8004
    .\\.venv\\Scripts\\python.exe server.py --mode mixed

GET /stream?mode=  the agent's program as plain text, in small chunks. Each
                   statement is validated first; a rejected one is replaced by
                   a `# rejected:` comment line, so the client never parses it.
"""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse

import agent
import lang
from security import CSP, SANDBOX

PAGE = Path(__file__).parent / "page"
MODES = ("static", "declarative", "open_ended", "mixed")
DEFAULT = {"mode": "static"}
CHUNK = 24
app = FastAPI(title="theme 04 - OpenUI Lang")


def checked(mode: str, text: str) -> str:
    cat = lang.MODE_CATALOG[mode]
    out = []
    for line in text.splitlines():
        try:
            stmt = lang.parse_line(line)
        except lang.ParseError as exc:
            out.append(f"# rejected: {exc}")
            continue
        if stmt is None:
            continue
        name, value = stmt
        if mode == "static" and isinstance(value, lang.Node):
            out.append(f"# rejected: static mode allows values only, not components ({name})")
            continue
        prog = lang.Program({name: value})
        errors = [e for e in lang.validate(prog, cat) if "never defined" not in e]  # forward refs are fine
        out.append(f"# rejected: {errors[0]}" if errors else line)
    return "\n".join(out) + "\n"


async def chunks(text: str, delay: float):
    for i in range(0, len(text), CHUNK):
        await asyncio.sleep(delay)
        yield text[i:i + CHUNK]


@app.get("/stream")
def stream(mode: str = "declarative", delay: float = 0.03):
    return StreamingResponse(chunks(checked(mode, agent.program(mode)), delay), media_type="text/plain")


@app.get("/config")
def config():
    return {"default_mode": DEFAULT["mode"], "modes": MODES, "sandbox": SANDBOX, "csp": CSP,
            "catalog": {m: c for m, c in lang.MODE_CATALOG.items()}}


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
    ap.add_argument("--port", type=int, default=8004)
    a = ap.parse_args()
    DEFAULT["mode"] = a.mode
    uvicorn.run(app, host="127.0.0.1", port=a.port, log_level="warning")
