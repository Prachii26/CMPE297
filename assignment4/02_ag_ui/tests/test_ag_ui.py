"""Theme 02 offline tests: event shape, catalog enforcement, sandbox, one
transport for four modes, and the shared-state round trip."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

import agent  # noqa: E402
import catalog  # noqa: E402
from events import EVENT_TYPES, apply_patch  # noqa: E402
from security import CSP, SANDBOX  # noqa: E402
from server import app  # noqa: E402

client = TestClient(app)


def run(mode, state=None, messages=()):
    body = {"state": state, "messages": list(messages), "forwardedProps": {"mode": mode, "delay": 0}}
    text = client.post("/agent", json=body).text
    return [json.loads(f[6:]) for f in text.strip().split("\n\n")]


def fold(events, state=None):
    """What the client does: snapshot replaces, delta patches."""
    for e in events:
        if e["type"] == "STATE_SNAPSHOT":
            state = e["snapshot"]
        elif e["type"] == "STATE_DELTA":
            state = apply_patch(state, e["delta"])
    return state


def test_every_event_has_the_spec_fields_and_the_ui_validates():
    for mode in ("static", "declarative", "open_ended", "mixed"):
        evs = run(mode)
        assert evs[0]["type"] == "RUN_STARTED" and evs[-1]["type"] == "RUN_FINISHED"
        for e in evs:
            assert e["type"] in EVENT_TYPES and EVENT_TYPES[e["type"]] <= e.keys()
    ui = fold(run("declarative"))["ui"]
    assert catalog.validate_flat(ui) == [] and len(ui["elements"]) == 10
    assert catalog.validate_flat(fold(run("mixed"))["ui"], mixed=True) == []


def test_out_of_catalog_component_is_rejected(monkeypatch):
    real = agent.ui_spec

    def with_carousel(mixed):
        s = real(mixed)
        s["elements"]["x"] = {"type": "Carousel", "props": {}}
        s["order"].append(("page", "x"))
        return s
    monkeypatch.setattr(agent, "ui_spec", with_carousel)
    evs = run("declarative")
    errors = [e for e in evs if e["type"] == "RUN_ERROR"]
    assert errors and "Carousel" in errors[0]["message"]
    assert not [e for e in evs if e["type"] == "STATE_DELTA"]   # nothing reached the surface


def test_sandbox_attributes_and_csp_are_present():
    evs = run("open_ended")
    args = json.loads("".join(e["delta"] for e in evs if e["type"] == "TOOL_CALL_ARGS"))
    assert f'content="{CSP}"' in args["html"]
    assert client.get("/config").json()["sandbox"] == SANDBOX == "allow-scripts"
    floor = fold(run("mixed"))["ui"]["elements"]["floor"]["props"]["html"]
    assert "Content-Security-Policy" in floor
    js = (ROOT / "page" / "app.js").read_text(encoding="utf-8")
    assert "sandbox: CFG.sandbox" in js and "allow-same-origin" not in js


def test_four_modes_one_transport():
    kinds = {m: {e["type"] for e in run(m)} for m in ("static", "declarative", "open_ended", "mixed")}
    assert all(k <= set(EVENT_TYPES) for k in kinds.values())
    names = {m: {e.get("toolCallName") for e in run(m) if e["type"] == "TOOL_CALL_START"}
             for m in kinds}
    assert names["static"] == {"show_component"} and names["open_ended"] == {"render_html"}
    assert "STATE_DELTA" in kinds["declarative"] and "TOOL_CALL_START" not in kinds["declarative"]


def test_user_state_patch_is_seen_by_the_agent():
    state = fold(run("declarative"))
    state = apply_patch(state, [{"op": "replace", "path": "/booking",
                                 "value": {"room": "ENG-112", "slot": "15:00-16:00",
                                           "status": "requested"}}])
    evs = run("declarative", state, [{"role": "user", "content": "Please book ENG-112."}])
    said = "".join(e["delta"] for e in evs if e["type"] == "TEXT_MESSAGE_CONTENT")
    assert "ENG-112" in said and "15:00-16:00" in said          # read from shared state
    after = fold(evs, state)
    assert after["booking"]["status"] == "confirmed"
    eng = next(r for r in after["rooms"] if r["id"] == "ENG-112")
    assert eng["available"] is False
    assert after["ui"]["elements"]["done"]["type"] == "Text"     # surface patched, not replaced
    assert "STATE_SNAPSHOT" not in {e["type"] for e in evs}
