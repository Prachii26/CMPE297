"""The scripted agent, emitting OpenUI-Lang-style text.

  static       only value statements (`free_value = "3 / 6"`, `rooms = [...]`).
               The LAYOUT program belongs to the client (page/app.js) and
               refers to these names before they exist -- forward references
               do the static mode's work.
  declarative  a whole program composed from theme 03's catalog
  open_ended   one statement: root = HtmlArtifact("<!doctype html>...")
  mixed        the declarative program plus one HtmlArtifact statement
"""
from __future__ import annotations

import json

import data
import formats
from security import sandboxed


def floor_map() -> str:
    cells = "".join(
        f"<g transform='translate({20 + (i % 3) * 110},{20 + (i // 3) * 70})'>"
        f"<rect width='100' height='58' rx='8' fill='{'#cfe8d4' if r['available'] else '#f1d3cf'}'"
        f" stroke='#555'/><text x='50' y='34' text-anchor='middle' font-size='12'>{r['id']}</text></g>"
        for i, r in enumerate(data.ROOMS))
    return sandboxed("<!doctype html><html><head><meta charset='utf-8'><style>body{margin:0}</style></head>"
                     f"<body><svg viewBox='0 0 360 170' width='100%' style='max-width:420px;display:block;"
                     f"margin:auto'>{cells}</svg></body></html>")


def open_page() -> str:
    cards = "".join(f"<div style='padding:14px;border:2px solid {'#2e8b57' if r['available'] else '#bbb'};"
                    f"border-radius:14px'><b>{r['name']}</b><br>{r['capacity']} seats</div>" for r in data.ROOMS)
    return sandboxed("<!doctype html><html><head><meta charset='utf-8'></head><body style='font:15px system-ui;"
                     "padding:16px;background:#f4f0ff'><h2 style='color:#5b3fbf'>Rooms (one HtmlArtifact line)</h2>"
                     f"<div style='display:grid;grid-template-columns:repeat(3,1fr);gap:10px'>{cards}</div>"
                     "</body></html>")


def program(mode: str) -> str:
    if mode == "static":
        m = data.metrics()
        lines = [f"{k}_label = {json.dumps(x['label'])}\n{k}_value = {json.dumps(x['value'])}"
                 for k, x in zip(("free", "peak", "today"), m)]
        lines.append("occupancy = [" + ", ".join(f'{{hour: "{o["hour"]}", pct: {o["pct"]}}}'
                                                  for o in data.OCCUPANCY) + "]")
        lines.append("rooms = [" + ", ".join(
            "{" + ", ".join(f"{k}: {json.dumps(r[k])}" for k in formats.ROOM_KEYS) + "}"
            for r in data.ROOMS) + "]")
        return "\n".join(lines) + "\n"
    if mode == "open_ended":
        return f'root = HtmlArtifact({json.dumps(open_page())}, "Agent-written page")\n'
    if mode == "mixed":
        return formats.openui_lang(mixed_html=floor_map())
    return formats.openui_lang()
