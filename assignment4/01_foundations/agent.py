"""The scripted agent.

Each function returns exactly what a model would emit for the prompt
"show me the study-room dashboard" in that generation mode. No model is
called: the output is fixed so every run is offline, free and reproducible,
and so the four modes differ ONLY in what the agent is allowed to emit.
"""
from __future__ import annotations

import json

import data

PROMPT = "Show me the study-room dashboard."


# ---------------------------------------------------------------- static
def static() -> list[dict]:
    """Static: the agent only NAMES prebuilt components and fills their
    props. Which components exist, and where they go, is our code."""
    return [
        {"component": "MetricCard", "props": {"metrics": data.metrics()}},
        {"component": "OccupancyChart", "props": {"series": data.OCCUPANCY}},
        {"component": "RoomTable", "props": {"rooms": data.ROOMS}},
    ]


# ----------------------------------------------------------- declarative
def _tree(mixed: bool = False) -> dict:
    """The dashboard as a nested tree (the shape a model writes naturally)."""
    metrics = [{"type": "MetricCard", "props": m} for m in data.metrics()]
    page = [
        {"type": "Heading", "props": {"text": "Study rooms - today"}},
        {"type": "Stack", "props": {"direction": "row"}, "children": metrics},
        {"type": "OccupancyChart", "props": {"series": data.OCCUPANCY}},
        {"type": "RoomTable", "props": {"rooms": data.ROOMS}},
        {"type": "Stack", "props": {"direction": "column"}, "children": [
            {"type": "BookingForm", "props": {
                "rooms": [r["id"] for r in data.ROOMS if r["available"]],
                "slots": data.SLOTS}},
            {"type": "Button", "props": {"label": "Confirm booking",
                                         "action": "confirm_booking"}},
        ]},
    ]
    if mixed:
        page.insert(3, {"type": "SandboxedHtml",
                        "props": {"title": "Floor map (generated)", "html": floor_map_html()}})
    return {"type": "Stack", "props": {"direction": "column"}, "children": page}


def nested(mixed: bool = False) -> dict:
    return _tree(mixed)


def flat(mixed: bool = False) -> dict:
    """The same dashboard as a flat element map: every element has an id,
    parents list child ids, and elements are emitted parent-first. Ids are
    assigned breadth-first, which is the order a streaming emitter uses."""
    elements: dict[str, dict] = {}
    counters: dict[str, int] = {}

    def new_id(t: str) -> str:
        counters[t] = counters.get(t, 0) + 1
        return f"{t[0].lower()}{t[1:]}_{counters[t]}"

    root_id = new_id("Stack")
    queue = [(root_id, _tree(mixed))]
    while queue:
        eid, node = queue.pop(0)
        el = {"type": node["type"], "props": node["props"]}
        if "children" in node:
            kids = [(new_id(c["type"]), c) for c in node["children"]]
            el["children"] = [k for k, _ in kids]
            queue.extend(kids)
        elements[eid] = el
    # Structure first: containers (with their child-id lists) before leaves.
    # Ids make this legal -- order no longer encodes nesting -- and it is the
    # whole reason the flat shape streams well. A nested tree cannot do this.
    ordered = {k: v for k, v in elements.items() if "children" in v}
    ordered.update({k: v for k, v in elements.items() if "children" not in v})
    return {"root": root_id, "elements": ordered}


def declarative_text(shape: str = "flat", mixed: bool = False) -> str:
    spec = flat(mixed) if shape == "flat" else nested(mixed)
    return json.dumps(spec)


# ------------------------------------------------------------ open-ended
def open_ended() -> str:
    """Open-ended: no catalog. The agent writes the whole page."""
    rows = "".join(
        f"<li class='{'free' if r['available'] else 'busy'}'><b>{r['name']}</b>"
        f"<span>{r['capacity']} seats &middot; {'free now' if r['available'] else 'free at ' + r['next_free']}</span>"
        + (f"<button data-room='{r['id']}'>Book 14:00</button>" if r["available"] else "")
        + "</li>" for r in data.ROOMS)
    bars = "".join(f"<div class='bar' style='height:{o['pct']}%' title='{o['hour']}:00 {o['pct']}%'>"
                   f"<em>{o['hour']}</em></div>" for o in data.OCCUPANCY)
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Study rooms</title>
<style>
body{{font-family:Georgia,serif;margin:0;padding:18px;background:#fbf7ef;color:#2b2118}}
h1{{font-size:22px;margin:0 0 4px}} p.sub{{margin:0 0 14px;color:#7a6650}}
.wrap{{display:grid;grid-template-columns:1.2fr 1fr;gap:16px}}
ul{{list-style:none;padding:0;margin:0}} li{{padding:9px 10px;margin-bottom:6px;border-radius:8px;
display:flex;gap:10px;align-items:center;background:#fff;border-left:5px solid #c9b79c}}
li.free{{border-left-color:#4f8a5b}} li span{{color:#7a6650;font-size:13px;flex:1}}
button{{background:#2b2118;color:#fbf7ef;border:0;border-radius:6px;padding:5px 9px;cursor:pointer}}
.chart{{display:flex;align-items:flex-end;gap:6px;height:150px;background:#fff;padding:10px;border-radius:8px}}
.bar{{flex:1;background:linear-gradient(#d98c4a,#a8572a);border-radius:4px 4px 0 0;position:relative}}
.bar em{{position:absolute;bottom:-18px;left:0;right:0;text-align:center;font-size:11px;font-style:normal}}
#msg{{margin-top:22px;font-style:italic}}
</style></head><body>
<h1>Where can I study right now?</h1>
<p class="sub">A page written freely by the agent - no catalog, no schema.</p>
<div class="wrap"><ul>{rows}</ul>
<div><div class="chart">{bars}</div><div id="msg">Peak hour is 14:00.</div></div></div>
<script>
document.querySelectorAll('button[data-room]').forEach(function(b){{
  b.addEventListener('click', function(){{
    parent.postMessage({{type:'book', room:b.dataset.room, slot:'14:00-15:00'}}, '*');
    document.getElementById('msg').textContent = 'Asked the host to book ' + b.dataset.room + '...';
  }});
}});
</script></body></html>"""


def floor_map_html() -> str:
    """Mixed mode's ONE open-ended region: a hand-drawn floor map the
    catalog has no component for."""
    cells = "".join(
        f"<g transform='translate({20 + (i % 3) * 110},{20 + (i // 3) * 70})'>"
        f"<rect width='100' height='58' rx='8' fill='{'#cfe8d4' if r['available'] else '#f1d3cf'}'"
        f" stroke='#555' data-room='{r['id']}' class='room'/>"
        f"<text x='50' y='26' text-anchor='middle' font-size='12'>{r['id']}</text>"
        f"<text x='50' y='44' text-anchor='middle' font-size='10'>{r['capacity']} seats</text></g>"
        for i, r in enumerate(data.ROOMS))
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
body{{margin:0;font:13px system-ui}} text{{pointer-events:none}} .room{{cursor:pointer}} .room:hover{{stroke-width:3}}
p{{margin:4px 10px}}</style></head><body>
<svg viewBox="0 0 360 170" width="100%" style="max-width:420px;display:block;margin:auto">{cells}</svg>
<p id="m">Click a green room to ask the host to book it.</p>
<script>
document.querySelectorAll('.room').forEach(function(r){{
  r.addEventListener('click', function(){{
    parent.postMessage({{type:'book', room:r.dataset.room, slot:'14:00-15:00'}}, '*');
    document.getElementById('m').textContent = 'Requested ' + r.dataset.room;
  }});
}});
</script></body></html>"""
