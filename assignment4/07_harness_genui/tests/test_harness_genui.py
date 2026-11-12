"""Theme 07 offline tests: render_ui inside the stage 15 loop, the catalog,
the sandbox, the mixed-mode rule, and both surfaces."""
import io
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "harness"), str(ROOT)]

from fastapi.testclient import TestClient  # noqa: E402
from rich.console import Console  # noqa: E402

import main as harness  # noqa: E402  (the stage 15 main.py, extended)
import render_ui as genui  # noqa: E402
import scripted_client  # noqa: E402
import server  # noqa: E402
import sessions  # noqa: E402
from terminal_surface import TerminalSurface, to_renderable  # noqa: E402


@pytest.fixture(autouse=True)
def isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(sessions, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(scripted_client, "ROOMS", [dict(r) for r in scripted_client.data.ROOMS])
    yield


def run(mode, prompt):
    msgs = harness.main(["--mode", mode, "--prompt", prompt])
    return msgs, [m["content"] for m in msgs if m["role"] == "tool"]


def test_render_ui_is_a_tool_of_the_stage15_loop():
    names = [t["function"]["name"] for t in harness.ALL_TOOLS]
    assert "render_ui" in names and "task" in names and "bash" in names      # stage 15 tools kept
    assert harness.ALL_FUNCTIONS["render_ui"] is genui.render_ui
    msgs, results = run("declarative", "Show me the study-room dashboard")
    assert results == [results[0]] and results[0].startswith("rendered 9 elements (declarative)")
    assert msgs[-1]["role"] == "assistant" and msgs[-1]["content"].startswith("Done")


def test_spec_shape_validates_and_out_of_catalog_is_rejected_as_a_result():
    good = scripted_client.dashboard()
    assert genui.validate(good, "declarative", "") == []
    bad = json.loads(json.dumps(good))
    bad["elements"]["x"] = {"type": "Carousel", "props": {}}
    assert genui.validate(bad, "declarative", "") == ["element 'x': 'Carousel' is not in the declarative catalog"]
    assert len(genui.CATALOG) == 6
    # inside the real loop: the error comes back as a tool result and the agent corrects
    _, results = run("declarative", "Dashboard with a carousel of room photos")
    assert results[0].startswith("error: spec rejected") and "Carousel" in results[0]
    assert results[1].startswith("rendered")


def test_sandbox_attributes_and_csp_are_present():
    genui.MODE, genui.CURRENT_REQUEST = "mixed", "give me an interactive room picker"
    spec = scripted_client.dashboard(interactive=True)
    assert genui.render_ui(spec).startswith("rendered")
    html = spec["elements"]["picker"]["props"]["html"]
    assert f'<meta http-equiv="Content-Security-Policy" content="{genui.CSP}">' in html
    assert genui.SANDBOX == "allow-scripts"
    js = (ROOT / "page" / "app.js").read_text(encoding="utf-8")
    assert "sandbox: CFG.sandbox" in js and 'allow-same-origin"' not in js


def test_mixed_mode_allows_html_only_for_interactive_requests():
    spec = scripted_client.dashboard(interactive=True)
    assert "only allowed when the user asks for something interactive" in " ".join(
        genui.validate(spec, "mixed", "Show me the dashboard"))
    assert genui.validate(spec, "mixed", "Give me an interactive picker") == []
    assert genui.validate(spec, "declarative", "interactive please") != []    # never in declarative
    _, plain = run("mixed", "Show me the dashboard")
    _, inter = run("mixed", "Show me the dashboard with an interactive room picker")
    assert plain[0].startswith("rendered 9") and inter[0].startswith("rendered 10")


def test_static_and_open_ended_modes():
    assert genui.validate({"root": "r", "elements": {"r": {"type": "RoomTable", "props": {"rooms": []}}}},
                          "static", "") == []
    assert genui.validate(scripted_client.dashboard(), "static", "") != []    # composition refused
    _, res = run("open_ended", "Show me the rooms")
    assert res[0].startswith("rendered 1 elements (open_ended)")


def test_one_agent_two_surfaces():
    genui.MODE = "declarative"
    buf = io.StringIO()
    term = TerminalSurface(Console(file=buf, width=110, color_system=None))
    web = server.WebSurface()
    genui.SURFACES[:] = [term, web]
    genui.CURRENT_REQUEST = ""
    assert genui.render_ui(scripted_client.dashboard()).endswith("on: terminal, web")
    assert "Library 201" in buf.getvalue() and "Bookings today" in buf.getvalue()
    sent = TestClient(server.app).get("/events?once=1").text
    payload = json.loads(sent.split("data: ", 1)[1])
    assert payload["spec"] == term.last and payload["mode"] == "declarative"
    out = io.StringIO()
    Console(file=out, width=100, color_system=None).print(to_renderable(payload["spec"]))
    assert "Peak occupancy" in out.getvalue()


def test_web_action_becomes_a_harness_turn():
    seen = []
    server.TURN["fn"] = lambda text: seen.append(text) or "Done - rendered"
    r = TestClient(server.app).post("/action", json={"name": "confirm_booking",
                                                      "params": {"room": "ENG-112", "slot": "14:00-15:00"}}).json()
    assert seen == ["Book ENG-112 for 14:00-15:00"] and r["reply"] == "Done - rendered"
