"""The second render target: the same spec, drawn in a terminal with rich.

    .\\.venv\\Scripts\\python.exe terminal.py --mode declarative
    .\\.venv\\Scripts\\python.exe terminal.py --mode declarative --book ENG-112 --svg docs\\terminal.svg

It consumes the same validated patch stream as the web page
(spec_stream.stream), so both renderers draw the same spec. The registry
below covers the same catalog names as page/app.js -- except that a terminal
cannot run HTML, so HtmlArtifact gets an honest placeholder.
"""
from __future__ import annotations

import argparse

from rich.columns import Columns
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

import spec_stream


def _bar(v: int) -> str:
    return "█" * (v // 5) + ("▌" if v % 5 >= 3 else "")


REGISTRY = {
    "Stack": lambda p, kids: (Columns(kids, equal=True, expand=True)
                              if p.get("direction") == "row" else Group(*kids)),
    "Heading": lambda p, _k: Text(p["text"], style="bold underline"),
    "Text": lambda p, _k: Text(p["text"], style={"success": "bold green", "error": "bold red"}
                               .get(p.get("tone"), "dim")),
    "Metric": lambda p, _k: Panel(Text(p["value"], style="bold cyan", justify="center"),
                                  title=p["label"], border_style="cyan"),
    "RoomTable": lambda p, _k: _rooms(p["rooms"]),
    "BarChart": lambda p, _k: Panel("\n".join(f"{b['label']:>4} {_bar(b['value']):<20} {b['value']:>3}%"
                                              for b in p["bars"]) or "(no data yet)",
                                    title=p.get("title", "chart"), border_style="blue"),
    "BookingForm": lambda p, _k: Panel(Text.assemble(("room: ", "dim"), " ".join(f"[{r}]" for r in p["rooms"]),
                                                     ("\nslot: ", "dim"), " ".join(f"[{s}]" for s in p["slots"])),
                                       title="BookingForm", border_style="magenta"),
    "Button": lambda p, _k: Text(f"  [ {p['label']} ]  -> action {p['action']['name']}", style="reverse"),
    "HtmlArtifact": lambda p, _k: Panel(
        Text(f"open-ended HTML region ({len(p['html'])} bytes): a terminal cannot run it.\n"
             "Open the web view to see it, sandboxed.", style="yellow"),
        title=p.get("title", "HtmlArtifact"), border_style="yellow"),
}


def _rooms(rooms):
    t = Table(title="Rooms", expand=True)
    for c in ("Room", "Building", "Seats", "Status"):
        t.add_column(c)
    for r in rooms:
        t.add_row(r["name"], r.get("building", ""), str(r["capacity"]),
                  Text("free now", style="green") if r["available"]
                  else Text(f"free at {r.get('next_free', '?')}", style="red"))
    return t


def render(spec: dict):
    if not spec or "root" not in spec:
        return Text("(empty spec)")

    def draw(eid):
        el = spec["elements"].get(eid)
        if el is None:
            return Text(f"{eid}...", style="dim")
        fn = REGISTRY.get(el["type"])
        if fn is None:
            return Text(f"rejected: {el['type']} not in catalog", style="bold red")
        return fn(el["props"], [draw(c) for c in el.get("children", [])])
    return draw(spec["root"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="declarative",
                    choices=["static", "declarative", "open_ended", "mixed"])
    ap.add_argument("--book", help="send confirm_booking for this room after rendering")
    ap.add_argument("--svg", help="save the final frame as SVG")
    a = ap.parse_args()
    console = Console(record=bool(a.svg), width=110)
    errors = [op for op in spec_stream.stream(a.mode) if "error" in op]
    if a.book:
        errors += [op for op in spec_stream.action(a.mode, "confirm_booking",
                                                   {"room": a.book, "slot": "14:00-15:00"}) if "error" in op]
    spec = spec_stream.SPECS[a.mode]
    console.print(Panel(render(spec), title=f"json-render spec · terminal renderer · mode={a.mode}",
                        border_style="white"))
    for e in errors:
        console.print(Text(f"rejected patch: {e['error']}", style="red"))
    if a.svg:
        console.save_svg(a.svg, title=f"terminal renderer - {a.mode}")


if __name__ == "__main__":
    main()
