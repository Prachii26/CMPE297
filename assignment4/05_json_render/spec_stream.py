"""Patches, validated one at a time, shared by both renderers.

`stream(mode)` yields only patches that leave the spec valid against the
mode's catalog; anything else becomes an {"error": ...} line and is never
applied. The web server streams these lines; terminal.py consumes the same
generator. Both renderers therefore see the same spec, op for op.
"""
from __future__ import annotations

import copy
import re

import agent
import catalog

SPECS: dict[str, dict] = {}            # live spec per mode (one user at a time)
STATIC_PATH = re.compile(r"^/elements/[^/]+/props(/.*)?$")


def _parts(path):
    return [p.replace("~1", "/").replace("~0", "~") for p in path.split("/")[1:]]


def apply(doc, op):
    doc = copy.deepcopy(doc)
    parts = _parts(op["path"])
    parent = doc
    for p in parts[:-1]:
        parent = parent[int(p)] if isinstance(parent, list) else parent[p]
    last = parts[-1]
    if isinstance(parent, list):
        i = len(parent) if last == "-" else int(last)
        if op["op"] == "add":
            parent.insert(i, copy.deepcopy(op["value"]))
        elif op["op"] == "replace":
            parent[i] = copy.deepcopy(op["value"])
        elif op["op"] == "remove":
            parent.pop(i)
    elif op["op"] == "remove":
        parent.pop(last)
    else:
        if op["op"] == "replace" and last not in parent:
            raise KeyError(f"replace of missing {op['path']}")
        parent[last] = copy.deepcopy(op["value"])
    return doc


def check(mode: str, spec: dict, op: dict) -> tuple[dict | None, list[str]]:
    if mode == "static" and not (op["op"] == "replace" and STATIC_PATH.match(op["path"])):
        return None, [f"static mode only allows replacing props; got {op['op']} {op['path']}"]
    try:
        new = apply(spec, op)
    except (KeyError, IndexError, ValueError, TypeError) as exc:
        return None, [f"patch does not apply: {exc}"]
    if "root" in new and "elements" in new and new["root"] in new["elements"]:
        errors = catalog.validate_spec(new, catalog.MODE_CATALOG[mode])
        if errors:
            return None, errors
    return new, []


def run_ops(mode: str, ops):
    spec = SPECS.get(mode, agent.empty(mode))
    for op in ops:
        new, errors = check(mode, spec, op)
        if errors:
            yield {"error": {"op": op["path"], "rejected": errors}}
            continue
        spec = new
        SPECS[mode] = spec
        yield op


def stream(mode: str):
    SPECS[mode] = agent.empty(mode)
    yield from run_ops(mode, agent.build(mode))


def action(mode: str, name: str, params: dict):
    yield from run_ops(mode, agent.act(mode, SPECS.get(mode, {}), name, params))
