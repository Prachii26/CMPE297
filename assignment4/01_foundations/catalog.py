"""The component catalog for the declarative and mixed modes, and the JSON
Schema derived from it.

The catalog is the contract: the agent may only compose these eight types,
each with these props. The JSON Schema is GENERATED from the catalog, not
hand-written alongside it, so the two cannot drift. Validation happens on
the server before the final spec is accepted, and the browser renderer has
no drawing function for anything outside the catalog.
"""
from __future__ import annotations

import jsonschema

S, I, B = {"type": "string"}, {"type": "integer"}, {"type": "boolean"}
ROOM = {"type": "object", "required": ["id", "name", "capacity", "available"],
        "properties": {"id": S, "name": S, "building": S, "capacity": I, "available": B,
                       "next_free": S}}

# name -> (prop schema, required props, may it have children?)
CATALOG = {
    "Stack":          ({"direction": {"enum": ["row", "column"]}}, [], True),
    "Heading":        ({"text": S}, ["text"], False),
    "Text":           ({"text": S}, ["text"], False),
    "MetricCard":     ({"label": S, "value": S}, ["label", "value"], False),
    "RoomTable":      ({"rooms": {"type": "array", "items": ROOM}}, ["rooms"], False),
    "OccupancyChart": ({"series": {"type": "array", "items": {
                          "type": "object", "required": ["hour", "pct"],
                          "properties": {"hour": S, "pct": I}}}}, ["series"], False),
    "BookingForm":    ({"rooms": {"type": "array", "items": S},
                        "slots": {"type": "array", "items": S}}, ["rooms", "slots"], False),
    "Button":         ({"label": S, "action": S}, ["label", "action"], False),
}

# Mixed mode adds exactly one open-ended region to the same catalog.
SANDBOX_COMPONENT = ("SandboxedHtml", ({"html": S, "title": S}, ["html"], False))


def catalog(mixed: bool = False) -> dict:
    cat = dict(CATALOG)
    if mixed:
        cat[SANDBOX_COMPONENT[0]] = SANDBOX_COMPONENT[1]
    return cat


def _props_schema(props, required):
    return {"type": "object", "properties": props, "required": required,
            "additionalProperties": False}


def element_schema(cat: dict) -> dict:
    """One element of a FLAT element map: {type, props, children: [ids]}."""
    return {"oneOf": [
        {"type": "object", "required": ["type", "props"], "additionalProperties": False,
         "properties": {"type": {"const": name}, "props": _props_schema(p, req),
                        **({"children": {"type": "array", "items": S}} if kids else {})}}
        for name, (p, req, kids) in cat.items()]}


def flat_schema(mixed: bool = False) -> dict:
    cat = catalog(mixed)
    return {"$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "Flat element map", "type": "object",
            "required": ["root", "elements"], "additionalProperties": False,
            "properties": {"root": S, "elements": {"type": "object",
                                                   "additionalProperties": element_schema(cat)}}}


def nested_schema(mixed: bool = False) -> dict:
    cat = catalog(mixed)
    node = {"oneOf": [
        {"type": "object", "required": ["type", "props"], "additionalProperties": False,
         "properties": {"type": {"const": name}, "props": _props_schema(p, req),
                        **({"children": {"type": "array", "items": {"$ref": "#"}}}
                           if kids else {})}}
        for name, (p, req, kids) in cat.items()]}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "Nested tree", **node}


def validate_flat(spec: dict, mixed: bool = False) -> list[str]:
    """Schema errors plus the graph checks a schema cannot express."""
    errors = []
    v = jsonschema.Draft202012Validator(flat_schema(mixed))
    for e in v.iter_errors(spec):
        el_type = None
        path = list(e.absolute_path)
        if len(path) >= 2 and path[0] == "elements":
            el_type = spec["elements"].get(path[1], {}).get("type")
        if el_type is not None and el_type not in catalog(mixed):
            errors.append(f"element '{path[1]}': component '{el_type}' is not in the catalog")
        else:
            errors.append(f"{'/'.join(map(str, path)) or '(root)'}: {e.message[:120]}")
    if errors:
        return sorted(set(errors))
    els = spec["elements"]
    if spec["root"] not in els:
        errors.append(f"root '{spec['root']}' is not an element")
    for eid, el in els.items():
        for child in el.get("children", []):
            if child not in els:
                errors.append(f"element '{eid}' references missing child '{child}'")
    sandboxes = [e for e in els.values() if e["type"] == "SandboxedHtml"]
    if len(sandboxes) > 1:
        errors.append("mixed mode allows exactly one SandboxedHtml region")
    return errors
