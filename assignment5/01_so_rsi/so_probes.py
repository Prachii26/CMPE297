"""Lightweight diagnostic probes (SO-RSI, signal 2).

A probe tests a hypothesis about WHY a fix did not work; it does not apply
a fix. Each one is an intervention on steering questions only: change one
thing in a throwaway copy of the solver, re-run the handful of questions in
question, and see whether the change explains the failure. A probe never
touches validation and never touches the held-out split; it costs a few
SQL executions, counted in `queries`.

  dispatch   Was the new handler ever reached? Trace which handler fired;
             call the new handler directly; then flip dispatch to priority
             order and re-run. Confirmed if the handler is right when
             reached and the flip makes it reached.
  values     Did the SQL compare against a value that is not in the
             database? Collect quoted literals; check them against stored
             values; flip entity linking on and re-run.
  counts     Did COUNT(*) count joined rows instead of entities? Flip
             distinct counting on and re-run.
  implicated For an opposing edit: does undoing the kept change fix any
             steering question that currently fails? If not, the kept change
             is not the cause and undoing it is a symptom-driven guess.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from task.db import schema_info
from task.evaluate import results_match, run_sql
from task.solver_state import SolverState, load_state

_INFO = schema_info()
KNOWN_VALUES = set(_INFO["departments"] + _INFO["dept_codes"] + _INFO["subjects"]
                   + _INFO["course_codes"] + _INFO["terms"])


@dataclass
class Finding:
    probe: str
    hypothesis: str
    confirmed: bool
    mechanism: str | None              # shadowing | value_linking | duplicate_counting | None
    qids: tuple[str, ...]
    evidence: dict = field(default_factory=dict)
    blocked_edit: str | None = None    # the fix this cause blocked, to re-apply later

    def as_dict(self) -> dict:
        return {"probe": self.probe, "hypothesis": self.hypothesis,
                "confirmed": self.confirmed, "mechanism": self.mechanism,
                "qids": list(self.qids), "evidence": self.evidence,
                "blocked_edit": self.blocked_edit}


class Prober:
    def __init__(self, steering: list[dict]) -> None:
        self.q = {q["qid"]: q for q in steering}
        self.queries = 0

    def _correct(self, solver, qid: str) -> bool:
        q = self.q[qid]
        self.queries += 1
        try:
            return results_match(run_sql(solver.solve(q["question"])), q["gold_result"],
                                 q["ordered"])
        except Exception:
            return False

    def _fired(self, solver, qid: str) -> tuple[str, str]:
        try:
            return solver.trace(self.q[qid]["question"])
        except Exception as exc:
            return "error", str(exc)

    # ------------------------------------------------------------------
    def dispatch(self, state: SolverState, qids: list[str], expected_cid: str,
                 edit_key: str) -> Finding:
        solver = load_state(state, "probe")
        fn = solver.handlers.get(expected_cid)
        fired = {qid: self._fired(solver, qid)[0] for qid in qids}
        bypassed = [qid for qid in qids if fired[qid] != expected_cid]
        direct_ok = []
        if fn is not None:
            for qid in bypassed:
                text = self.q[qid]["question"]
                if solver.flags.get("LINK_ENTITIES"):
                    text = solver.link(text)
                try:
                    sql = fn(text)
                except Exception:
                    sql = None
                self.queries += 1
                try:
                    ok = bool(sql) and results_match(run_sql(sql), self.q[qid]["gold_result"],
                                                     self.q[qid]["ordered"])
                except Exception:
                    ok = False
                if ok:
                    direct_ok.append(qid)
        flipped = load_state(state.with_flag("DISPATCH", "priority"), "probe")
        unblocked = [qid for qid in bypassed if self._correct(flipped, qid)]
        confirmed = bool(bypassed) and bool(unblocked) and state.flag("DISPATCH") != "priority"
        return Finding(
            "dispatch", f"{expected_cid} never fires because an earlier handler claims "
            "its questions first", confirmed, "shadowing" if confirmed else None, tuple(qids),
            {"fired_instead": {q: fired[q] for q in bypassed},
             "correct_when_called_directly": direct_ok, "fixed_by_priority_dispatch": unblocked},
            blocked_edit=edit_key if confirmed else None)

    def values(self, state: SolverState, qids: list[str], edit_key: str) -> Finding:
        solver = load_state(state, "probe")
        unknown: dict[str, list[str]] = {}
        for qid in qids:
            _h, sql = self._fired(solver, qid)
            lits = [v for v in re.findall(r"'((?:[^']|'')*)'", sql or "")
                    if not v.replace(".", "").isdigit()]
            bad = [v for v in lits if v not in KNOWN_VALUES]
            if bad:
                unknown[qid] = bad
        linked = load_state(state.with_flag("LINK_ENTITIES", True), "probe")
        fixed = [qid for qid in unknown if self._correct(linked, qid)]
        confirmed = bool(fixed) and not state.flag("LINK_ENTITIES")
        return Finding(
            "values", "the SQL compares against a surface form that is not a stored value",
            confirmed, "value_linking" if confirmed else None, tuple(qids),
            {"literals_not_in_database": unknown, "fixed_by_entity_linking": fixed},
            blocked_edit=edit_key if confirmed else None)

    def counts(self, state: SolverState, qids: list[str], edit_key: str) -> Finding:
        solver = load_state(state, "probe")
        counting = [qid for qid in qids if "COUNT(*)" in (self._fired(solver, qid)[1] or "")]
        distinct = load_state(state.with_flag("COUNT_DISTINCT", True), "probe")
        fixed = [qid for qid in counting if self._correct(distinct, qid)]
        confirmed = bool(fixed) and not state.flag("COUNT_DISTINCT")
        return Finding(
            "counts", "COUNT(*) counts joined enrollment rows, not distinct students",
            confirmed, "duplicate_counting" if confirmed else None, tuple(qids),
            {"count_star_queries": counting, "fixed_by_distinct": fixed},
            blocked_edit=edit_key if confirmed else None)

    def implicated(self, state: SolverState, undone: SolverState, failing: list[str],
                   kept_key: str) -> Finding:
        solver = load_state(undone, "probe")
        fixed = [qid for qid in failing if self._correct(solver, qid)]
        return Finding(
            "implicated", f"kept change {kept_key} causes some current steering failures",
            bool(fixed), None, tuple(failing), {"fixed_by_undoing": fixed})

    def diagnose(self, state: SolverState, qids: list[str], expected_cid: str | None,
                 edit_key: str) -> list[Finding]:
        """Run every probe whose precondition holds; refuted ones are kept
        too -- negative evidence belongs in the inquiry memory as well."""
        if not qids:
            return []
        out = []
        if expected_cid and state.has(expected_cid):
            out.append(self.dispatch(state, qids, expected_cid, edit_key))
        out.append(self.values(state, qids, edit_key))
        out.append(self.counts(state, qids, edit_key))
        return out
