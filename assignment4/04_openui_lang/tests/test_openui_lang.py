"""Theme 04 offline tests: grammar, catalog, sandbox, forward references,
streaming prefixes, and the token measurement (offline tokenizer)."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["TIKTOKEN_CACHE_DIR"] = str(ROOT / "tokenizer")

from fastapi.testclient import TestClient  # noqa: E402

import agent  # noqa: E402
import formats  # noqa: E402
import lang  # noqa: E402
from security import CSP  # noqa: E402
from server import app, checked  # noqa: E402

client = TestClient(app)


def test_program_parses_validates_and_resolves_to_theme03_components():
    prog = lang.parse(formats.openui_lang())
    assert prog.errors == [] and lang.validate(prog, lang.CATALOG) == []
    comps = lang.to_components(prog, lang.CATALOG)
    assert comps["m0"] == {"MetricCard": {"label": "Rooms free now", "value": "3 / 6"}}
    assert comps["root"]["Column"]["children"][0] == {"$ref": "title"}
    assert comps["table"]["RoomTable"]["rows"][0]["id"] == "LIB-201"
    assert {next(iter(c)) for c in comps.values()} <= set(lang.CATALOG)


def test_out_of_catalog_component_is_rejected():
    prog = lang.parse('root = Column([x])\nx = Carousel(["a", "b"])\n')
    assert lang.validate(prog, lang.CATALOG) == ["x: component 'Carousel' is not in the catalog"]
    out = checked("declarative", 'x = Carousel(["a"])\nt = Text("ok")\n')
    assert out.splitlines()[0].startswith("# rejected:") and out.splitlines()[1] == 't = Text("ok")'
    # static mode: the agent may define values, never components
    assert checked("static", 'root = Text("hijack")\n').startswith("# rejected: static mode")
    assert lang.validate(lang.parse('m = MetricCard("a", "b", "c")\n'), lang.CATALOG)[0].endswith("got 3")


def test_sandbox_attributes_and_csp_are_present():
    prog = lang.parse(agent.program("open_ended"))
    html = prog.statements["root"].args[0]
    assert f'content="{CSP}"' in html
    assert client.get("/config").json()["sandbox"] == "allow-scripts"
    js = (ROOT / "page" / "app.js").read_text(encoding="utf-8")
    assert "sandbox: CFG.sandbox" in js and "allow-same-origin" not in js
    assert "HtmlArtifact" not in lang.MODE_CATALOG["declarative"]


def test_forward_references_and_every_streaming_prefix():
    text = formats.openui_lang()
    seen = 0
    for cut in range(0, len(text) + 1, 7):
        prog = lang.parse(text[:cut], complete=False)
        assert prog.errors == []                    # an unfinished line is never an error
        assert len(prog.order) >= seen               # statements only ever accumulate
        seen = len(prog.order)
    early = lang.parse("root = Column([title, chart])\n", complete=False)
    assert lang.validate(early, lang.CATALOG) == [
        "root: reference 'title' is never defined", "root: reference 'chart' is never defined"]
    later = lang.parse('root = Column([title])\ntitle = Text("hi")\n')
    assert lang.validate(later, lang.CATALOG) == []


def test_token_measurement_runs_offline_and_matches_the_readme():
    import tiktoken
    enc = tiktoken.get_encoding("cl100k_base")
    lang_t = len(enc.encode(formats.openui_lang()))
    jr = len(enc.encode(formats.json_render()))
    a2 = len(enc.encode(formats.a2ui_jsonl()))
    assert (lang_t, jr, a2) == (460, 499, 1132)
    assert lang_t < jr < a2
