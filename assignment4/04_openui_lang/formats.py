"""The same study-room interface in three description formats.

All three carry identical content: a heading, three metric cards, an
occupancy chart over 7 hours, a 6-room table, a booking form with 3 free
rooms and 4 slots, and a confirm button. Only the encoding differs.

  openui_lang()   our line-oriented language (lang.py)
  a2ui_jsonl()    theme 03's A2UI messages: surfaceUpdate components bound
                  to a separate dataModelUpdate, plus beginRendering
  json_render()   theme 05's flat element map with literal props
"""
from __future__ import annotations

import json

import data

FREE = [r["id"] for r in data.ROOMS if r["available"]]
ROOM_KEYS = ("id", "name", "building", "capacity", "available", "next_free")


def _lit(v):
    return json.dumps(v)


def openui_lang(mixed_html: str | None = None) -> str:
    rooms = ", ".join("{" + ", ".join(f"{k}: {_lit(r[k])}" for k in ROOM_KEYS) + "}" for r in data.ROOMS)
    series = ", ".join(f'{{hour: "{o["hour"]}", pct: {o["pct"]}}}' for o in data.OCCUPANCY)
    m = data.metrics()
    children = ["title", "metrics", "chart", "table", "form", "confirm"]
    if mixed_html is not None:
        children.insert(3, "floor")
    lines = [
        f"root = Column([{', '.join(children)}])",
        'title = Text("Study rooms - OpenUI Lang", "h1")',
        "metrics = Row([m0, m1, m2])",
        *[f"m{i} = MetricCard({_lit(x['label'])}, {_lit(x['value'])})" for i, x in enumerate(m)],
        f"chart = OccupancyChart([{series}])",
        f"table = RoomTable([{rooms}])",
        f"form = BookingForm({_lit(FREE)}, {_lit(data.SLOTS)})",
        'confirm = Button("Confirm booking", "confirm_booking")',
    ]
    if mixed_html is not None:
        lines.insert(4, f"floor = HtmlArtifact({_lit(mixed_html)}, \"Floor map (generated)\")")
    return "\n".join(lines) + "\n"


def a2ui_jsonl() -> str:
    L = lambda s: {"literalString": s}
    P = lambda p: {"path": p}
    comps = [
        {"id": "root", "component": {"Column": {"children": {"explicitList":
            ["title", "metrics", "chart", "table", "form", "confirm"]}}}},
        {"id": "title", "component": {"Text": {"text": L("Study rooms - OpenUI Lang"), "usageHint": "h1"}}},
        {"id": "metrics", "component": {"Row": {"children": {"explicitList": ["m0", "m1", "m2"]}}}},
        *[{"id": f"m{i}", "component": {"MetricCard": {"label": P(f"/metrics/{i}/label"),
                                                      "value": P(f"/metrics/{i}/value")}}} for i in range(3)],
        {"id": "chart", "component": {"OccupancyChart": {"series": P("/occupancy")}}},
        {"id": "table", "component": {"RoomTable": {"rows": P("/rooms")}}},
        {"id": "form", "component": {"BookingForm": {"rooms": P("/freeRooms"), "slots": P("/slots")}}},
        {"id": "confirm", "component": {"Button": {"label": L("Confirm booking"),
                                                   "action": {"name": "confirm_booking"}}}},
    ]

    def entries(obj):
        def e(k, v):
            if isinstance(v, bool):
                return {"key": k, "valueBoolean": v}
            if isinstance(v, (int, float)):
                return {"key": k, "valueNumber": v}
            if isinstance(v, str):
                return {"key": k, "valueString": v}
            if isinstance(v, list):
                return {"key": k, "valueMap": [e(str(i), x) for i, x in enumerate(v)]}
            return {"key": k, "valueMap": [e(a, b) for a, b in v.items()]}
        return [e(k, v) for k, v in obj.items()]

    model = {"metrics": data.metrics(), "occupancy": data.OCCUPANCY, "rooms": data.ROOMS,
             "freeRooms": FREE, "slots": data.SLOTS}
    msgs = [{"surfaceUpdate": {"surfaceId": "rooms", "components": comps}},
            {"dataModelUpdate": {"surfaceId": "rooms", "path": "/", "contents": entries(model)}},
            {"beginRendering": {"surfaceId": "rooms", "root": "root"}}]
    return "\n".join(json.dumps(m, separators=(",", ":")) for m in msgs) + "\n"


def json_render() -> str:
    m = data.metrics()
    els = {
        "root": {"type": "Column", "props": {}, "children": ["title", "metrics", "chart", "table", "form", "confirm"]},
        "title": {"type": "Text", "props": {"text": "Study rooms - OpenUI Lang", "usageHint": "h1"}},
        "metrics": {"type": "Row", "props": {}, "children": ["m0", "m1", "m2"]},
        **{f"m{i}": {"type": "MetricCard", "props": x} for i, x in enumerate(m)},
        "chart": {"type": "OccupancyChart", "props": {"series": data.OCCUPANCY}},
        "table": {"type": "RoomTable", "props": {"rows": data.ROOMS}},
        "form": {"type": "BookingForm", "props": {"rooms": FREE, "slots": data.SLOTS}},
        "confirm": {"type": "Button", "props": {"label": "Confirm booking",
                                                "action": {"name": "confirm_booking"}}},
    }
    return json.dumps({"root": "root", "elements": els}, separators=(",", ":"))


def pretty(text: str) -> str:
    """The same JSON with default indentation, as a model often writes it."""
    return "\n".join(json.dumps(json.loads(l), indent=2) for l in text.strip().split("\n"))
