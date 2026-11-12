"""NEW in assignment 4: a render_ui(spec) tool for the stage 15 loop.

The spec is a json-render style flat element map,
    {"root": "page", "elements": {"page": {"type": "Stack", "props": {...}, "children": [...]}}}
validated against a SIX-component catalog. A valid spec is handed to every
registered surface (the terminal, and the browser when --web is on); an
invalid one is returned to the model as an error string -- the same way the
loop already returns a failed bash command -- so the model can correct it.

Generation modes (set once by main.py --mode):
  static       exactly one catalog component, no composition; the harness
               draws it inside its own fixed frame
  declarative  any element map over the six components
  open_ended   a single HtmlArtifact (raw HTML, sandboxed on the web surface)
  mixed        the six components plus AT MOST ONE HtmlArtifact -- and only
               when the user's request asks for something interactive. That
               rule is enforced here, in the tool, not left to the model.
"""
from __future__ import annotations

import json
import re

import jsonschema

S, I, B = {"type": "string"}, {"type": "integer"}, {"type": "boolean"}


def _props(required, **p):
    return {"type": "object", "properties": p, "required": required, "additionalProperties": False}


ROOM = _props(["id", "name", "capacity", "available"], id=S, name=S, building=S, capacity=I,
              available=B, next_free=S)
CATALOG = {
    "Stack": _props([], direction={"enum": ["row", "column"]}),
    "Heading": _props(["text"], text=S, tone={"enum": ["normal", "success", "error"]}),
    "Metric": _props(["label", "value"], label=S, value=S),
    "RoomTable": _props(["rooms"], rooms={"type": "array", "items": ROOM}),
    "BarChart": _props(["bars"], title=S, bars={"type": "array", "items": _props(
        ["label", "value"], label=S, value={"type": "integer", "minimum": 0, "maximum": 100})}),
    "Button": _props(["label", "action"], label=S, action=_props(["name"], name=S, params={"type": "object"})),
}
HTML_ARTIFACT = {"HtmlArtifact": _props(["html"], html=S, title=S)}
CONTAINERS = {"Stack"}
STATIC_TYPES = {"Metric", "RoomTable", "BarChart"}

INTERACTIVE = re.compile(r"\b(interactive|click|clickable|pick|drag|choose|map)\b", re.I)

MODE = "declarative"          # set by main.py
CURRENT_REQUEST = ""          # set by main.py before each turn: the user's message
SURFACES: list = []           # objects with .show(spec, mode)

SANDBOX = "allow-scripts"
CSP = ("default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
       "img-src data:; base-uri 'none'; form-action 'none'")

RENDER_UI_SCHEMA = {
    "type": "function",
    "function": {
        "name": "render_ui",
        "description": (
            "Show the user an interface instead of (or as well as) text. `spec` is a flat "
            "element map {root, elements}; each element is {type, props, children?}. "
            "Components: Stack(direction), Heading(text, tone), Metric(label, value), "
            "RoomTable(rooms), BarChart(title, bars), Button(label, action{name, params}). "
            "Only if the user asks for something interactive you may add ONE "
            "HtmlArtifact(html, title), which is sandboxed."),
        "parameters": {"type": "object", "required": ["spec"],
                       "properties": {"spec": {"type": "object"}}},
    },
}


def catalog_for(mode: str) -> dict:
    if mode == "open_ended":
        return dict(HTML_ARTIFACT)
    if mode == "mixed":
        return {**CATALOG, **HTML_ARTIFACT}
    return dict(CATALOG)


def validate(spec, mode: str = None, request: str = None) -> list[str]:
    mode = mode or MODE
    request = CURRENT_REQUEST if request is None else request
    if not isinstance(spec, dict) or not isinstance(spec.get("elements"), dict) or "root" not in spec:
        return ["spec must be {root, elements}"]
    cat, els, errors = catalog_for(mode), spec["elements"], []
    for eid, el in els.items():
        t = el.get("type") if isinstance(el, dict) else None
        if t not in cat:
            errors.append(f"element '{eid}': '{t}' is not in the {mode} catalog")
            continue
        for e in jsonschema.Draft202012Validator(cat[t]).iter_errors(el.get("props", {})):
            errors.append(f"element '{eid}' ({t}): {e.message[:100]}")
        if "children" in el and t not in CONTAINERS:
            errors.append(f"element '{eid}': {t} cannot have children")
        for c in el.get("children", []):
            if c not in els:
                errors.append(f"element '{eid}' references missing child '{c}'")
    if spec["root"] not in els:
        errors.append(f"root '{spec['root']}' is not an element")
    html = [k for k, v in els.items() if isinstance(v, dict) and v.get("type") == "HtmlArtifact"]
    if mode == "static" and (len(els) != 1 or next(iter(els.values()), {}).get("type") not in STATIC_TYPES):
        errors.append("static mode: name exactly one prebuilt component (Metric, RoomTable or "
                      "BarChart); the harness owns the layout")
    if mode == "mixed":
        if len(html) > 1:
            errors.append("mixed mode allows at most one HtmlArtifact")
        if html and not INTERACTIVE.search(request or ""):
            errors.append("HtmlArtifact is only allowed when the user asks for something "
                          "interactive; use catalog components")
    return errors


def sandboxed(html: str) -> str:
    meta = f'<meta http-equiv="Content-Security-Policy" content="{CSP}">'
    return html.replace("<head>", "<head>" + meta, 1) if "<head>" in html else meta + html


def render_ui(spec) -> str:
    """The tool. Its return value is what the model reads."""
    if isinstance(spec, str):
        try:
            spec = json.loads(spec)
        except json.JSONDecodeError:
            return "error: spec is not valid JSON"
    errors = validate(spec)
    if errors:
        return "error: spec rejected -- " + "; ".join(errors)
    for el in spec["elements"].values():           # the CSP goes in before any surface sees it
        if el["type"] == "HtmlArtifact":
            el["props"]["html"] = sandboxed(el["props"]["html"])
    for s in SURFACES:
        s.show(spec, MODE)
    names = ", ".join(s.name for s in SURFACES) or "no surface"
    return f"rendered {len(spec['elements'])} elements ({MODE}) on: {names}"
