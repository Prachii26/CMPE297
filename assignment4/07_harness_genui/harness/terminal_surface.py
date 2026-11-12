"""NEW in assignment 4: the terminal surface for render_ui.

Draws a validated spec with rich, on the same console stage 13's ui.py uses.
A terminal cannot run HTML, so an HtmlArtifact is shown as a placeholder
pointing at the web surface.
"""
from __future__ import annotations

from rich.columns import Columns
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

import ui


def _rooms(rooms):
    t = Table(expand=True, title="Rooms")
    for c in ("Room", "Building", "Seats", "Status"):
        t.add_column(c)
    for r in rooms:
        t.add_row(r["name"], r.get("building", ""), str(r["capacity"]),
                  Text("free now", "green") if r["available"] else Text(f"free at {r.get('next_free', '?')}", "red"))
    return t


REGISTRY = {
    "Stack": lambda p, kids: Columns(kids, equal=True, expand=True) if p.get("direction") == "row" else Group(*kids),
    "Heading": lambda p, _k: Text(p["text"], style={"success": "bold green", "error": "bold red"}.get(
        p.get("tone"), "bold underline")),
    "Metric": lambda p, _k: Panel(Text(p["value"], "bold cyan", justify="center"), title=p["label"],
                                  border_style="cyan"),
    "RoomTable": lambda p, _k: _rooms(p["rooms"]),
    "BarChart": lambda p, _k: Panel("\n".join(f"{b['label']:>4} {'█' * (b['value'] // 5):<20} {b['value']:>3}%"
                                              for b in p["bars"]), title=p.get("title", "chart"),
                                    border_style="blue"),
    "Button": lambda p, _k: Text(f"[ {p['label']} ]  (action: {p['action']['name']})", style="reverse"),
    "HtmlArtifact": lambda p, _k: Panel(Text(
        f"interactive HTML ({len(p['html'])} bytes) - a terminal cannot run it; "
        "it is live, sandboxed, on the --web surface.", "yellow"),
        title=p.get("title", "HtmlArtifact"), border_style="yellow"),
}


def to_renderable(spec: dict):
    def draw(eid):
        el = spec["elements"][eid]
        return REGISTRY[el["type"]](el["props"], [draw(c) for c in el.get("children", [])])
    return draw(spec["root"])


class TerminalSurface:
    name = "terminal"

    def __init__(self, console=None):
        self.console = console or ui.console
        self.last = None

    def show(self, spec: dict, mode: str) -> None:
        self.last = spec
        body = to_renderable(spec)
        if mode == "static":           # the harness owns the layout; the agent filled one slot
            body = Panel(body, title="[harness frame] the agent named one prebuilt component",
                         border_style="dim")
        self.console.print(Panel(body, title=f"render_ui · terminal surface · {mode}", border_style="white"))
