"""The domain: deterministic data, a fixed benchmark, a correct metric, and a
held-out boundary that holds in code."""
import json
from pathlib import Path

import pytest

from task import db, questions, vault
from task.boundary import BoundaryViolation, final_phase, improvement_phase
from task.evaluate import evaluate, results_match, run_sql
from task.solver_state import load, load_state
from task.splits import ImproverView, load_split
from task.strategies import BY_ID, COVERAGE_STRATEGIES, initial_state

DATA = Path(questions.DATA_DIR)


def _all(split):
    return json.loads((DATA / f"{split}.json").read_text(encoding="utf-8"))


def test_database_is_deterministic_and_has_eight_tables():
    assert db.build_rows() == db.build_rows()
    conn = db.connect()
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert tables == set(db.TABLES) and len(tables) == 8
    assert conn.execute("SELECT COUNT(*) FROM students").fetchone()[0] == db.N_STUDENTS


def test_retakes_exist_so_distinct_counting_matters():
    conn = db.connect()
    n = conn.execute("SELECT COUNT(*) FROM (SELECT e.student_id, s.course_id FROM enrollments e "
                     "JOIN sections s ON e.section_id = s.section_id "
                     "GROUP BY 1, 2 HAVING COUNT(*) > 1)").fetchone()[0]
    assert n > 0


def test_committed_questions_match_a_fresh_build():
    fresh = questions.build()
    for split in questions.SPLITS:
        assert fresh[split] == _all(split), f"{split}.json drifted from the generator"


def test_splits_are_40_40_40_disjoint_and_balanced():
    splits = {s: _all(s) for s in questions.SPLITS}
    assert [len(v) for v in splits.values()] == [40, 40, 40]
    ids = [q["qid"] for v in splits.values() for q in v]
    texts = [q["question"] for v in splits.values() for q in v]
    assert len(set(ids)) == 120 and len(set(texts)) == 120
    for v in splits.values():
        fams = {}
        for q in v:
            fams.setdefault(q["family"], []).append(q["phrasing"])
        assert len(fams) == 20 and all(sorted(p) == ["A", "B"] for p in fams.values())


def test_gold_results_reexecute_and_are_never_empty():
    conn = db.connect()
    for split in questions.SPLITS:
        for q in _all(split):
            rows = conn.execute(q["gold_sql"]).fetchall()
            assert questions.normalize_rows(rows, q["ordered"]) == q["gold_result"]
            assert q["gold_result"] and q["gold_result"] != [[None]]


def test_starting_solver_is_weak_and_inside_the_required_band():
    solver = load_state(initial_state())
    for split in ("steering", "validation", "heldout"):
        acc = evaluate(solver, _all(split), split).accuracy
        assert acc == 0.25
        assert 0.15 <= acc <= 0.55


def test_committed_solver_py_is_the_rendered_starting_state():
    assert Path("task/solver.py").read_text(encoding="utf-8") == initial_state().render()


def test_every_fix_together_reaches_100_percent():
    state = initial_state()
    for s in COVERAGE_STRATEGIES:
        if s.position == "append" and not s.sid.endswith("_distinct"):
            state = state.with_component(s.component, "append")
    for sid in ("dispatch_priority", "link_entities", "count_distinct"):
        state = state.with_flag(BY_ID[sid].flag, BY_ID[sid].value)
    solver = load_state(state)
    for split in ("steering", "validation", "heldout"):
        assert evaluate(solver, _all(split), split).accuracy == 1.0


def test_set_compare_ignores_order_unless_ordered():
    assert results_match([("b",), ("a",)], [["a"], ["b"]], ordered=False)
    assert not results_match([("b",), ("a",)], [["a"], ["b"]], ordered=True)
    assert results_match([(2.004,)], [[2.0]], ordered=False)      # floats compared at 2dp


def test_non_select_and_errors_count_as_wrong_not_skipped():
    with pytest.raises(ValueError):
        run_sql("DELETE FROM students")
    bad = load('def trace(q):\n    return "x", "SELEC nonsense"\n'
               'def solve(q):\n    return trace(q)[1]\n', "bad")
    rep = evaluate(bad, _all("steering"), "steering")
    assert rep.n == 40 and rep.n_correct == 0 and all(r.error for r in rep.results)


def test_heldout_cannot_be_loaded_as_a_split():
    with pytest.raises(BoundaryViolation):
        load_split("heldout")


def test_vault_is_sealed_during_improvement():
    solver = load_state(initial_state())
    with improvement_phase("test"):
        with pytest.raises(BoundaryViolation, match="phase 'improving'"):
            vault.heldout_score(solver, method="t", run_id="t", label="t", proposer="t")


def test_vault_opens_only_in_final_phase_and_is_audited(tmp_path):
    solver = load_state(initial_state())
    with pytest.raises(BoundaryViolation):
        vault.heldout_score(solver, method="t", run_id="t", label="t", proposer="t")
    with final_phase("test"):
        rep = vault.heldout_score(solver, method="t", run_id="r1", label="t", proposer="t")
    assert rep.accuracy == 0.25
    audit = (tmp_path / "ledgers" / "heldout_access.jsonl").read_text().splitlines()
    assert json.loads(audit[-1])["run_id"] == "r1"


def test_final_phase_cannot_open_inside_an_improvement_loop():
    with improvement_phase("loop"):
        with pytest.raises(BoundaryViolation, match="only after the improvement loop"):
            with final_phase("sneaky"):
                pass


def test_a_solver_cannot_read_heldout_even_during_final_scoring():
    """Generated code on the stack is refused even inside final_phase()."""
    src = (
        "SEEN = []\n"
        "def trace(q):\n"
        "    from task import vault\n"
        "    try:\n"
        "        vault.heldout_score(None, method='x', run_id='x', label='x', proposer='x')\n"
        "        SEEN.append('READ')\n"
        "    except Exception as exc:\n"
        "        SEEN.append(type(exc).__name__)\n"
        "    return 'stub', 'SELECT name FROM students WHERE 0'\n")
    code = compile(src, "<solver:attack>", "exec")
    ns = {}
    exec(code, ns)
    import types
    solver = types.SimpleNamespace(trace=ns["trace"], solve=lambda q: ns["trace"](q)[1])
    with final_phase("test"):
        vault.heldout_score(solver, method="t", run_id="t", label="t", proposer="t")
    assert set(ns["SEEN"]) == {"BoundaryViolation"}


def test_improver_view_exposes_validation_only_as_a_number():
    view = ImproverView()
    public = [a for a in dir(view) if not a.startswith("_")]
    assert "validation" not in public
    summary = view.validation_score(load_state(initial_state()))
    assert summary.n == 40 and not hasattr(summary, "results")
