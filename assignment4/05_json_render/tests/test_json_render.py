"""Theme 05 offline tests: spec validation, catalog enforcement, sandbox,
patches in place, actions, and one spec driving two renderers."""
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402
from rich.console import Console  # noqa: E402

import agent  # noqa: E402
import catalog  # noqa: E402
import spec_stream  # noqa: E402
import terminal  # noqa: E402
from security import CSP  # noqa: E402
from server import app  # noqa: E402

client = TestClient(app)


def stream(mode):
    return [json.loads(l) for l in client.get(f"/spec/stream?mode={mode}&delay=0").text.splitlines()]


def test_built_spec_validates_against_per_component_schemas():
    for mode in ("static", "declarative", "open_ended", "mixed"):
        lines = stream(mode)
        assert not [l for l in lines if "error" in l], mode
        assert catalog.validate_spec(spec_stream.SPECS[mode], catalog.MODE_CATALOG[mode]) == []
    # a prop violating its schema is caught, not just an unknown type
    bad = {"root": "c", "elements": {"c": {"type": "BarChart", "props": {"bars": [{"label": "x", "value": 140}]}}}}
    errs = catalog.validate_spec(bad, catalog.CATALOG)
    assert errs and "BarChart" in errs[0]


def test_out_of_catalog_component_is_rejected_and_never_applied():
    spec_stream.SPECS["declarative"] = agent.empty("declarative")
    list(spec_stream.stream("declarative"))
    out = list(spec_stream.run_ops("declarative", [
        {"op": "add", "path": "/elements/x", "value": {"type": "Carousel", "props": {}}}]))
    assert "error" in out[0] and "Carousel" in out[0]["error"]["rejected"][0]
    assert "x" not in spec_stream.SPECS["declarative"]["elements"]
    # HtmlArtifact is out of catalog in declarative mode, too
    out = list(spec_stream.run_ops("declarative", [
        {"op": "add", "path": "/elements/y", "value": {"type": "HtmlArtifact", "props": {"html": "<b>"}}}]))
    assert "error" in out[0]


def test_sandbox_attributes_and_csp_are_present():
    stream("open_ended")
    html = spec_stream.SPECS["open_ended"]["elements"]["html"]["props"]["html"]
    assert f'content="{CSP}"' in html
    assert client.get("/config").json()["sandbox"] == "allow-scripts"
    js = (ROOT / "page" / "app.js").read_text(encoding="utf-8")
    assert "sandbox: CFG.sandbox" in js and "allow-same-origin" not in js


def test_static_mode_may_only_replace_props():
    lines = stream("static")
    assert {l["op"] for l in lines} == {"replace"}
    out = list(spec_stream.run_ops("static", [
        {"op": "add", "path": "/elements/z", "value": {"type": "Metric", "props": {"label": "a", "value": "b"}}}]))
    assert "static mode only allows replacing props" in out[0]["error"]["rejected"][0]


def test_action_patches_the_live_spec_in_place():
    stream("declarative")
    before = json.loads(json.dumps(spec_stream.SPECS["declarative"]))
    ops = [json.loads(l) for l in client.post("/action", json={
        "mode": "declarative", "name": "confirm_booking",
        "params": {"room": "ENG-112", "slot": "14:00-15:00"}}).text.splitlines()]
    assert ops and all(o["op"] in ("replace", "add") for o in ops)
    after = spec_stream.SPECS["declarative"]
    eng = next(r for r in after["elements"]["rooms"]["props"]["rooms"] if r["id"] == "ENG-112")
    assert eng["available"] is False and after["elements"]["m0"]["props"]["value"] == "2 / 6"
    assert after["elements"]["result"]["props"]["tone"] == "success"
    assert set(before["elements"]) | {"result"} == set(after["elements"])   # nothing replaced wholesale


def test_one_spec_two_renderers():
    stream("mixed")
    spec = spec_stream.SPECS["mixed"]
    buf = io.StringIO()
    Console(file=buf, width=110, color_system=None).print(terminal.render(spec))
    out = buf.getvalue()
    for name in ("Library 201", "Peak occupancy", "Confirm booking", "a terminal cannot run it"):
        assert name in out
    js = (ROOT / "page" / "app.js").read_text(encoding="utf-8")
    for comp in catalog.MODE_CATALOG["mixed"]:
        assert comp in terminal.REGISTRY and f"{comp}:" in js


def test_open_ended_action_can_only_resend_the_whole_region():
    stream("open_ended")
    ops = list(spec_stream.action("open_ended", "confirm_booking", {"room": "SU-018", "slot": "14:00-15:00"}))
    assert [o["path"] for o in ops] == ["/elements/html/props/html"]
    html = spec_stream.SPECS["open_ended"]["elements"]["html"]["props"]["html"]
    assert "Booked Student Union 018" in html and "Content-Security-Policy" in html
