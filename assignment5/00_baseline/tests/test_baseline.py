"""The naive loop: ledgers every iteration, keeps only strict improvements,
is deterministic, and never switches proposers."""
import json

import pytest

from conftest import add_method_path
from core import ledger as ledger_mod
from core.proposers import LLMProposer, ProposalContext, ProposerError, ScriptedProposer

add_method_path("00_baseline")
import naive_loop  # noqa: E402

REQUIRED = {"iteration", "proposer", "strategy_id", "edit_key", "decision", "reason",
            "val_before", "wall_clock_s"}


def _iterations(tmp_path, name):
    rows = ledger_mod.read(tmp_path / "ledgers" / f"{name}.jsonl")
    return rows, [r for r in rows if r["type"] == "iteration"]


def test_run_ledgers_every_iteration(tmp_path):
    s = naive_loop.run(ScriptedProposer(0), iterations=8, seed=0, ledger_name="t")
    rows, its = _iterations(tmp_path, "t")
    assert rows[0]["type"] == "run_start" and rows[-1]["type"] == "run_end"
    assert len(its) == 8
    for e in its:
        assert REQUIRED <= e.keys()
        if e["decision"] in ("keep", "revert"):
            assert {"val_after", "steering_after", "actual_fixes"} <= e.keys()
    assert s["heldout_start"] == 0.25


def test_keeps_only_strict_validation_improvements(tmp_path):
    naive_loop.run(ScriptedProposer(1), iterations=15, seed=1, ledger_name="t")
    _, its = _iterations(tmp_path, "t")
    for e in its:
        if e["decision"] == "keep":
            assert e["val_after"] > e["val_before"]
        if e["decision"] == "revert":
            assert e["val_after"] <= e["val_before"]
    vals = [e["val_before"] for e in its]
    assert vals == sorted(vals)            # the current solver never gets worse


def test_same_seed_same_decisions(tmp_path):
    naive_loop.run(ScriptedProposer(3), iterations=10, seed=3, ledger_name="a")
    naive_loop.run(ScriptedProposer(3), iterations=10, seed=3, ledger_name="b")
    _, a = _iterations(tmp_path, "a")
    _, b = _iterations(tmp_path, "b")
    assert [(e["strategy_id"], e["decision"]) for e in a] == \
           [(e["strategy_id"], e["decision"]) for e in b]


def test_every_entry_names_one_proposer(tmp_path):
    naive_loop.run(ScriptedProposer(2), iterations=10, seed=2, ledger_name="t")
    rows, _ = _iterations(tmp_path, "t")
    assert {r["proposer"] for r in rows} == {"scripted"}


class _Failing:
    name = "llm:fake"

    def propose(self, ctx):
        raise ProposerError("HTTP 429: quota")


def test_a_failing_proposer_is_logged_not_replaced(tmp_path):
    """No silent fallback: errors become proposer_error entries."""
    s = naive_loop.run(_Failing(), iterations=3, seed=0, ledger_name="t")
    rows, its = _iterations(tmp_path, "t")
    assert [e["decision"] for e in its] == ["proposer_error"] * 3
    assert {r["proposer"] for r in rows} == {"llm:fake"}
    assert s["heldout_final"] == 0.25


def test_llm_reply_parsing_without_network(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-not-a-real-key")
    p = LLMProposer("gemini-test", max_calls=1)
    from task.strategies import initial_state
    from task.solver_state import load_state
    from task.evaluate import evaluate
    from task.splits import load_split
    steer = load_split("steering")
    ctx = ProposalContext(initial_state(), evaluate(load_state(initial_state()), steer, "s"), steer)
    reply = json.dumps({"kind": "add_handler", "name": "s4 cap", "position": "prepend",
                        "priority": 60, "body": "return None", "target_family": "S4",
                        "predicted_fixes": ["S4-0"], "rationale": "r"})
    prop = p._parse(reply, ctx)
    assert prop.proposer == "llm:gemini-test" and prop.kind == "add_handler"
    assert prop.component.cid == "llm_s4_cap" and prop.position == "prepend"
    with pytest.raises(ProposerError):
        p._parse('{"kind": "patch_file"}', ctx)
    with pytest.raises(ProposerError):
        p._parse("not json", ctx)
