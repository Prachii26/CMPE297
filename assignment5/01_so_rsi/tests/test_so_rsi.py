"""SO-RSI: each component in isolation, then the loop."""
import json

from conftest import add_method_path
from core import ledger as ledger_mod
from core.proposers import ScriptedProposer
from task.splits import load_split
from task.strategies import BY_ID, initial_state

add_method_path("01_so_rsi")
import so_loop  # noqa: E402
from so_anomalies import TraceState, after_evaluation, before_evaluation  # noqa: E402
from so_memory import InquiryMemory  # noqa: E402
from so_probes import Prober  # noqa: E402

STEER = load_split("steering")
QIDS = {q["family"]: [x["qid"] for x in STEER if x["family"] == q["family"]] for q in STEER}


def _with(*sids, position=None):
    state = initial_state()
    for sid in sids:
        s = BY_ID[sid]
        if s.kind == "add_handler":
            state = state.with_component(s.component, position or s.position)
        else:
            state = state.with_flag(s.flag, s.value)
    return state


# ---------------------------------------------------------------- anomalies
def test_recurrence_needs_the_same_edit_in_the_same_solver():
    t = TraceState()
    t.observe(["add:j1_courses_by_dept"], "revert")
    assert [a.kind for a in before_evaluation(["add:j1_courses_by_dept"], t)] == ["recurrence"]
    t.observe(["add:a3_avg_grade_course"], "keep")        # the solver changed
    assert before_evaluation(["add:j1_courses_by_dept"], t) == []


def test_opposing_edit_is_an_undo_of_a_kept_change():
    t = TraceState()
    t.observe(["flag:LINK_ENTITIES=True"], "keep")
    a = before_evaluation(["flag:LINK_ENTITIES=False"], t)
    assert a[0].kind == "opposing" and "flag:LINK_ENTITIES=True" in a[0].detail


def test_expectation_mismatch():
    assert after_evaluation("k", ("a", "b"), ["a", "b"], []) == []
    m = after_evaluation("k", ("a", "b", "c", "d"), ["a"], [])
    assert m[0].kind == "expectation_mismatch" and set(m[0].qids) == {"b", "c", "d"}
    assert after_evaluation("k", ("a",), ["a"], ["z"])[0].kind == "expectation_mismatch"


# ------------------------------------------------------------------- probes
def test_dispatch_probe_confirms_shadowing_by_intervention():
    p = Prober(STEER)
    f = p.dispatch(_with("fix_J1"), QIDS["J1"], "j1_courses_by_dept", "add:j1_courses_by_dept")
    assert f.confirmed and f.mechanism == "shadowing"
    assert set(f.evidence["fired_instead"].values()) == {"generic_list"}
    assert f.evidence["fixed_by_priority_dispatch"] and p.queries > 0


def test_dispatch_probe_refutes_when_handler_is_reached():
    f = Prober(STEER).dispatch(_with("fix_J1_front"), QIDS["J1"], "j1_courses_by_dept", "k")
    assert not f.confirmed and f.evidence["fired_instead"] == {}


def test_values_probe_confirms_linking_on_the_user_phrased_instance():
    f = Prober(STEER).values(_with("fix_J1_front"), QIDS["J1"], "k")
    assert f.confirmed and f.mechanism == "value_linking"
    bad = [v for vs in f.evidence["literals_not_in_database"].values() for v in vs]
    assert bad and all(v == v.lower() for v in bad)


def test_counts_probe_confirms_duplicate_counting():
    f = Prober(STEER).counts(_with("fix_A4"), QIDS["A4"], "k")
    assert f.confirmed and f.mechanism == "duplicate_counting"
    assert f.evidence["count_star_queries"]


def test_implicated_probe_separates_useful_from_useless_undo():
    state = _with("fix_A3")
    fails = [q["qid"] for q in STEER if q["family"] == "A3"]
    p = Prober(STEER)
    assert p.implicated(state, state.without("a3_avg_grade_course"), fails, "k").confirmed is False
    broken = _with("fix_A3").with_component(BY_ID["fix_J1_front"].component, "prepend")
    assert p.implicated(broken, broken.with_flag("LINK_ENTITIES", True),
                        QIDS["J1"], "k").confirmed


# ------------------------------------------------------------------- memory
def test_inquiry_memory_persists_and_tracks_what_is_pending(tmp_path):
    m = InquiryMemory(tmp_path / "inq.jsonl")
    f = Prober(STEER).dispatch(_with("fix_J1"), QIDS["J1"], "j1_courses_by_dept",
                               "add:j1_courses_by_dept")
    m.record(f, 3)
    assert m.pending() == ["shadowing"]
    assert m.blocked_by("shadowing") == ["add:j1_courses_by_dept"]
    assert m.cause_of("add:j1_courses_by_dept") == "shadowing"
    m.mark("shadowing", kept=True)
    assert m.pending() == [] and m.cause_of("add:j1_courses_by_dept") is None
    rows = [json.loads(l) for l in (tmp_path / "inq.jsonl").read_text().splitlines()]
    assert rows[0]["round"] == 3 and rows[0]["mechanism"] == "shadowing"


# --------------------------------------------------------------------- loop
def _run(tmp_path, seed=2, iterations=12, ablation="full"):
    s = so_loop.run(ScriptedProposer(seed), iterations=iterations, seed=seed,
                    ledger_name="so", ablation=ablation)
    rows = ledger_mod.read(tmp_path / "ledgers" / "so.jsonl")
    return s, [r for r in rows if r["type"] == "iteration"]


def test_loop_makes_systematic_edits_from_confirmed_findings(tmp_path):
    s, its = _run(tmp_path)
    systematic = [e for e in its if e.get("strategy_id", "").startswith("systematic:")]
    assert systematic and any(e["decision"] == "keep" for e in systematic)
    assert all(e["proposer"] == "scripted" for e in its)
    assert s["confirmed_findings"] >= 1 and "shadowing" in s["mechanisms_applied"]


def test_loop_never_blind_repeats_and_logs_every_veto(tmp_path):
    s, its = _run(tmp_path, seed=0, iterations=20)
    assert s["blind_repeats"] == 0
    for e in its:
        for v in e.get("vetoed", []):
            assert v["reason"] and v["edit_key"]


def test_probes_never_score_validation(tmp_path, monkeypatch):
    """Probes run on steering only: every validation call is a counted evaluation."""
    from task import splits
    calls = {"n": 0}
    real = splits.ImproverView.validation_score

    def counting(self, solver):
        calls["n"] += 1
        return real(self, solver)
    monkeypatch.setattr(splits.ImproverView, "validation_score", counting)
    s, _ = _run(tmp_path, iterations=10)
    assert calls["n"] == s["evaluations"] and s["probe_queries"] > 0


def test_no_probes_ablation_is_a_plain_tabu_list(tmp_path):
    s, its = _run(tmp_path, ablation="no_probes")
    assert s["findings"] == 0 and s["mechanisms_applied"] == []
    assert not any(e.get("strategy_id", "").startswith("systematic:") for e in its)
