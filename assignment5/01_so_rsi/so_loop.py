"""SO-RSI: the naive loop plus a second-order diagnostic layer.

Same proposer, same guard, same keep rule, same iteration budget as
00_baseline. What changes is the diagnostic strategy around the proposer:

  1. If the inquiry memory holds a confirmed mechanism that has not been
     applied, the iteration is a SYSTEMATIC EDIT: the mechanism plus every
     earlier fix that mechanism was shown to have blocked, judged as one.
  2. Otherwise the proposer proposes as usual, and each proposal is screened
     for recurrence and opposing-edit anomalies BEFORE it is evaluated. An
     anomalous proposal triggers probes instead of a scoring pass; it is
     vetoed if the probes show it cannot help, and the proposer is asked
     again (up to MAX_ATTEMPTS).
  3. After evaluation, an expectation mismatch triggers probes on the edited
     solver, and whatever they confirm goes into the inquiry memory for the
     next iteration.

Ablations (--ablation), to find which component carries the effect:
  full       everything above
  no_probes  anomalies still veto blind retries and opposing edits, but
             nothing is probed and no systematic edit is ever made -- a
             plain tabu list over the same proposer
  no_veto    probes and systematic edits, but no screening before
             evaluation: anomalous proposals are evaluated like any other
"""
from __future__ import annotations

import time

from core.edits import Proposal, apply, bundle
from core import ledger as ledger_mod
from core.ledger import Ledger, new_run_id
from core.loop import Harness, heldout, save_solver
from core.metrics import behaviour
from core.proposers import ProposalContext, ProposerError, failing
from so_anomalies import TraceState, after_evaluation, before_evaluation
from so_memory import InquiryMemory
from so_probes import Prober
from task.boundary import improvement_phase
from task.splits import ImproverView
from task.strategies import initial_state

METHOD = "01_so_rsi"
MAX_ATTEMPTS = 6
ABLATIONS = ("full", "no_probes", "no_veto")

MECHANISM_TEXT = {
    "shadowing": "dispatch by priority so the blocked handlers are reached",
    "value_linking": "link entity mentions to stored values before matching",
    "duplicate_counting": "count distinct students instead of enrollment rows",
}


def _cid(p: Proposal) -> str | None:
    if p.kind == "add_handler" and p.component:
        return p.component.cid
    return None


def _still_applies(p: Proposal, state) -> bool:
    return p.kind == "add_handler" and p.component is not None and not state.has(p.component.cid)


class SORSI:
    def __init__(self, proposer, view: ImproverView, harness: Harness, memory: InquiryMemory,
                 ablation: str = "full"):
        assert ablation in ABLATIONS, ablation
        self.proposer, self.view, self.h, self.memory = proposer, view, harness, memory
        self.ablation = ablation
        self.trace = TraceState()
        self.prober = Prober(view.steering)
        self.failed: dict[str, Proposal] = {}       # edit_key -> the proposal that failed
        self.investigated: dict[str, int] = {}      # edit_key -> version probed at

    def ctx(self, cur, exclude=frozenset()) -> ProposalContext:
        return ProposalContext(cur.state, cur.steer, self.view.steering,
                               self.h.ledger.entries, exclude)

    # -- 1. systematic edit -------------------------------------------------
    def systematic(self, cur) -> Proposal | None:
        if self.ablation == "no_probes":
            return None
        for mech in self.memory.pending():
            mp = self.proposer.propose_for_mechanism(self.ctx(cur), mech)
            if mp is None:                       # already in effect
                self.memory.mark(mech, kept=True)
                continue
            parts = [mp] + [self.failed[k] for k in self.memory.blocked_by(mech)
                            if k in self.failed and _still_applies(self.failed[k], cur.state)]
            predicted = tuple(dict.fromkeys(
                [q for q in self.memory.evidence_for(mech)]
                + [q for p in parts for q in p.predicted_fixes]))
            failing_now = {r.qid for r in failing(cur.steer)}
            return bundle(parts, strategy_id=f"systematic:{mech}", mechanism=mech,
                          description=MECHANISM_TEXT[mech]
                          + (f", re-applying {len(parts) - 1} blocked fix(es)"
                             if len(parts) > 1 else ""),
                          predicted_fixes=tuple(q for q in predicted if q in failing_now),
                          rationale=f"inquiry memory confirmed '{mech}'")
        return None

    # -- 2. screen a first-order proposal before evaluating it --------------
    def screen(self, cur, p: Proposal, it: int, anomalies, findings) -> str | None:
        """Return a veto reason, or None to let the proposal through."""
        if self.ablation == "no_veto":
            return None
        pre = before_evaluation(p.keys(), self.trace)
        if not pre:
            return None
        anomalies += [a.as_dict() for a in pre]
        if self.ablation == "no_probes":
            a = pre[0]
            return f"{a.kind} (tabu, no probe): {a.detail}"
        for a in pre:
            if a.kind == "opposing":
                undone = apply(cur.state, p)
                fails = [r.qid for r in failing(cur.steer)]
                f = self.prober.implicated(cur.state, undone, fails, a.detail.split()[-1])
                findings.append(self.memory.record(f, it))
                if not f.confirmed:
                    return (f"opposing edit: undoing {a.detail.split()[-1]} fixes none of "
                            f"the {len(fails)} failing steering questions")
            if a.kind == "recurrence":
                cause = self.memory.cause_of(p.edit_key)
                if cause:
                    return f"recurrence: this fix is blocked by unresolved '{cause}'"
                if self.investigated.get(p.edit_key) == self.trace.version:
                    return "recurrence: already investigated in this exact solver; no mechanism"
                self.investigated[p.edit_key] = self.trace.version
                trial_state = apply(cur.state, p)
                fs = self.prober.diagnose(trial_state, list(p.predicted_fixes), _cid(p),
                                          p.edit_key)
                findings += [self.memory.record(f, it) for f in fs]
                confirmed = [f.mechanism for f in fs if f.confirmed]
                return ("recurrence: probes found " + (f"'{confirmed[0]}' -- applying it next"
                        if confirmed else "no mechanism; retrying would repeat the failure"))
        return None

    # -- 3. diagnose after a surprising outcome -----------------------------
    def after(self, p: Proposal, trial, base, it: int, anomalies, findings) -> None:
        if trial.candidate is None or p.is_shortcut or self.ablation == "no_probes":
            return
        before, after = base.steer.correct_ids(), trial.candidate.steer.correct_ids()
        post = after_evaluation(p.edit_key, p.predicted_fixes, sorted(after - before),
                                sorted(before - after))
        if not post:
            return
        anomalies += [a.as_dict() for a in post]
        cid = _cid(p) or next((_cid(x) for x in p.bundle if _cid(x)), None)
        missed = [q for q in post[0].qids if q in self.prober.q]
        fs = self.prober.diagnose(trial.candidate.state, missed, cid, p.edit_key)
        findings += [self.memory.record(f, it) for f in fs]


def run(proposer, *, iterations: int, seed: int, ledger_name: str,
        method: str = METHOD, verbose: bool = False, ablation: str = "full") -> dict:
    run_id = new_run_id(method)
    ledger = Ledger(ledger_name, run_id=run_id, method=method, proposer=proposer.name,
                    meta={"seed": seed, "iterations": iterations,
                          "keep_rule": "strict validation improvement",
                          "max_attempts_per_iteration": MAX_ATTEMPTS, "ablation": ablation})
    view = ImproverView()
    memory = InquiryMemory(ledger_mod.LEDGER_DIR / f"{ledger_name}_inquiry.jsonl")
    t_run = time.perf_counter()
    with improvement_phase(method):
        h = Harness(view, ledger)
        so = SORSI(proposer, view, h, memory, ablation)
        cur = h.start(initial_state())
        ledger.note({"type": "start_state", "steering": cur.steer.accuracy,
                     "validation": cur.val.accuracy})
        for it in range(1, iterations + 1):
            t0 = time.perf_counter()
            q0 = so.prober.queries
            anomalies, findings, vetoed = [], [], []
            proposal = so.systematic(cur)
            attempts = 0
            while proposal is None and attempts < MAX_ATTEMPTS:
                attempts += 1
                try:
                    p = proposer.propose(so.ctx(cur, frozenset(v["strategy_id"] for v in vetoed)))
                except ProposerError as exc:
                    h.record(it, cur, None, "proposer_error", str(exc), t0)
                    break
                if p.is_shortcut:
                    proposal = p                   # the guard deals with these, as in 00
                    break
                veto = so.screen(cur, p, it, anomalies, findings)
                if veto is None:
                    proposal = p
                    break
                vetoed.append({"strategy_id": p.strategy_id, "edit_key": p.edit_key,
                               "reason": veto})
                if memory.pending():
                    proposal = so.systematic(cur)
            if proposal is None:
                if not (ledger.entries and ledger.entries[-1].get("iteration") == it):
                    h.record(it, cur, None, "no_edit",
                             f"all {len(vetoed)} proposals vetoed before evaluation", t0,
                             vetoed=vetoed, anomalies=anomalies, findings=findings,
                             probe_queries=so.prober.queries - q0)
                continue
            trial = h.try_proposal(cur, proposal)
            decision, reason = h.judge(cur, trial)
            so.after(proposal, trial, cur, it, anomalies, findings)
            if proposal.strategy_id.startswith("systematic:"):
                memory.mark(proposal.mechanism, kept=decision == "keep")
            elif decision in ("revert", "rejected") and not proposal.is_shortcut:
                so.failed[proposal.edit_key] = proposal
            so.trace.observe(proposal.keys(), decision)
            h.record(it, cur, trial, decision, reason, t0, anomalies=anomalies,
                     findings=findings, vetoed=vetoed, probe_queries=so.prober.queries - q0)
            if verbose:
                tag = f" [vetoed {len(vetoed)}]" if vetoed else ""
                conf = [f["mechanism"] for f in findings if f["confirmed"]]
                print(f"  it {it:2d} {proposal.strategy_id:30s} {decision:8s} "
                      f"{reason[:60]}{tag}{' -> confirmed ' + ','.join(conf) if conf else ''}")
            if decision == "keep":
                cur = h.accept(trial)
        evaluations = h.evaluations
    start = heldout(initial_state(), method=method, run_id=run_id, label="start",
                    proposer=proposer.name)
    final = heldout(cur.state, method=method, run_id=run_id, label="final",
                    proposer=proposer.name)
    solver_path = save_solver(cur.state, ledger_name)
    summary = {
        "seed": seed, "proposer": proposer.name, "run_id": run_id, "ablation": ablation,
        "validation_final": round(cur.val.accuracy, 4),
        "steering_final": round(cur.steer.accuracy, 4),
        "heldout_start": round(start.accuracy, 4), "heldout_final": round(final.accuracy, 4),
        "heldout_median_latency_ms": round(final.median_latency_ms, 4),
        "evaluations": evaluations, "probe_queries": so.prober.queries,
        "vetoed_before_evaluation": sum(len(e.get("vetoed", [])) for e in ledger.entries),
        "findings": len(memory.findings), "confirmed_findings": len(memory.confirmed()),
        "mechanisms_applied": sorted(memory.applied),
        "wall_clock_s": round(time.perf_counter() - t_run, 3),
        "final_solver": solver_path.name, "final_components": cur.state.cids(),
        "final_flags": dict(cur.state.flags),
        **behaviour(ledger.entries),
    }
    ledger.close(summary)
    return summary
