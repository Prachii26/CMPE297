"""The scripted agent, emitting A2UI messages.

STRUCTURE (surfaceUpdate) and DATA (dataModelUpdate) are separate streams of
lines. The surface's components point at data paths, so the agent can change
a number on screen by sending only data -- and change the layout by sending
only the components that changed.
"""
from __future__ import annotations

import copy

import data
from a2ui import to_contents
from security import sandboxed

SID = "rooms"


def L(s):            # BoundValue helpers
    return {"literalString": s}


def P(path):
    return {"path": path}


def initial_data() -> dict:
    return {"metrics": data.metrics(), "occupancy": data.OCCUPANCY,
            "rooms": copy.deepcopy(data.ROOMS),
            "freeRooms": [r["id"] for r in data.ROOMS if r["available"]],
            "slots": data.SLOTS, "form": {"room": "LIB-201", "slot": data.SLOTS[1]}}


def comp(cid, ctype, **props):
    return {"id": cid, "component": {ctype: props}}


def components(mixed: bool) -> list[dict]:
    root_children = ["title", "metricsRow", "chart", "table", "form", "confirm"]
    if mixed:
        root_children.insert(3, "floor")
    out = [
        comp("root", "Column", children={"explicitList": root_children}),
        comp("title", "Text", text=L("Study rooms - A2UI surface"), usageHint="h1"),
        comp("metricsRow", "Row", children={"explicitList": ["m0", "m1", "m2"]}),
        *[comp(f"m{i}", "MetricCard", label=P(f"/metrics/{i}/label"), value=P(f"/metrics/{i}/value"))
          for i in range(3)],
        comp("chart", "OccupancyChart", series=P("/occupancy")),
        comp("table", "RoomTable", rows=P("/rooms")),
        comp("form", "BookingForm", rooms=P("/freeRooms"), slots=P("/slots"),
             roomPath="/form/room", slotPath="/form/slot"),
        comp("confirm", "Button", label=L("Confirm booking"),
             action={"name": "confirm_booking",
                     "context": [{"key": "room", "value": P("/form/room")},
                                 {"key": "slot", "value": P("/form/slot")}]}),
    ]
    if mixed:
        out.append(comp("floor", "HtmlArtifact", title=L("Floor map (generated HTML)"),
                        html=L(sandboxed(floor_map()))))
    return out


def floor_map() -> str:
    cells = "".join(
        f"<g transform='translate({20 + (i % 3) * 110},{20 + (i // 3) * 70})'>"
        f"<rect width='100' height='58' rx='8' fill='{'#cfe8d4' if r['available'] else '#f1d3cf'}'"
        f" stroke='#555' data-room='{r['id']}' class='room'/>"
        f"<text x='50' y='34' text-anchor='middle' font-size='12'>{r['id']}</text></g>"
        for i, r in enumerate(data.ROOMS))
    return ("<!doctype html><html><head><meta charset='utf-8'><style>body{margin:0;font:13px "
            "system-ui} text{pointer-events:none} .room{cursor:pointer}</style></head><body>"
            f"<svg viewBox='0 0 360 170' width='100%' style='max-width:420px;display:block;margin:auto'>{cells}</svg>"
            "<script>document.querySelectorAll('.room').forEach(function(r){r.addEventListener('click',"
            "function(){parent.postMessage({type:'book',room:r.dataset.room,slot:'14:00-15:00'},'*');});});"
            "</script></body></html>")


def open_page(note: str = "") -> str:
    rows = "".join(f"<li>{r['name']} - {'free' if r['available'] else 'busy until ' + r['next_free']}"
                   + (f" <button data-room='{r['id']}'>Book</button>" if r["available"] else "")
                   + "</li>" for r in STATE["rooms"])
    return sandboxed(
        "<!doctype html><html><head><meta charset='utf-8'><style>body{font:15px Georgia,serif;"
        "padding:14px;background:#fffaf0} li{margin:6px 0} button{margin-left:8px}</style></head>"
        f"<body><h2>Rooms, as the agent chose to draw them</h2>{note}<ul>{rows}</ul><script>"
        "document.querySelectorAll('button').forEach(function(b){b.onclick=function(){"
        "parent.postMessage({type:'book',room:b.dataset.room,slot:'14:00-15:00'},'*');};});"
        "</script></body></html>")


STATE: dict = {}


def run(mode: str) -> list[dict]:
    """Messages for the first render, in order."""
    STATE.clear()
    STATE.update(initial_data())
    first = to_contents(STATE)                 # the first render shows 37 bookings...
    STATE["metrics"][2]["value"] = "38"        # ...and the agent's own model moves with the live update
    if mode == "static":
        # The client owns the surface; the agent may only send data.
        return [
            {"dataModelUpdate": {"surfaceId": "static", "path": "/", "contents": first}},
            {"dataModelUpdate": {"surfaceId": "static", "path": "/metrics/2",
                                 "contents": to_contents({"label": "Bookings today", "value": "38"})}},
        ]
    if mode == "open_ended":
        return [
            {"surfaceUpdate": {"surfaceId": SID, "components": [
                comp("root", "HtmlArtifact", title=L("Agent-written page"), html=L(open_page()))]}},
            {"beginRendering": {"surfaceId": SID, "root": "root"}},
        ]
    msgs = [{"surfaceUpdate": {"surfaceId": SID, "components": [c]}}
            for c in components(mode == "mixed")]
    msgs.append({"dataModelUpdate": {"surfaceId": SID, "path": "/", "contents": first}})
    msgs.append({"beginRendering": {"surfaceId": SID, "root": "root"}})
    # structure untouched, one number changes: data streams on its own
    msgs.append({"dataModelUpdate": {"surfaceId": SID, "path": "/metrics/2",
                                     "contents": to_contents({"label": "Bookings today",
                                                              "value": "38"})}})
    return msgs


def act(mode: str, action: dict) -> list[dict]:
    """A userAction came back. Patch the existing surface: send only the data
    that changed and only the components that changed."""
    if not STATE:
        STATE.update(initial_data())
    ctx = action.get("context", {})
    room_id, slot = ctx.get("room"), ctx.get("slot") or data.SLOTS[1]
    idx = next((i for i, r in enumerate(STATE["rooms"]) if r["id"] == room_id), None)
    sid = "static" if mode == "static" else SID
    if idx is None or not STATE["rooms"][idx]["available"]:
        msg = f"{room_id} is not free."
        result = {"ok": False}
    else:
        result = data.book(room_id, slot)
        msg = result["message"]
        STATE["rooms"][idx].update(available=False, next_free=slot.split("-")[1])
        STATE["freeRooms"] = [r["id"] for r in STATE["rooms"] if r["available"]]
        free = len(STATE["freeRooms"])
        STATE["metrics"][0]["value"] = f"{free} / {len(STATE['rooms'])}"
        if STATE["freeRooms"]:
            STATE["form"]["room"] = STATE["freeRooms"][0]   # keep the form pointing at a free room
    # data that changed, merged at the root of the data model
    out = [{"dataModelUpdate": {"surfaceId": sid, "path": "/",
                                "contents": to_contents({"rooms": STATE["rooms"],
                                                         "metrics": STATE["metrics"],
                                                         "freeRooms": STATE["freeRooms"],
                                                         "form": STATE["form"],
                                                         "lastResult": msg})}}]
    if mode == "open_ended":
        # the only advertised component is HtmlArtifact: the region is re-sent whole
        out.append({"surfaceUpdate": {"surfaceId": SID, "components": [
            comp("root", "HtmlArtifact", title=L("Agent-written page"),
                 html=L(open_page(f"<p><b>{msg}</b></p>")))]}})
    elif mode in ("declarative", "mixed"):
        children = ["title", "result", "metricsRow", "chart", "table", "form", "confirm"]
        if mode == "mixed":
            children.insert(4, "floor")
        out.append({"surfaceUpdate": {"surfaceId": SID, "components": [
            comp("result", "Text", text=P("/lastResult"),
                 usageHint="success" if result.get("ok") else "body"),
            comp("root", "Column", children={"explicitList": children})]}})
    return out
