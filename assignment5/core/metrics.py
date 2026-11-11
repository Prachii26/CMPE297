"""Behavioural metrics computed from a ledger, identically for every method.

SO-RSI's claim is about behaviour (less thrashing), not just score, so these
are counted from the raw iteration entries with one definition each:

  repeated_fix_attempts  an edit whose key already failed earlier in the run
  blind_repeats          ...and nothing has been kept since it failed, so it
                         is being retried in exactly the situation where it
                         already failed. This is thrashing in the strict sense.
  oscillations           an edit that undoes a change that was kept and is
                         still in effect (the paper's "opposing edits")
  zero_progress          a scored iteration whose validation score did not move
  guard_rejections       proposals the guard refused, by check

Shortcut proposals are excluded from the thrash counts (they are counted
under guard_rejections instead), so a method is not credited or blamed for
the proposer's occasional reward-hack attempt.
"""
from __future__ import annotations

from collections import Counter

from task.strategies import inverse_key


def behaviour(entries: list[dict]) -> dict:
    failed_at: dict[str, int] = {}
    active: set[str] = set()
    version = 0
    out = Counter()
    rejections = Counter()
    for e in entries:
        if e.get("type") != "iteration":
            continue
        decision = e.get("decision")
        out["iterations"] += 1
        out[decision] += 1
        if decision == "rejected":
            rejections[e.get("guard", {}).get("check", "?")] += 1
        if "edit_key" not in e or e.get("mechanism") == "shortcut":
            continue
        keys = e["edit_key"].split("+")
        if any(k in failed_at for k in keys):
            out["repeated_fix_attempts"] += 1
            if any(failed_at.get(k) == version for k in keys):
                out["blind_repeats"] += 1
        if any(inverse_key(k) in active for k in keys):
            out["oscillations"] += 1
        if "val_after" in e and e["val_after"] == e["val_before"]:
            out["zero_progress"] += 1
        if decision == "keep":
            version += 1
            for k in keys:
                active.discard(inverse_key(k))
                active.add(k)
                failed_at.pop(k, None)
        elif decision in ("revert", "rejected"):
            for k in keys:
                failed_at[k] = version
    result = {k: out.get(k, 0) for k in
              ("iterations", "keep", "revert", "rejected", "proposer_error",
               "repeated_fix_attempts", "blind_repeats", "oscillations", "zero_progress")}
    result["guard_rejections"] = dict(rejections)
    return result
