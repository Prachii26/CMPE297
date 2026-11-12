"""A2UI messages, catalog and validation, written by hand (no SDK).

Envelope names follow A2UI v0.8. The server streams JSON Lines; each line
is one message:

  surfaceUpdate     {"surfaceUpdate": {"surfaceId", "components": [{"id", "component": {Type: props}}]}}
                    STRUCTURE. Components are a flat list with ids; a parent
                    lists child ids. A later surfaceUpdate merges by id, so an
                    existing surface is patched, never replaced.
  dataModelUpdate   {"dataModelUpdate": {"surfaceId", "path", "contents": [entries]}}
                    DATA. Typed entries {key, valueString | valueNumber |
                    valueBoolean | valueMap}. Arrays are valueMaps keyed "0","1",...
  beginRendering    {"beginRendering": {"surfaceId", "root"}}
  deleteSurface     {"deleteSurface": {"surfaceId"}}

Props are BoundValues: {"literalString": "..."} or {"path": "/metrics/0/value"},
so structure can point at data that changes independently of it.

The client sends back:
  userAction        {"userAction": {"name", "surfaceId", "sourceComponentId", "context": {...}}}
"""
from __future__ import annotations

import json

LIT = {"type": "object", "properties": {"literalString": {}, "literalNumber": {},
                                         "literalBoolean": {}, "path": {"type": "string"}}}

# Our study-room catalog. The CLIENT advertises which of these it supports;
# the agent may only use advertised components.
CATALOG = {
    "Column":         {"children": "ids"},
    "Row":            {"children": "ids"},
    "Text":           {"text": "bound", "usageHint": "enum:h1,h2,body,success"},
    "MetricCard":     {"label": "bound", "value": "bound"},
    "RoomTable":      {"rows": "bound"},
    "OccupancyChart": {"series": "bound"},
    "BookingForm":    {"rooms": "bound", "slots": "bound", "roomPath": "string",
                       "slotPath": "string"},
    "Button":         {"label": "bound", "action": "action"},
}
# A client-side escape hatch, NOT part of A2UI's standard catalog: generated
# HTML in a sandboxed iframe. Only usable if the client advertises it.
HTML_ARTIFACT = {"HtmlArtifact": {"html": "bound", "title": "bound"}}

ADVERTISED = {
    "static": {},                                   # client owns the surface; data only
    "declarative": dict(CATALOG),
    "open_ended": dict(HTML_ARTIFACT),
    "mixed": {**CATALOG, **HTML_ARTIFACT},
}


def validate_component(comp: dict, catalog: dict) -> list[str]:
    errors = []
    cid = comp.get("id")
    body = comp.get("component")
    if not isinstance(cid, str) or not isinstance(body, dict) or len(body) != 1:
        return [f"malformed component {comp!r:.80}"]
    (ctype, props), = body.items()
    if ctype not in catalog:
        return [f"component '{cid}': type '{ctype}' is not in the client's advertised catalog"]
    spec = catalog[ctype]
    for k, v in props.items():
        if k not in spec:
            errors.append(f"component '{cid}': unknown prop '{k}' for {ctype}")
        elif spec[k] == "bound" and not (isinstance(v, dict) and set(v) & set(LIT["properties"])):
            errors.append(f"component '{cid}': prop '{k}' must be a BoundValue")
        elif spec[k] == "ids" and not (isinstance(v, dict) and isinstance(v.get("explicitList"), list)):
            errors.append(f"component '{cid}': children must be {{explicitList: [ids]}}")
        elif spec[k].startswith("enum:") and v not in spec[k][5:].split(","):
            errors.append(f"component '{cid}': {k}={v!r} not allowed")
    return errors


def validate_message(msg: dict, catalog: dict) -> list[str]:
    if len(msg) != 1:
        return ["a message must have exactly one envelope key"]
    (kind, body), = msg.items()
    if kind == "surfaceUpdate":
        return [e for c in body.get("components", []) for e in validate_component(c, catalog)]
    if kind in ("dataModelUpdate", "beginRendering", "deleteSurface"):
        return [] if "surfaceId" in body else [f"{kind} missing surfaceId"]
    return [f"unknown envelope '{kind}'"]


# ------------------------------------------------- data model entries
def to_contents(obj: dict) -> list[dict]:
    """A plain dict -> A2UI typed entries (arrays become index-keyed maps)."""
    def entry(key, v):
        if isinstance(v, bool):
            return {"key": key, "valueBoolean": v}
        if isinstance(v, (int, float)):
            return {"key": key, "valueNumber": v}
        if isinstance(v, str):
            return {"key": key, "valueString": v}
        if isinstance(v, list):
            return {"key": key, "valueMap": [entry(str(i), x) for i, x in enumerate(v)],
                    "isList": True}
        return {"key": key, "valueMap": [entry(k, x) for k, x in v.items()]}
    return [entry(k, v) for k, v in obj.items()]


def from_contents(entries: list[dict]) -> dict:
    out = {}
    for e in entries:
        if "valueMap" in e:
            inner = from_contents(e["valueMap"])
            out[e["key"]] = [inner[str(i)] for i in range(len(inner))] if e.get("isList") else inner
        else:
            out[e["key"]] = next(e[k] for k in ("valueString", "valueNumber", "valueBoolean") if k in e)
    return out


def jsonl(msg: dict) -> str:
    return json.dumps(msg) + "\n"
