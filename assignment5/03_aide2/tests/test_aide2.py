"""AIDE2: the control module, the hidden-evaluation boundary, the inner agent,
and the outer loop's lineage."""
import pytest

from conftest import add_method_path
from core import ledger as ledger_mod
from core.proposers import ScriptedProposer
from guard import guard
from task.boundary import BoundaryViolation, improvement_phase, inner_agent
from task.splits import ImproverView, load_split
from task.solver_state import load_state
from task.strategies import initial_state

add_method_path("03_aide2")
import aide_outer  # noqa: E402
from aide_control import SLOTS, ControlSpec, load, options  # noqa: E402
from aide_hidden import HiddenBenchmark, guard_control  # noqa: E402
from aide_inner import SteeringOnlyView, run_inner  # noqa: E402

STEER = load_split("steering")


# ------------------------------------------------------------ control module
def test_every_library_combination_renders_loads_and_passes_the_guard():
    spec = ControlSpec()
    for slot in SLOTS:
        for value in options(slot):
            s = spec.with_slot(slot, value, 1)
            ns = load(s.render())
            assert callable(ns.select_node) and ns.BRANCHING == s.BRANCHING
            assert guard_control(s.render()).ok, (slot, value)


def test_lineage_records_the_generation_of_each_slot():
    s = ControlSpec().with_slot("BRANCHING", 4, 2).with_slot("select_node", "ucb", 5)
    origin = dict(s.origin)
    assert origin["BRANCHING"] == 2 and origin["select_node"] == 5 and origin["PATIENCE"] == 0
    assert s.key() != ControlSpec().key()


@pytest.mark.parametrize("body,check", [
    ("from task.splits import load_split\nreturn frontier[0]", "heldout_access"),
    ("V = 'validation'\nreturn frontier[0]", "control_tamper"),
    ("import os\nreturn frontier[0]", "control_tamper"),
    ("from task import vault\nreturn frontier[0]", "heldout_access"),
])
def test_guard_rejects_control_code_that_reaches_for_hidden_data(body, check):
    src = ControlSpec().render().replace(
        "    return max(frontier, key=lambda n: (n.score, -n.depth))",
        "\n".join("    " + l for l in body.splitlines()))
    v = guard_control(src)
    assert not v.ok and v.check == check


# ----------------------------------------------------- hidden-eval boundary
def test_validation_is_sealed_inside_an_inner_agent():
    view = ImproverView()                         # built outside: allowed
    with inner_agent():
        with pytest.raises(BoundaryViolation, match="inner agent"):
            load_split("validation")
        with pytest.raises(BoundaryViolation, match="inner agent"):
            view.validation_score(load_state(initial_state()))
        assert len(load_split("steering")) == 40  # steering stays visible


def test_generated_control_code_cannot_load_validation_even_outside_the_context():
    code = compile("def peek():\n    from task.splits import load_split\n"
                   "    return load_split('validation')\n", "<control:attack>", "exec")
    ns = {}
    exec(code, ns)
    with pytest.raises(BoundaryViolation, match="generated code"):
        ns["peek"]()


def test_inner_agent_view_has_no_validation_at_all():
    view = SteeringOnlyView(STEER)
    assert not [a for a in dir(view) if "valid" in a.lower()]


def test_benchmark_exposes_only_scalars():
    with improvement_phase("t"):
        bench = HiddenBenchmark(inner_seeds=(0,), budget=4)
        res = bench.run(ControlSpec())
    pub = res.public()
    assert set(pub) == {"hidden", "per_seed", "steering", "attempts", "evals",
                        "shortcut_attempts", "guard_rejections", "guard"}
    assert all(isinstance(x, float) for x in pub["per_seed"])
    assert not [a for a in vars(bench) if "question" in a.lower()]


# --------------------------------------------------------------- inner agent
def _run(spec, seed=0, budget=10):
    with inner_agent():
        return run_inner(load(spec.render()), SteeringOnlyView(STEER), initial_state(),
                         ScriptedProposer(0), seed, guard.integrity_fingerprint(), budget)


def test_inner_agent_respects_its_budget_and_is_deterministic():
    a, b = _run(ControlSpec()), _run(ControlSpec())
    assert a.stats.attempts <= 10
    assert a.best_state.key() == b.best_state.key()      # fixed proposer, fixed seed


def test_reward_hacks_cost_inner_budget_and_are_rejected():
    hacky = ControlSpec().render().replace(
        "    return sorted(cands, key=lambda c: -c.weight)",
        "    return sorted(cands, key=lambda c: not c.is_shortcut)")
    with inner_agent():
        r = run_inner(load(hacky), SteeringOnlyView(STEER), initial_state(),
                      ScriptedProposer(0), 0, guard.integrity_fingerprint(), 8)
    assert r.stats.shortcut_attempts > 0
    assert sum(r.stats.guard_rejections.values()) >= r.stats.shortcut_attempts
    assert r.best_steering == 0.25                   # nothing a hack did was kept


# ---------------------------------------------------------------- outer loop
def test_outer_loop_keeps_only_winners_and_records_lineage(tmp_path):
    s = aide_outer.run(generations=2, per_generation=2, outer_seed=0, inner_seeds=(0,),
                       ledger_name="aide")
    rows = ledger_mod.read(tmp_path / "ledgers" / "aide.jsonl")
    its = [r for r in rows if r["type"] == "iteration"]
    assert its[0]["decision"] == "start" and len(its) == 1 + 2 * 2
    assert all(r["proposer"] == "scripted-outer" for r in rows)
    hidden = [l["hidden"] for l in s["lineage"]]
    assert hidden == sorted(hidden)                      # a survivor is never worse
    for slot, info in s["surviving_changes"].items():
        assert 1 <= info["from_generation"] <= 2
    assert 0.25 <= s["heldout_start"] <= s["heldout_final"] + 0.25
