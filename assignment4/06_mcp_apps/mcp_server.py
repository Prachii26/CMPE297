"""A minimal MCP server with an MCP App, written by hand (JSON-RPC 2.0).

Methods: initialize, tools/list, tools/call, resources/list, resources/read.

The MCP Apps part (SEP-1865, as used here):
  * the tool `show_rooms_app` declares `_meta.ui.resourceUri = "ui://rooms/dashboard"`
  * `resources/read` on that URI returns HTML with mimeType
    "text/html;profile=mcp-app" and `_meta.ui.csp` saying which origins the
    app needs (none) -- the HOST turns that into a Content-Security-Policy
  * the tool result carries `content` (for the model) and `structuredContent`
    (for the app); the host passes structuredContent into the iframe

The other three tools exist so the SAME host can show the other generation
modes: their results carry a catalog-constrained payload in
structuredContent and no UI resource, and the host renders them itself.
That convention is ours -- MCP Apps does not define a declarative format.
"""
from __future__ import annotations

import agent
import data

PROTOCOL = "2025-06-18"
APP_URI = "ui://rooms/dashboard"
MIXED_URI = "ui://rooms/floor-map"
APP_MIME = "text/html;profile=mcp-app"

TOOLS = [
    {"name": "show_rooms_static", "description": "Show room status as one prebuilt component.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "show_rooms_declarative", "description": "Show a dashboard composed from the host catalog.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "show_rooms_app", "description": "Show the study-room dashboard as an interactive app.",
     "inputSchema": {"type": "object", "properties": {}},
     "_meta": {"ui": {"resourceUri": APP_URI}}},
    {"name": "show_rooms_mixed", "description": "Catalog dashboard with one embedded app region.",
     "inputSchema": {"type": "object", "properties": {}},
     "_meta": {"ui": {"resourceUri": MIXED_URI}}},
    {"name": "book_room", "description": "Book a study room.",
     "inputSchema": {"type": "object", "required": ["room", "slot"],
                     "properties": {"room": {"type": "string"}, "slot": {"type": "string"}}}},
    {"name": "cancel_all_bookings", "description": "Administrative: cancel every booking.",
     "inputSchema": {"type": "object", "properties": {}}},
]
RESOURCES = [
    {"uri": APP_URI, "name": "Study room dashboard", "mimeType": APP_MIME,
     "_meta": {"ui": {"csp": {"connectDomains": [], "resourceDomains": []}, "prefersBorder": True}}},
    {"uri": MIXED_URI, "name": "Floor map region", "mimeType": APP_MIME,
     "_meta": {"ui": {"csp": {"connectDomains": [], "resourceDomains": []}}}},
]

STATE = {"rooms": [dict(r) for r in data.ROOMS]}


def snapshot() -> dict:
    free = sum(r["available"] for r in STATE["rooms"])
    return {"rooms": STATE["rooms"], "occupancy": data.OCCUPANCY,
            "metrics": [{"label": "Rooms free now", "value": f"{free} / {len(STATE['rooms'])}"},
                        *data.metrics()[1:]], "slots": data.SLOTS}


def call_tool(name: str, args: dict) -> dict:
    result = _call_tool(name, args)
    render = (result.get("structuredContent") or {}).get("render")
    if render is not None:
        errors = agent.validate_payload(render)
        if errors:     # never hand a host a payload outside its catalog
            return {"content": [{"type": "text", "text": "payload rejected: " + "; ".join(errors)}],
                    "isError": True}
    return result


def _call_tool(name: str, args: dict) -> dict:
    snap = snapshot()
    free = sum(r["available"] for r in snap["rooms"])
    text = f"{free} of {len(snap['rooms'])} study rooms are free now."
    if name == "show_rooms_app":
        return {"content": [{"type": "text", "text": text}], "structuredContent": snap}
    if name == "show_rooms_static":
        return {"content": [{"type": "text", "text": text}],
                "structuredContent": {"render": agent.static_payload(snap)}}
    if name == "show_rooms_declarative":
        return {"content": [{"type": "text", "text": text}],
                "structuredContent": {"render": agent.declarative_payload(snap, region=False)}}
    if name == "show_rooms_mixed":
        return {"content": [{"type": "text", "text": text}],
                "structuredContent": {"render": agent.declarative_payload(snap, region=True), **snap}}
    if name == "book_room":
        room = next((r for r in STATE["rooms"] if r["id"] == args.get("room")), None)
        if room is None or not room["available"]:
            return {"content": [{"type": "text", "text": f"{args.get('room')} is not free."}],
                    "isError": True}
        result = data.book(args["room"], args.get("slot", data.SLOTS[1]))
        room["available"], room["next_free"] = False, args.get("slot", data.SLOTS[1]).split("-")[1]
        return {"content": [{"type": "text", "text": result["message"]}],
                "structuredContent": {**snapshot(), "booking": result}}
    if name == "cancel_all_bookings":
        STATE["rooms"] = [dict(r) for r in data.ROOMS]
        return {"content": [{"type": "text", "text": "All bookings cancelled."}]}
    raise KeyError(name)


def read_resource(uri: str) -> dict:
    meta = next((r for r in RESOURCES if r["uri"] == uri), None)
    if meta is None:
        raise KeyError(uri)
    html = agent.app_html() if uri == APP_URI else agent.floor_map_html()
    return {"contents": [{"uri": uri, "mimeType": APP_MIME, "text": html, "_meta": meta["_meta"]}]}


def handle(req: dict) -> dict | None:
    """One JSON-RPC 2.0 request -> response (None for notifications)."""
    rid, method, params = req.get("id"), req.get("method"), req.get("params") or {}
    if rid is None:
        return None
    try:
        if method == "initialize":
            result = {"protocolVersion": PROTOCOL, "serverInfo": {"name": "study-rooms", "version": "1.0"},
                      "capabilities": {"tools": {}, "resources": {},
                                       "extensions": {"io.modelcontextprotocol/ui": {}}}}
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            result = call_tool(params["name"], params.get("arguments") or {})
        elif method == "resources/list":
            result = {"resources": RESOURCES}
        elif method == "resources/read":
            result = read_resource(params["uri"])
        else:
            return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": f"no method {method}"}}
    except KeyError as exc:
        return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32602, "message": f"unknown {exc}"}}
    return {"jsonrpc": "2.0", "id": rid, "result": result}
