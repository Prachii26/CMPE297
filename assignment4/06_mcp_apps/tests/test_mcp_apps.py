"""Theme 06 offline tests: MCP JSON-RPC shape, the ui:// link, catalog
payloads, sandbox/CSP, and the host's bridge policy."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

import agent  # noqa: E402
import mcp_server  # noqa: E402
from server import app  # noqa: E402

client = TestClient(app)
JS = (ROOT / "page" / "app.js").read_text(encoding="utf-8")


def rpc(method, params=None, rid=1):
    r = client.post("/mcp", json={"jsonrpc": "2.0", "id": rid, "method": method, "params": params or {}}).json()
    assert r["jsonrpc"] == "2.0" and r["id"] == rid
    return r


def test_tool_links_to_a_ui_resource_served_as_an_mcp_app():
    tools = {t["name"]: t for t in rpc("tools/list")["result"]["tools"]}
    uri = tools["show_rooms_app"]["_meta"]["ui"]["resourceUri"]
    assert uri == "ui://rooms/dashboard"
    content = rpc("resources/read", {"uri": uri})["result"]["contents"][0]
    assert content["mimeType"] == "text/html;profile=mcp-app"
    assert "ui/initialize" in content["text"] and "tools/call" in content["text"]
    assert content["_meta"]["ui"]["csp"] == {"connectDomains": [], "resourceDomains": []}
    res = rpc("tools/call", {"name": "show_rooms_app", "arguments": {}})["result"]
    assert res["content"][0]["type"] == "text" and "rooms" in res["structuredContent"]


def test_catalog_payload_shape_validates_and_out_of_catalog_is_rejected(monkeypatch):
    res = rpc("tools/call", {"name": "show_rooms_declarative"})["result"]
    payload = res["structuredContent"]["render"]
    assert agent.validate_payload(payload) == [] and payload["root"] in payload["elements"]
    assert rpc("tools/call", {"name": "show_rooms_static"})["result"]["structuredContent"]["render"]["component"] == "RoomTable"
    real = agent.declarative_payload
    monkeypatch.setattr(agent, "declarative_payload", lambda snap, region: {
        **real(snap, region), "elements": {**real(snap, region)["elements"],
                                           "x": {"type": "Carousel", "props": {}}}})
    bad = rpc("tools/call", {"name": "show_rooms_declarative"})["result"]
    assert bad["isError"] and "Carousel" in bad["content"][0]["text"] and "structuredContent" not in bad


def test_sandbox_attributes_and_csp_are_present():
    assert 'const SANDBOX = "allow-scripts";' in JS and 'allow-same-origin"' not in JS
    assert "sandbox: SANDBOX" in JS and "connect-src ${connect}" in JS
    assert "default-src 'none'" in JS and "|| \"'none'\"" in JS   # no origins asked -> connect-src 'none'


def test_host_bridge_allows_only_book_room():
    assert 'const ALLOWED_FROM_APP = new Set(["book_room"]);' in JS
    assert "ALLOWED_FROM_APP.has(name)" in JS and "-32001" in JS
    # the server would run it if asked directly -- the refusal is the host's
    tools = {t["name"] for t in rpc("tools/list")["result"]["tools"]}
    assert "cancel_all_bookings" in tools


def test_book_room_round_trip_and_unknown_method():
    client.post("/reset")
    ok = rpc("tools/call", {"name": "book_room", "arguments": {"room": "SU-018", "slot": "14:00-15:00"}})["result"]
    assert "Booked Student Union 018" in ok["content"][0]["text"]
    again = rpc("tools/call", {"name": "book_room", "arguments": {"room": "SU-018", "slot": "14:00-15:00"}})["result"]
    assert again["isError"]
    assert rpc("ui/whatever")["error"]["code"] == -32601
    assert client.post("/mcp", json={"jsonrpc": "2.0", "method": "notifications/initialized"}).status_code == 202
