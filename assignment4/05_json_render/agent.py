"""The scripted agent, emitting json-render style RFC 6902 patches.

The agent never sends a whole spec. It sends patches that build one from
nothing and then change it in place. The four modes are four vocabularies:

  static       only `replace` on the props of a skeleton the CLIENT owns
  declarative  add elements from the catalog and link them into parents
  open_ended   one HtmlArtifact under a bare Stack
  mixed        the declarative build plus one HtmlArtifact
"""
from __future__ import annotations

import copy

import data
from security import sandboxed

BARS = [{"label": f"{o['hour']}h", "value": o["pct"]} for o in data.OCCUPANCY]

# Static mode: this skeleton belongs to the client (page/app.js and
# terminal.py both start from it). The agent may only fill props.
SKELETON = {"root": "page", "elements": {
    "page": {"type": "Stack", "props": {"direction": "column"},
             "children": ["metrics", "chart", "rooms"]},
    "metrics": {"type": "Stack", "props": {"direction": "row"}, "children": ["m0", "m1", "m2"]},
    "m0": {"type": "Metric", "props": {"label": "-", "value": "-"}},
    "m1": {"type": "Metric", "props": {"label": "-", "value": "-"}},
    "m2": {"type": "Metric", "props": {"label": "-", "value": "-"}},
    "chart": {"type": "BarChart", "props": {"bars": []}},
    "rooms": {"type": "RoomTable", "props": {"rooms": []}},
}}


def elements(mixed: bool) -> list[tuple[str, str, dict]]:
    """(parent, id, element) in emission order."""
    out = [
        ("page", "title", {"type": "Heading", "props": {"text": "Study rooms - json-render"}}),
        ("page", "metrics", {"type": "Stack", "props": {"direction": "row"}, "children": []}),
        *[("metrics", f"m{i}", {"type": "Metric", "props": m}) for i, m in enumerate(data.metrics())],
        ("page", "chart", {"type": "BarChart", "props": {"title": "Occupancy by hour", "bars": BARS}}),
        ("page", "rooms", {"type": "RoomTable", "props": {"rooms": data.ROOMS}}),
        ("page", "form", {"type": "BookingForm", "props": {
            "rooms": [r["id"] for r in data.ROOMS if r["available"]], "slots": data.SLOTS}}),
        ("page", "confirm", {"type": "Button", "props": {
            "label": "Confirm booking", "action": {"name": "confirm_booking"}}}),
    ]
    if mixed:
        out.insert(6, ("page", "floor", {"type": "HtmlArtifact", "props": {
            "title": "Floor map (generated)", "html": sandboxed(floor_map())}}))
    return out


def floor_map() -> str:
    cells = "".join(
        f"<g transform='translate({20 + (i % 3) * 110},{20 + (i // 3) * 70})'>"
        f"<rect width='100' height='58' rx='8' fill='{'#cfe8d4' if r['available'] else '#f1d3cf'}'"
        f" stroke='#555' data-room='{r['id']}' class='room'/>"
        f"<text x='50' y='34' text-anchor='middle' font-size='12'>{r['id']}</text></g>"
        for i, r in enumerate(data.ROOMS))
    return ("<!doctype html><html><head><meta charset='utf-8'><style>body{margin:0;font:13px system-ui}"
            " text{pointer-events:none} .room{cursor:pointer}</style></head><body>"
            f"<svg viewBox='0 0 360 170' width='100%' style='max-width:420px;display:block;margin:auto'>{cells}</svg>"
            "<script>document.querySelectorAll('.room').forEach(function(r){r.addEventListener('click',"
            "function(){parent.postMessage({type:'book',room:r.dataset.room,slot:'14:00-15:00'},'*');});});"
            "</script></body></html>")


BOOKED: set[str] = set()          # open-ended mode has no structured state to patch


def open_page(note: str = "") -> str:
    free = lambda r: r["available"] and r["id"] not in BOOKED
    items = "".join(f"<div class='r {'f' if free(r) else 'b'}'>{r['id']}<small>{r['capacity']} seats</small>"
                    + (f"<button data-room='{r['id']}'>book</button>" if free(r) else "") + "</div>"
                    for r in data.ROOMS)
    return sandboxed(
        "<!doctype html><html><head><meta charset='utf-8'><style>body{font:14px system-ui;margin:0;"
        "padding:14px;background:#111;color:#eee}.g{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}"
        ".r{padding:16px;border-radius:12px;background:#333;display:flex;flex-direction:column;gap:6px}"
        ".f{background:#1f5f3a}.b{background:#6b2323}button{margin-top:4px}</style></head><body>"
        f"<h2>Room grid (agent-written)</h2>{note}<div class='g'>{items}</div><script>"
        "document.querySelectorAll('button').forEach(function(b){b.onclick=function(){parent.postMessage("
        "{type:'book',room:b.dataset.room,slot:'14:00-15:00'},'*');};});</script></body></html>")


def build(mode: str) -> list[dict]:
    """The patch stream for the first render."""
    if mode == "static":
        ops = [{"op": "replace", "path": f"/elements/m{i}/props", "value": m}
               for i, m in enumerate(data.metrics())]
        ops.append({"op": "replace", "path": "/elements/chart/props",
                    "value": {"title": "Occupancy by hour", "bars": BARS}})
        ops.append({"op": "replace", "path": "/elements/rooms/props", "value": {"rooms": data.ROOMS}})
        return ops
    ops = [{"op": "add", "path": "/root", "value": "page"},
           {"op": "add", "path": "/elements", "value": {}},
           {"op": "add", "path": "/elements/page",
            "value": {"type": "Stack", "props": {"direction": "column"}, "children": []}}]
    if mode == "open_ended":
        BOOKED.clear()
        return ops + [{"op": "add", "path": "/elements/html", "value": {
            "type": "HtmlArtifact", "props": {"title": "Agent-written page", "html": open_page()}}},
            {"op": "add", "path": "/elements/page/children/-", "value": "html"}]
    for parent, eid, el in elements(mode == "mixed"):
        ops.append({"op": "add", "path": f"/elements/{eid}", "value": el})
        ops.append({"op": "add", "path": f"/elements/{parent}/children/-", "value": eid})
    return ops


def act(mode: str, spec: dict, name: str, params: dict) -> list[dict]:
    """An action from either renderer. Answer with patches to the live spec."""
    if name != "confirm_booking":
        return []
    if mode == "open_ended":
        # Nothing structured to patch: the only way to change what is on screen
        # is to re-send the whole region. That is the open-ended cost.
        room_id, slot = params.get("room"), params.get("slot") or data.SLOTS[1]
        res = data.book(room_id, slot)
        if res["ok"]:
            BOOKED.add(room_id)
        note = f"<p style='color:#8fd18f'>{res['message']}</p>"
        return [{"op": "replace", "path": "/elements/html/props/html", "value": open_page(note)}]
    room_id, slot = params.get("room"), params.get("slot") or data.SLOTS[1]
    els = spec.get("elements", {})
    rooms = els.get("rooms", {}).get("props", {}).get("rooms", [])
    idx = next((i for i, r in enumerate(rooms) if r["id"] == room_id), None)
    if idx is None or not rooms[idx]["available"]:
        msg, tone, ops = f"{room_id} is not free.", "error", []
    else:
        res = data.book(room_id, slot)
        msg, tone = res["message"], "success"
        free = sum(r["available"] for r in rooms) - 1
        ops = [{"op": "replace", "path": f"/elements/rooms/props/rooms/{idx}/available", "value": False},
               {"op": "replace", "path": f"/elements/rooms/props/rooms/{idx}/next_free",
                "value": slot.split("-")[1]},
               {"op": "replace", "path": "/elements/m0/props/value", "value": f"{free} / {len(rooms)}"}]
        if "form" in els:
            left = [r["id"] for i, r in enumerate(rooms) if r["available"] and i != idx]
            ops.append({"op": "replace", "path": "/elements/form/props/rooms", "value": left})
    if mode in ("declarative", "mixed"):
        if "result" in els:
            ops.append({"op": "replace", "path": "/elements/result/props", "value": {"text": msg, "tone": tone}})
        else:
            ops += [{"op": "add", "path": "/elements/result", "value": {"type": "Text", "props": {"text": msg, "tone": tone}}},
                    {"op": "add", "path": "/elements/page/children/1", "value": "result"}]
    return ops


def empty(mode: str) -> dict:
    return copy.deepcopy(SKELETON) if mode == "static" else {}
