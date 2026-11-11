"""The evaluation boundary, enforced in code.

Three phases, tracked in a process-wide variable:
  idle       -- nothing running
  improving  -- an RSI loop is active; the held-out split is sealed
  final      -- the loop has finished; the held-out split may be read once
                per run, and every read is written to an audit ledger

The held-out split is reachable only through task/vault.py, and the vault
calls `assert_heldout_allowed()` first. That raises BoundaryViolation if:
  1. the phase is not `final` -- so no improver, proposer or probe running
     inside `improvement_phase()` can read it, whatever it imports; or
  2. any frame on the call stack is generated code -- a solver ("<solver...>")
     or an AIDE2 search-control module ("<control...>") -- or lives in a
     proposer module. This closes the one gap the phase check leaves: the
     final phase runs the solver over the held-out questions, so a solver
     that tried to read the vault *during* that scoring would otherwise be
     inside the final phase.

The guard (guard/guard.py) adds a static layer on top: an edit that so much
as names the vault or the held-out split is rejected before it runs.
"""
from __future__ import annotations

import sys
from contextlib import contextmanager

GENERATED_PREFIXES = ("<solver", "<control")
PROPOSER_MARKERS = ("proposers.py", "llm_proposer")


class BoundaryViolation(RuntimeError):
    """Something on the improvement side tried to reach the held-out split."""


_phase = "idle"
_phase_owner = ""


def current_phase() -> str:
    return _phase


@contextmanager
def improvement_phase(owner: str):
    global _phase, _phase_owner
    if _phase != "idle":
        raise BoundaryViolation(f"cannot start improving inside phase '{_phase}'")
    _phase, _phase_owner = "improving", owner
    try:
        yield
    finally:
        _phase, _phase_owner = "idle", ""


@contextmanager
def final_phase(owner: str):
    global _phase, _phase_owner
    if _phase != "idle":
        raise BoundaryViolation(
            f"final evaluation requested during phase '{_phase}' ({_phase_owner}); "
            "the held-out split opens only after the improvement loop has ended")
    _phase, _phase_owner = "final", owner
    try:
        yield
    finally:
        _phase, _phase_owner = "idle", ""


def _offending_frame() -> str | None:
    frame = sys._getframe(1)
    while frame is not None:
        name = frame.f_code.co_filename
        if name.startswith(GENERATED_PREFIXES):
            return name
        if any(marker in name for marker in PROPOSER_MARKERS):
            return name
        frame = frame.f_back
    return None


def assert_heldout_allowed() -> None:
    if _phase != "final":
        raise BoundaryViolation(
            f"held-out split requested during phase '{_phase}'"
            + (f" (owner: {_phase_owner})" if _phase_owner else "")
            + "; it is readable only inside final_phase()")
    offender = _offending_frame()
    if offender:
        raise BoundaryViolation(
            f"held-out split requested from {offender}; generated code and proposers "
            "may never read it, even during final scoring")
