"""Theme 01 offline tests: spec shape, catalog enforcement, sandbox, streaming."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import jsonschema  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import agent  # noqa: E402
import catalog  # noqa: E402
from partial_json import parse_partial  # noqa: E402
from server import CSP, SANDBOX, app  # noqa: E402

client = TestClient(app)


def events(mode, **kw):
    q = "&".join(f"{k}={v}" for k, v in {"mode": mode, "delay": 0, **kw}.items())
    body = client.get(f"/stream?{q}").text
    out = []
    for block in body.strip().split("\n\n"):
        ev = dict(line.split(": ", 1) for line in block.splitlines())
        out.append((ev["event"], json.loads(ev["data"])))
    return out


def test_declarative_spec_shape_validates_against_the_generated_schema():
    jsonschema.validate(agent.flat(), catalog.flat_schema())
    jsonschema.validate(agent.nested(), catalog.nested_schema())
    assert catalog.validate_flat(agent.flat()) == []
    assert len(catalog.CATALOG) == 8


def test_out_of_catalog_component_is_rejected():
    spec = agent.flat()
    spec["elements"]["stack_1"]["children"].append("x")
    spec["elements"]["x"] = {"type": "Carousel", "props": {"slides": []}}
    errors = catalog.validate_flat(spec)
    assert errors == ["element 'x': component 'Carousel' is not in the catalog"]
    # and SandboxedHtml is only legal in mixed mode
    assert catalog.validate_flat(agent.flat(mixed=True)) != []
    assert catalog.validate_flat(agent.flat(mixed=True), mixed=True) == []


def test_sandbox_attributes_and_csp_are_present():
    ev = dict(events("open_ended"))["html"]
    assert ev["sandbox"] == SANDBOX == "allow-scripts"
    assert "allow-same-origin" not in ev["sandbox"]
    assert f'<meta http-equiv="Content-Security-Policy" content="{CSP}">' in ev["html"]
    assert "default-src 'none'" in CSP
    js = (ROOT / "page" / "app.js").read_text(encoding="utf-8")
    assert "sandbox: cfg.sandbox" in js and "allow-same-origin" not in js
    mixed = dict(events("mixed"))["validation"]
    assert mixed["ok"] and mixed["sandbox"] == SANDBOX


def test_all_four_modes_stream_different_payloads():
    kinds = {m: {e for e, _ in events(m)} for m in ("static", "declarative", "open_ended", "mixed")}
    assert "component" in kinds["static"] and "chunk" in kinds["declarative"]
    assert "html" in kinds["open_ended"] and "chunk" in kinds["mixed"]
    statics = [p["component"] for e, p in events("static") if e == "component"]
    assert statics == ["MetricCard", "OccupancyChart", "RoomTable"]


def test_partial_parser_only_ever_shows_a_prefix_of_the_final_value():
    text = agent.declarative_text("flat")
    final = json.loads(text)
    for cut in range(1, len(text), 37):
        p = parse_partial(text[:cut])
        if p and "elements" in p:
            for k, v in p["elements"].items():
                assert k in final["elements"]
                assert v.get("type") in (None, final["elements"][k]["type"])
    assert parse_partial(text) == final


def test_confirm_action_round_trips():
    r = client.post("/action", json={"action": "confirm_booking", "room": "LIB-201",
                                     "slot": "14:00-15:00"}).json()
    assert r["ok"] and "Library 201" in r["message"]
