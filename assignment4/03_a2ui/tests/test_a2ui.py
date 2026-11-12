"""Theme 03 offline tests: message shape, advertised-catalog enforcement,
sandbox, structure/data independence, and patch-not-replace on action."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

import a2ui  # noqa: E402
import agent  # noqa: E402
from security import CSP  # noqa: E402
from server import app  # noqa: E402

client = TestClient(app)
ADV = {m: sorted(c) for m, c in a2ui.ADVERTISED.items()}


def run(mode, catalog=None):
    body = {"mode": mode, "clientCapabilities": {"catalog": ADV[mode] if catalog is None else catalog},
            "delay": 0}
    return [json.loads(l) for l in client.post("/a2ui/run", json=body).text.splitlines()]


def act(mode, room="LIB-201", slot="14:00-15:00"):
    body = {"mode": mode, "clientCapabilities": {"catalog": ADV[mode]}, "delay": 0,
            "userAction": {"name": "confirm_booking", "surfaceId": "rooms",
                           "sourceComponentId": "confirm", "context": {"room": room, "slot": slot}}}
    return [json.loads(l) for l in client.post("/a2ui/action", json=body).text.splitlines()]


def test_messages_have_one_envelope_and_validate():
    for mode in ADV:
        for m in run(mode):
            assert len(m) == 1 and next(iter(m)) in (
                "surfaceUpdate", "dataModelUpdate", "beginRendering", "deleteSurface")
            assert a2ui.validate_message(m, a2ui.ADVERTISED[mode]) == []
    # flat component list with ids, children by id
    comps = [c for m in run("declarative") if "surfaceUpdate" in m for c in m["surfaceUpdate"]["components"]]
    ids = {c["id"] for c in comps}
    for c in comps:
        kids = next(iter(c["component"].values())).get("children", {}).get("explicitList", [])
        assert set(kids) <= ids


def test_component_outside_the_advertised_catalog_is_rejected():
    # a client that does not advertise OccupancyChart never receives one
    cat = [c for c in ADV["declarative"] if c != "OccupancyChart"]
    lines = run("declarative", cat)
    errors = [l["error"] for l in lines if "error" in l]
    assert errors and "OccupancyChart" in errors[0]["rejected"][0]
    sent = [c["component"] for l in lines if "surfaceUpdate" in l for c in l["surfaceUpdate"]["components"]]
    assert not any("OccupancyChart" in c for c in sent)
    assert a2ui.validate_component({"id": "x", "component": {"Carousel": {}}}, a2ui.CATALOG)


def test_sandbox_attributes_and_csp_are_present():
    html = run("open_ended")[0]["surfaceUpdate"]["components"][0]["component"]["HtmlArtifact"]["html"]
    assert f'content="{CSP}"' in html["literalString"]
    assert client.get("/config").json()["sandbox"] == "allow-scripts"
    js = (ROOT / "page" / "app.js").read_text(encoding="utf-8")
    assert "sandbox: CFG.sandbox" in js and "allow-same-origin" not in js
    # HtmlArtifact is only reachable when advertised
    assert "HtmlArtifact" not in a2ui.ADVERTISED["declarative"]


def test_static_mode_is_data_only_and_data_changes_without_structure():
    kinds = [next(iter(m)) for m in run("static")]
    assert set(kinds) == {"dataModelUpdate"}
    decl = run("declarative")
    last = decl[-1]
    assert "dataModelUpdate" in last and last["dataModelUpdate"]["path"] == "/metrics/2"
    assert a2ui.from_contents(last["dataModelUpdate"]["contents"])["value"] == "38"


def test_user_action_patches_the_existing_surface():
    run("declarative")
    out = act("declarative")
    kinds = [next(iter(m)) for m in out]
    assert "beginRendering" not in kinds and "deleteSurface" not in kinds   # not replaced
    data = a2ui.from_contents(out[0]["dataModelUpdate"]["contents"])
    assert next(r for r in data["rooms"] if r["id"] == "LIB-201")["available"] is False
    assert data["metrics"][0]["value"] == "2 / 6"
    assert data["metrics"][2]["value"] == "38"        # the earlier live update is not lost
    changed = [c["id"] for c in out[-1]["surfaceUpdate"]["components"]]
    assert changed == ["result", "root"]                 # only what changed, merged by id
    assert a2ui.from_contents(a2ui.to_contents({"a": [1, {"b": True}]})) == {"a": [1, {"b": True}]}
