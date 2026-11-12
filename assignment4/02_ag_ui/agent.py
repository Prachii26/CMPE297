"""The scripted agent, emitting AG-UI events.

A run is a generator of events. The four generation modes differ only in
WHICH events carry the UI -- the transport is identical:

  static       TOOL_CALL show_component {component, props}, three times
  declarative  STATE_SNAPSHOT with an empty surface, then one STATE_DELTA
               per element, building the element map inside shared state
  open_ended   TOOL_CALL render_html {html}
  mixed        the declarative deltas, one of which adds a SandboxedHtml

Every run starts from the client's state (RunAgentInput.state). If that
state says the user requested a booking, the agent acts on it -- that is the
state patch demo: the user changes shared state, the agent sees the change.
"""
from __future__ import annotations

import catalog
import data
from events import apply_patch, event, new_id, text_message, tool_call
from security import sandboxed

FLOOR_MAP = """<!doctype html><html><head><meta charset="utf-8"><style>
body{margin:0;font:13px system-ui} text{pointer-events:none} .room{cursor:pointer}
p{margin:4px 10px}</style></head><body>
<svg viewBox="0 0 360 170" width="100%" style="max-width:420px;display:block;margin:auto">""" + "".join(
    f"<g transform='translate({20 + (i % 3) * 110},{20 + (i // 3) * 70})'>"
    f"<rect width='100' height='58' rx='8' fill='{'#cfe8d4' if r['available'] else '#f1d3cf'}' "
    f"stroke='#555' data-room='{r['id']}' class='room'/>"
    f"<text x='50' y='34' text-anchor='middle' font-size='12'>{r['id']}</text></g>"
    for i, r in enumerate(data.ROOMS)) + """</svg>
<p id="m">Click a green room to request it.</p>
<script>document.querySelectorAll('.room').forEach(function(r){r.addEventListener('click',
function(){parent.postMessage({type:'book',room:r.dataset.room,slot:'14:00-15:00'},'*');
document.getElementById('m').textContent='Requested '+r.dataset.room;});});</script>
</body></html>"""


def domain_state() -> dict:
    return {"rooms": [dict(r) for r in data.ROOMS], "metrics": data.metrics(),
            "booking": None, "ui": None}


def ui_spec(mixed: bool) -> dict:
    els = {
        "page": {"type": "Stack", "props": {"direction": "column"}, "children": []},
        "title": {"type": "Heading", "props": {"text": "Study rooms - live via AG-UI"}},
        "metrics": {"type": "Stack", "props": {"direction": "row"}, "children": []},
        **{f"m{i}": {"type": "MetricCard", "props": m} for i, m in enumerate(data.metrics())},
        "chart": {"type": "OccupancyChart", "props": {"series": data.OCCUPANCY}},
        "rooms": {"type": "RoomTable", "props": {"rooms": data.ROOMS}},
        "form": {"type": "BookingForm", "props": {
            "rooms": [r["id"] for r in data.ROOMS if r["available"]], "slots": data.SLOTS}},
        "confirm": {"type": "Button", "props": {"label": "Request booking",
                                                "action": "request_booking"}},
    }
    order = [("page", "title"), ("page", "metrics"), ("metrics", "m0"), ("metrics", "m1"),
             ("metrics", "m2"), ("page", "chart"), ("page", "rooms"), ("page", "form"),
             ("page", "confirm")]
    if mixed:
        els["floor"] = {"type": "SandboxedHtml",
                        "props": {"title": "Floor map (generated)", "html": sandboxed(FLOOR_MAP)}}
        order.insert(6, ("page", "floor"))
    return {"root": "page", "elements": els, "order": order}


def build_ui(mixed: bool, state: dict):
    """STATE_DELTA ops that grow the surface one element at a time. Each op
    pair adds an element, then links it into its parent, so every
    intermediate state is a valid element map."""
    spec = ui_spec(mixed)
    final = {"root": spec["root"], "elements": spec["elements"]}
    errors = catalog.validate_flat(_finished(final), mixed)
    if errors:
        yield event("RUN_ERROR", message="spec rejected: " + "; ".join(errors))
        return
    root = spec["elements"]["page"]
    yield event("STATE_DELTA", delta=[{"op": "replace", "path": "/ui", "value": {
        "root": "page", "elements": {"page": {**root, "children": []}}}}])
    added = {"page"}
    for parent, child in spec["order"]:
        el = spec["elements"][child]
        ops = []
        if child not in added:
            body = {**el, "children": []} if "children" in el else el
            ops.append({"op": "add", "path": f"/ui/elements/{child}", "value": body})
            added.add(child)
        ops.append({"op": "add", "path": f"/ui/elements/{parent}/children/-", "value": child})
        yield event("STATE_DELTA", delta=ops)


def _finished(spec: dict) -> dict:
    """The element map with every parent's children filled in, for validation."""
    full = {k: dict(v) for k, v in spec["elements"].items()}
    for k in full:
        if "children" in full[k]:
            full[k]["children"] = []
    for parent, child in ui_spec("floor" in spec["elements"])["order"]:
        full[parent]["children"].append(child)
    return {"root": spec["root"], "elements": full}


def run(mode: str, state: dict | None, messages: list[dict], thread_id: str, run_id: str):
    yield event("RUN_STARTED", threadId=thread_id, runId=run_id)
    state = state or domain_state()
    booking = state.get("booking") or {}
    if booking.get("status") == "requested":
        yield from confirm_booking(state, booking)
    else:
        yield event("STATE_SNAPSHOT", snapshot={**domain_state(), "mode": mode})
        if mode == "static":
            yield from text_message("Here are the three prebuilt views, filled in.")
            for comp, props in (("MetricCard", {"metrics": data.metrics()}),
                                ("OccupancyChart", {"series": data.OCCUPANCY}),
                                ("RoomTable", {"rooms": data.ROOMS})):
                yield from tool_call("show_component", {"component": comp, "props": props})
        elif mode in ("declarative", "mixed"):
            yield from text_message("Building the dashboard in shared state, one element at a time.")
            yield from build_ui(mode == "mixed", state)
        elif mode == "open_ended":
            yield from text_message("I wrote this page myself; your page sandboxes it.")
            yield from tool_call("render_html", {"html": sandboxed(FLOOR_MAP.replace(
                "<body>", "<body><h3 style='margin:10px'>Pick a room (agent-written page)</h3>"))})
    yield event("RUN_FINISHED", threadId=thread_id, runId=run_id)


def confirm_booking(state: dict, booking: dict):
    """The agent reads the booking the USER wrote into shared state."""
    room_id, slot = booking.get("room"), booking.get("slot")
    idx = next((i for i, r in enumerate(state["rooms"]) if r["id"] == room_id), None)
    if idx is None or not state["rooms"][idx]["available"]:
        yield from text_message(f"Shared state asks for {room_id}, but it is not free. "
                                "Nothing was booked.")
        yield event("STATE_DELTA", delta=[{"op": "replace", "path": "/booking/status",
                                           "value": "rejected"}])
        return
    result = data.book(room_id, slot)
    yield from text_message(f"I see in shared state that you requested {room_id} for {slot}. "
                            f"{result['message']}")
    free = sum(r["available"] for r in state["rooms"]) - 1
    ops = [
        {"op": "replace", "path": "/booking/status", "value": "confirmed"},
        {"op": "add", "path": "/booking/booking_id", "value": result["booking_id"]},
        {"op": "replace", "path": f"/rooms/{idx}/available", "value": False},
        {"op": "replace", "path": f"/rooms/{idx}/next_free", "value": slot.split("-")[1]},
        {"op": "replace", "path": "/metrics/0/value", "value": f"{free} / {len(state['rooms'])}"},
    ]
    ui = state.get("ui")
    if ui and "rooms" in ui.get("elements", {}):
        ops += [
            {"op": "replace", "path": f"/ui/elements/rooms/props/rooms/{idx}/available", "value": False},
            {"op": "replace", "path": f"/ui/elements/rooms/props/rooms/{idx}/next_free",
             "value": slot.split("-")[1]},
            {"op": "replace", "path": "/ui/elements/m0/props/value",
             "value": f"{free} / {len(state['rooms'])}"},
            {"op": "add", "path": "/ui/elements/done",
             "value": {"type": "Text", "props": {"text": f"Confirmed: {result['booking_id']}"}}},
            {"op": "add", "path": "/ui/elements/page/children/1", "value": "done"},
        ]
    apply_patch(state, ops)        # proves the patch applies to the client's state
    yield event("STATE_DELTA", delta=ops)
