"""Structural anomaly detection over the trace history (SO-RSI, signal 1).

The paper monitors execution traces passively for three structural
anomalies and uses them to trigger an investigation. Ours watch the ledger:

  recurrence            the same fix is attempted again after it already
                        failed, with nothing kept in between
  opposing edit         a proposal would undo a change that was kept and is
                        still in effect
  expectation mismatch  an edit predicted it would fix a set of steering
                        questions and the outcome contradicts that: it fixed
                        under half of them, or broke some that passed

Recurrence and opposing edits are checked BEFORE a proposal is evaluated,
so investigating costs a handful of probe queries instead of a full scoring
pass. Expectation mismatch can only be checked after.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from task.strategies import inverse_key


@dataclass(frozen=True)
class Anomaly:
    kind: str                 # recurrence | opposing | expectation_mismatch
    edit_key: str
    detail: str
    qids: tuple[str, ...] = ()

    def as_dict(self) -> dict:
        return {"kind": self.kind, "edit_key": self.edit_key, "detail": self.detail,
                "qids": list(self.qids)}


@dataclass
class TraceState:
    """What the detector remembers about the run: which edit keys are in
    effect, and at which solver version each failed edit last failed."""
    version: int = 0
    active: set[str] = field(default_factory=set)
    failed_at: dict[str, int] = field(default_factory=dict)
    failed_edit_at: dict[frozenset, int] = field(default_factory=dict)

    def observe(self, keys: list[str], decision: str) -> None:
        if decision == "keep":
            self.version += 1
            for k in keys:
                self.active.discard(inverse_key(k))
                self.active.add(k)
                self.failed_at.pop(k, None)
        elif decision in ("revert", "rejected"):
            for k in keys:
                self.failed_at[k] = self.version
            self.failed_edit_at[frozenset(keys)] = self.version


def before_evaluation(keys: list[str], trace: TraceState) -> list[Anomaly]:
    found = []
    if keys and trace.failed_edit_at.get(frozenset(keys)) == trace.version:
        found.append(Anomaly("recurrence", "+".join(keys),
                             "this edit already failed and nothing has been kept since"))
    for k in keys:
        inv = inverse_key(k)
        if inv in trace.active:
            found.append(Anomaly("opposing", k, f"would undo kept change {inv}"))
    return found


def after_evaluation(edit_key: str, predicted: tuple[str, ...], fixed: list[str],
                     regressed: list[str]) -> list[Anomaly]:
    if not predicted:
        return []
    hit = set(predicted) & set(fixed)
    missed = tuple(q for q in predicted if q not in hit)
    if regressed or len(hit) * 2 < len(predicted):
        detail = (f"predicted {len(predicted)} fixes, got {len(hit)}"
                  + (f", broke {len(regressed)}" if regressed else ""))
        return [Anomaly("expectation_mismatch", edit_key, detail, missed + tuple(regressed))]
    return []
