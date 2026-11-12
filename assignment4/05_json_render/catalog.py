"""The json-render style catalog: one definition, three uses.

Each component has a JSON Schema for its props. From this one table we get
  1. the validator for a whole spec (validate_spec)
  2. the list of what the agent may emit (the prompt, if a model were used)
  3. the registries of BOTH renderers (page/app.js and terminal.py draw
     exactly these names, and nothing else)

A spec is a flat element map:
  {"root": "page", "elements": {"page": {"type": "Stack", "props": {...}, "children": [...]}}}
"""
from __future__ import annotations

import jsonschema

S, I, B = {"type": "string"}, {"type": "integer"}, {"type": "boolean"}
ROOM = {"type": "object", "required": ["id", "name", "capacity", "available"],
        "properties": {"id": S, "name": S, "building": S, "capacity": I, "available": B,
                       "next_free": S}, "additionalProperties": False}
ACTION = {"type": "object", "required": ["name"], "additionalProperties": False,
          "properties": {"name": {"enum": ["confirm_booking", "refresh"]},
                         "params": {"type": "object"}}}


def props(required, **p):
    return {"type": "object", "properties": p, "required": required, "additionalProperties": False}


CATALOG = {
    "Stack":          {"props": props([], direction={"enum": ["row", "column"]}), "children": True},
    "Heading":        {"props": props(["text"], text=S)},
    "Text":           {"props": props(["text"], text=S, tone={"enum": ["muted", "success", "error"]})},
    "Metric":         {"props": props(["label", "value"], label=S, value=S)},
    "RoomTable":      {"props": props(["rooms"], rooms={"type": "array", "items": ROOM})},
    "BarChart":       {"props": props(["bars"], title=S, bars={"type": "array", "items": props(
                          ["label", "value"], label=S, value={"type": "integer", "minimum": 0,
                                                              "maximum": 100})})},
    "BookingForm":    {"props": props(["rooms", "slots"], rooms={"type": "array", "items": S},
                                      slots={"type": "array", "items": S})},
    "Button":         {"props": props(["label", "action"], label=S, action=ACTION)},
}
HTML_ARTIFACT = {"HtmlArtifact": {"props": props(["html"], html=S, title=S)}}

MODE_CATALOG = {
    "static": {k: CATALOG[k] for k in ("Stack", "Metric", "BarChart", "RoomTable")},
    "declarative": CATALOG,
    "open_ended": {"Stack": CATALOG["Stack"], **HTML_ARTIFACT},
    "mixed": {**CATALOG, **HTML_ARTIFACT},
}


def element_schema(cat: dict) -> dict:
    return {"oneOf": [
        {"type": "object", "required": ["type", "props"], "additionalProperties": False,
         "properties": {"type": {"const": name}, "props": d["props"],
                        **({"children": {"type": "array", "items": S}} if d.get("children") else {})}}
        for name, d in cat.items()]}


def spec_schema(cat: dict) -> dict:
    return {"type": "object", "required": ["root", "elements"], "additionalProperties": False,
            "properties": {"root": S, "elements": {"type": "object",
                                                    "additionalProperties": element_schema(cat)}}}


def validate_element(eid: str, el: dict, cat: dict) -> list[str]:
    t = el.get("type") if isinstance(el, dict) else None
    if t not in cat:
        return [f"element '{eid}': '{t}' is not in the catalog"]
    v = jsonschema.Draft202012Validator(element_schema({t: cat[t]}))
    return [f"element '{eid}' ({t}): {e.message[:110]}" for e in v.iter_errors(el)]


def validate_spec(spec: dict, cat: dict) -> list[str]:
    if not isinstance(spec, dict) or "elements" not in spec or "root" not in spec:
        return ["spec needs root and elements"]
    errors = [e for eid, el in spec["elements"].items() for e in validate_element(eid, el, cat)]
    if spec["root"] not in spec["elements"]:
        errors.append(f"root '{spec['root']}' missing")
    for eid, el in spec["elements"].items():
        for c in el.get("children", []) if isinstance(el, dict) else []:
            if c not in spec["elements"]:
                errors.append(f"element '{eid}' references missing child '{c}'")
    if sum(1 for e in spec["elements"].values() if e.get("type") == "HtmlArtifact") > 1:
        errors.append("at most one HtmlArtifact")
    return errors
