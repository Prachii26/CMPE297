"""NEW in assignment 4: a scripted stand-in for the OpenAI client.

`client.chat.completions.create(model=..., messages=..., tools=...)` returns
an object shaped like the OpenAI SDK's response (choices[0].message.content /
.tool_calls[i].function.name/.arguments, and .usage), so stage 15's
run_loop() drives it without modification. What it "decides" is fixed: for a
request it emits the render_ui call a model would emit, then a short reply
once the tool result comes back. No key, no network.

It also scripts one correction loop: asked for a "carousel", it first emits
a spec with an out-of-catalog component, reads the validator's error from the
tool result, and retries with a valid spec -- validation errors are results.
"""
from __future__ import annotations

import copy
import json
import re
from types import SimpleNamespace

import data
import render_ui as genui

ROOMS = copy.deepcopy(data.ROOMS)


def _metrics():
    free = sum(r["available"] for r in ROOMS)
    return [{"label": "Rooms free now", "value": f"{free} / {len(ROOMS)}"}, *data.metrics()[1:]]


def floor_map_html() -> str:
    cells = "".join(
        f"<g transform='translate({20 + (i % 3) * 110},{20 + (i // 3) * 70})'>"
        f"<rect class='room' data-room='{r['id']}' width='100' height='58' rx='8' stroke='#555' "
        f"fill='{'#cfe8d4' if r['available'] else '#f1d3cf'}'/>"
        f"<text x='50' y='34' text-anchor='middle' font-size='12'>{r['id']}</text></g>"
        for i, r in enumerate(ROOMS))
    return ("<!doctype html><html><head><meta charset='utf-8'><style>body{margin:0;font:13px system-ui}"
            " text{pointer-events:none} .room{cursor:pointer} p{margin:4px 10px}</style></head><body>"
            f"<svg viewBox='0 0 360 170' width='100%' style='max-width:420px;display:block;margin:auto'>{cells}</svg>"
            "<p id='m'>Click a green room to book it for 14:00.</p><script>"
            "document.querySelectorAll('.room').forEach(function(r){r.addEventListener('click',function(){"
            "parent.postMessage({type:'book',room:r.dataset.room,slot:'14:00-15:00'},'*');"
            "document.getElementById('m').textContent='Asked the agent to book '+r.dataset.room;});});"
            "</script></body></html>")


def dashboard(note: str | None = None, tone: str = "normal", interactive: bool = False) -> dict:
    free = [r for r in ROOMS if r["available"]]
    els = {
        "page": {"type": "Stack", "props": {"direction": "column"}, "children": ["title", "metrics", "chart", "rooms"]},
        "title": {"type": "Heading", "props": {"text": "Study rooms - rendered by the stage 15 harness"}},
        "metrics": {"type": "Stack", "props": {"direction": "row"}, "children": ["m0", "m1", "m2"]},
        **{f"m{i}": {"type": "Metric", "props": m} for i, m in enumerate(_metrics())},
        "chart": {"type": "BarChart", "props": {"title": "Occupancy by hour",
                                                "bars": [{"label": f"{o['hour']}h", "value": o["pct"]} for o in data.OCCUPANCY]}},
        "rooms": {"type": "RoomTable", "props": {"rooms": copy.deepcopy(ROOMS)}},
    }
    if free:
        els["book"] = {"type": "Button", "props": {"label": f"Book {free[0]['id']} at 14:00",
                                                   "action": {"name": "confirm_booking",
                                                              "params": {"room": free[0]["id"], "slot": "14:00-15:00"}}}}
        els["page"]["children"].append("book")
    if note:
        els["note"] = {"type": "Heading", "props": {"text": note, "tone": tone}}
        els["page"]["children"].insert(1, "note")
    if interactive:
        els["picker"] = {"type": "HtmlArtifact", "props": {"title": "Pick a room (interactive)",
                                                           "html": floor_map_html()}}
        els["page"]["children"].insert(2, "picker")
    return {"root": "page", "elements": els}


def spec_for(request: str, attempt: int) -> dict:
    mode = genui.MODE
    note, tone = None, "normal"
    m = re.search(r"\bbook\s+([A-Z]+-\d+)", request, re.I)
    if m:
        room = next((r for r in ROOMS if r["id"] == m.group(1).upper()), None)
        if room and room["available"]:
            res = data.book(room["id"], "14:00-15:00")
            room.update(available=False, next_free="15:00")
            note, tone = res["message"], "success"
        else:
            note, tone = f"{m.group(1)} is not free.", "error"
    if mode == "static":
        return {"root": "rooms", "elements": {"rooms": {"type": "RoomTable", "props": {"rooms": copy.deepcopy(ROOMS)}}}}
    if mode == "open_ended":
        return {"root": "page", "elements": {"page": {"type": "HtmlArtifact", "props": {
            "title": "Agent-written page", "html": floor_map_html().replace(
                "<body>", "<body><h2 style='margin:10px;font-family:Georgia'>Rooms, drawn freely</h2>")}}}}
    spec = dashboard(note, tone, interactive=(mode == "mixed" and bool(genui.INTERACTIVE.search(request))))
    if "carousel" in request.lower() and attempt == 0:
        spec["elements"]["photos"] = {"type": "Carousel", "props": {"images": ["a.png", "b.png"]}}
        spec["elements"]["page"]["children"].append("photos")
    return spec


def _usage(messages, out_chars):
    p = sum(len(str(m.get("content") or "")) for m in messages) // 4
    c = out_chars // 4
    return SimpleNamespace(prompt_tokens=p, completion_tokens=c, total_tokens=p + c,
                           prompt_tokens_details=None)


class _Completions:
    def __init__(self):
        self.calls = 0

    def create(self, model, messages, tools=None, **_):
        self.calls += 1
        convo = [m for m in messages if not (m["role"] == "user" and
                                             str(m.get("content", "")).startswith("<system-reminder>"))]
        last_user = max(i for i, m in enumerate(convo) if m["role"] == "user")
        request = convo[last_user]["content"]
        results = [m for m in convo[last_user + 1:] if m["role"] == "tool"]
        if not results or (results[-1]["content"].startswith("error") and len(results) < 2):
            attempt = len(results)
            args = json.dumps({"spec": spec_for(request, attempt)})
            call = SimpleNamespace(id=f"call_{self.calls}", type="function",
                                   function=SimpleNamespace(name="render_ui", arguments=args))
            text = "The validator rejected that; fixing the spec." if attempt else None
            msg = SimpleNamespace(content=text, tool_calls=[call])
            return SimpleNamespace(choices=[SimpleNamespace(message=msg)], usage=_usage(messages, len(args)))
        outcome = results[-1]["content"]
        reply = ("Done - " + outcome) if not outcome.startswith("error") else f"I could not render that: {outcome}"
        msg = SimpleNamespace(content=reply, tool_calls=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)], usage=_usage(messages, len(reply)))


class ScriptedClient:
    """Drop-in for openai.OpenAI(...) as far as run_loop() is concerned."""

    def __init__(self):
        self.chat = SimpleNamespace(completions=_Completions())
