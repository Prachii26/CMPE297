"""Dream-RSI: the three stages separately, then the controlled comparison."""
import numpy as np

from conftest import add_method_path
from core import ledger as ledger_mod
from core.ledger import Ledger
from core.loop import Harness
from core.proposers import ScriptedProposer
from task.splits import ImproverView
from task.strategies import BY_ID, initial_state

add_method_path("02_dream_rsi")
import dream_loop  # noqa: E402
from dream_dreaming import improve  # noqa: E402
from dream_online import explore  # noqa: E402
from dream_policy import DESIGNED, FEATURES, THETA0, Policy, features  # noqa: E402
from dream_simulator import ReplaySimulator  # noqa: E402


def _harness(tmp_path):
    view = ImproverView()
    h = Harness(view, Ledger("d", run_id="d", method="t", proposer="scripted",
                             directory=tmp_path))
    return view, h, h.start(initial_state())


def _tree(tmp_path, budget=5, seed=0):
    view, h, root = _harness(tmp_path)
    tree = explore(Policy(THETA0.copy()), root, h, ScriptedProposer(seed, include_shortcuts=False),
                   budget, np.random.default_rng(seed), 1)
    return view, h, tree


def test_features_describe_an_expansion():
    f = features(0.4, {"J1": 2}, 3, BY_ID["fix_J1_front"], True, n_handlers=5)
    assert f.shape == (len(FEATURES),)
    named = dict(zip(FEATURES, f))
    assert named["family_failures"] == 1.0 and named["is_prepend"] == 1.0
    assert named["is_mechanism"] == 0.0 and named["mech_context"] == 0.0
    m = dict(zip(FEATURES, features(0.4, {"J1": 2}, 0, BY_ID["link_entities"], True, 5)))
    assert m["is_mechanism"] == 1.0 and m["mech_context"] == 5 / 15


def test_online_exploration_spends_exactly_its_budget_and_logs_traces(tmp_path):
    view, h, tree = _tree(tmp_path, budget=5)
    live = [t for t in tree.transitions if t["live_call"]]
    assert len(live) == 5 and h.evaluations == 1 + 5
    for t in tree.transitions:
        assert {"node", "strategy_id", "n_candidates", "features", "guard",
                "val_before"} <= t.keys()
    assert all(t["child"] in tree.nodes for t in live if t["guard"]["ok"])


def test_simulator_holds_only_recorded_expansions(tmp_path):
    _view, _h, tree = _tree(tmp_path, budget=6)
    sim = ReplaySimulator()
    sim.add_tree(tree)
    assert sim.n_edges == sum(1 for t in tree.transitions if t["live_call"] and t["guard"]["ok"])
    curve = sim.rollout(Policy(THETA0.copy()), tree.root, 20, np.random.default_rng(0))
    assert len(curve) <= sim.n_edges          # cannot dream past the realised space


def test_dreaming_costs_zero_live_calls(tmp_path):
    view, h, tree = _tree(tmp_path, budget=6)
    sim = ReplaySimulator()
    sim.add_tree(tree)
    before = (h.evaluations, view.validation_calls, view.steering_calls)
    res = improve(Policy(THETA0.copy()), sim, steps=6, seed=1, round_=1)
    assert (h.evaluations, view.validation_calls, view.steering_calls) == before
    assert res.candidates_evaluated > 0 and res.steps_simulated > 0


def test_inactive_weights_stay_pinned():
    sim = ReplaySimulator()
    view, h, tree = None, None, None
    import tempfile, pathlib
    with tempfile.TemporaryDirectory() as d:
        _v, _h, tree = _tree(pathlib.Path(d), budget=6)
    sim.add_tree(tree)
    res = improve(Policy(THETA0.copy(), active=DESIGNED.copy()), sim, 6, 1, 1)
    assert res.policy.theta[FEATURES.index("mech_context")] == 0.0


def test_support_only_leaves_unobserved_features_alone(tmp_path):
    _view, _h, tree = _tree(tmp_path, budget=6)
    sim = ReplaySimulator()
    sim.add_tree(tree)
    sup = dict(zip(FEATURES, sim.support()))
    tried_mechanism = any(t["strategy_id"] in ("dispatch_priority", "link_entities",
                                                "count_distinct") for t in tree.transitions)
    assert sup["is_mechanism"] == tried_mechanism
    res = improve(Policy(THETA0.copy()), sim, 6, 1, 1, support_only=True)
    for f, s in sup.items():
        if not s and DESIGNED[FEATURES.index(f)]:
            assert res.policy.theta[FEATURES.index(f)] == THETA0[FEATURES.index(f)]


def test_fixed_arm_never_changes_policy_and_shares_round_one(tmp_path):
    f = dream_loop.run_arm("fixed", seed=1, rounds=3, budget=3, ledger_name="fx")
    d = dream_loop.run_arm("dream", seed=1, rounds=3, budget=3, ledger_name="dr")
    rows_f = ledger_mod.read(tmp_path / "ledgers" / "fx.jsonl")
    rows_d = ledger_mod.read(tmp_path / "ledgers" / "dr.jsonl")
    assert {r["policy"]["label"] for r in rows_f if r["type"] == "round_end"} == {"theta0"}
    assert not any("dream" in r for r in rows_f if r["type"] == "round_end")
    r1 = lambda rows: [r["strategy_id"] for r in rows if r["type"] == "iteration"
                       and r["round"] == 1]
    assert r1(rows_f) == r1(rows_d)                  # same start, same random numbers
    assert f["live_calls"] == d["live_calls"] == 9   # same budget
    assert f["heldout_start"] == d["heldout_start"] == 0.25


def test_calls_to_reach():
    curve = [(0, 0.25), (3, 0.4), (7, 0.6), (9, 0.6)]
    assert dream_loop.calls_to_reach(curve, 0.6) == 7
    assert dream_loop.calls_to_reach(curve, 0.9) is None
