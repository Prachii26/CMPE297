"""A proposed edit, and how it is applied to a SolverState.

Every proposal records which proposer made it (`proposer`), so no ledger
entry can be attributed to the wrong source, and what it predicts it will
fix (`predicted_fixes`), which is what SO-RSI's expectation-mismatch check
compares against.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

from task.solver_state import Component, SolverState


@dataclass(frozen=True)
class Proposal:
    strategy_id: str
    kind: str                       # add_handler | set_flag | remove_handler | replace_solver
                                    # (restrict_questions | patch_file exist only to be rejected)
    mechanism: str
    description: str
    proposer: str
    edit_key: str
    family: str | None = None
    component: Component | None = None
    position: str = "append"
    flag: str | None = None
    value: object = None
    remove_cid: str | None = None
    source: str | None = None       # replace_solver
    path: str | None = None         # patch_file
    patch: str | None = None        # patch_file
    restrict: dict | None = None    # restrict_questions
    predicted_fixes: tuple[str, ...] = ()
    rationale: str = ""
    bundle: tuple["Proposal", ...] = field(default=())

    @property
    def is_shortcut(self) -> bool:
        return self.mechanism == "shortcut"

    def keys(self) -> list[str]:
        """Every edit key this proposal applies (a bundle applies several)."""
        return [k for p in self.bundle for k in p.keys()] if self.bundle else [self.edit_key]

    def summary(self) -> dict:
        d = {"strategy_id": self.strategy_id, "kind": self.kind, "mechanism": self.mechanism,
             "edit_key": self.edit_key, "family": self.family, "position": self.position,
             "description": self.description, "proposer": self.proposer,
             "predicted_fixes": list(self.predicted_fixes)}
        if self.bundle:
            d["bundle"] = [p.strategy_id for p in self.bundle]
        if self.rationale:
            d["rationale"] = self.rationale
        return d


def apply(state: SolverState, proposal: Proposal) -> SolverState:
    """Pure: returns the new state, executes nothing."""
    if proposal.bundle:
        for part in proposal.bundle:
            state = apply(state, part)
        return state
    if proposal.kind == "add_handler":
        return state.with_component(proposal.component, proposal.position)
    if proposal.kind == "set_flag":
        return state.with_flag(proposal.flag, proposal.value)
    if proposal.kind == "remove_handler":
        return state.without(proposal.remove_cid)
    if proposal.kind == "replace_solver":
        return replace(state, override=proposal.source)
    raise ValueError(f"edit kind '{proposal.kind}' cannot be applied to a solver")


def bundle(parts: list[Proposal], *, strategy_id: str, mechanism: str, description: str,
           predicted_fixes: tuple[str, ...], rationale: str) -> Proposal:
    """Several edits applied and judged as one (SO-RSI's systematic edit)."""
    return Proposal(strategy_id=strategy_id, kind="bundle", mechanism=mechanism,
                    description=description, proposer=parts[0].proposer,
                    edit_key="+".join(p.edit_key for p in parts), bundle=tuple(parts),
                    predicted_fixes=predicted_fixes, rationale=rationale)
