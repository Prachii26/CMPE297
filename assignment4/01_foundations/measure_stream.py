"""At which streamed chunk does the layout become known: nested tree vs flat
element map?

    .\\.venv\\Scripts\\python.exe measure_stream.py

The same dashboard (same components, same props) is serialised both ways,
streamed in fixed CHUNK-character pieces, and after every chunk the prefix
is run through the tolerant partial-JSON parser. Three events are recorded:

  first paint    first chunk at which at least one leaf component is both
                 complete (its props equal the final props) and placed
                 (reachable from the root through known structure)
  layout known   first chunk at which every container and its full ordered
                 list of children is known -- every slot exists and is in its
                 final position, even if its content is still streaming
  all complete   first chunk at which every component is complete

Writes docs/stream_measurement.json and prints a markdown table.
"""
from __future__ import annotations

import json
from pathlib import Path

import agent
from partial_json import parse_partial
from server import CHUNK


def flat_state(partial, final):
    els = (partial or {}).get("elements", {}) if isinstance(partial, dict) else {}
    fels = final["elements"]
    root = (partial or {}).get("root")
    reach, todo = set(), [root] if root in els else []
    while todo:
        eid = todo.pop()
        if eid in reach or eid not in els:
            continue
        reach.add(eid)
        todo.extend(els[eid].get("children", []) if isinstance(els[eid], dict) else [])
    leaves = [k for k, v in fels.items() if "children" not in v]
    complete = sum(1 for k in leaves if k in reach and els.get(k) == fels[k])
    containers = [k for k, v in fels.items() if "children" in v]
    layout = root == final["root"] and all(
        k in els and isinstance(els[k], dict) and els[k].get("children") == fels[k]["children"]
        and els[k].get("type") == fels[k]["type"] for k in containers)
    return complete, len(leaves), layout


def _shape(node):
    if not isinstance(node, dict) or "type" not in node:
        return None
    return (node["type"], tuple(_shape(c) for c in node.get("children", []))
            if "children" in node else None)


def nested_state(partial, final):
    def leaves(f):
        return 1 if "children" not in f else sum(leaves(c) for c in f["children"])

    def done(p, f):
        if not isinstance(p, dict):
            return 0
        if "children" not in f:
            return int(p == f)
        kids = p.get("children", []) if isinstance(p.get("children"), list) else []
        return sum(done(pc, fc) for pc, fc in zip(kids, f["children"]))

    return done(partial, final), leaves(final), _shape(partial) == _shape(final)


def measure(shape: str) -> dict:
    text = agent.declarative_text(shape)
    final = json.loads(text)
    n_chunks = -(-len(text) // CHUNK)
    first_paint = layout_known = all_done = None
    curve = []
    for i in range(1, n_chunks + 1):
        partial = parse_partial(text[: i * CHUNK])
        complete, total, layout = (flat_state if shape == "flat" else nested_state)(partial, final)
        curve.append(complete)
        if first_paint is None and complete:
            first_paint = i
        if layout_known is None and layout:
            layout_known = i
        if all_done is None and complete == total:
            all_done = i
    return {"shape": shape, "chars": len(text), "chunks": n_chunks, "components": total,
            "first_paint": first_paint, "layout_known": layout_known, "all_complete": all_done,
            "complete_by_quarter": {q: curve[max(0, round(n_chunks * q / 4) - 1)] for q in (1, 2, 3, 4)}}


def main() -> None:
    rows = [measure("nested"), measure("flat")]
    out = Path(__file__).parent / "docs" / "stream_measurement.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({"chunk_chars": CHUNK, "results": rows}, indent=2))
    print(f"chunk size: {CHUNK} characters\n")
    print("| shape | chars | chunks | first paint | layout known | all complete | complete at 25% / 50% / 75% of stream |")
    print("|---|---|---|---|---|---|---|")
    for r in rows:
        q = r["complete_by_quarter"]
        print(f"| {r['shape']} | {r['chars']} | {r['chunks']} | chunk {r['first_paint']} "
              f"| chunk {r['layout_known']} ({100 * r['layout_known'] / r['chunks']:.0f}%) "
              f"| chunk {r['all_complete']} | {q[1]} / {q[2]} / {q[3]} of {r['components']} |")


if __name__ == "__main__":
    main()
