"""Stage 1 -- online exploration.

The current policy drives real discovery: it repeatedly picks one expansion
(a node of the discovery tree, and an edit the base agent offers there), the
base agent applies it, and the child is scored live -- one discovery call,
the expensive feedback Dream-RSI is trying to spend less of. Every decision
is logged in full: how many candidates there were, the features of the one
chosen, its outcome, and the guard verdict. That trace is what stage 2
turns into a simulator.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

import numpy as np

from core.loop import Harness, Snapshot
from core.proposers import ProposalContext, ScriptedProposer, from_strategy, failing
from dream_policy import Policy, features
from task.strategies import BASE_CIDS


@dataclass
class Node:
    key: str
    snap: Snapshot
    depth: int
    parent: str | None
    via: str | None

    @property
    def val(self) -> float:
        return self.snap.val.accuracy

    @property
    def n_handlers(self) -> int:
        return sum(1 for c in self.snap.state.cids() if c not in BASE_CIDS)

    def fail_by_family(self) -> dict[str, int]:
        return dict(Counter(r.family for r in failing(self.snap.steer)))


@dataclass
class DiscoveryTree:
    round: int
    root: str
    nodes: dict[str, Node] = field(default_factory=dict)
    transitions: list[dict] = field(default_factory=list)   # the full execution trace
    expanded: set[tuple[str, str]] = field(default_factory=set)

    def best(self) -> Node:
        return max(self.nodes.values(), key=lambda n: (n.val, -n.depth))


def explore(policy: Policy, root: Snapshot, harness: Harness, agent: ScriptedProposer,
            budget: int, rng: np.random.Generator, round_: int, on_call=None) -> DiscoveryTree:
    tree = DiscoveryTree(round_, root.state.key())
    tree.nodes[tree.root] = Node(tree.root, root, 0, None, None)
    calls = 0
    while calls < budget:
        cands, feats = [], []
        tried = {sid for _k, sid in tree.expanded}
        for node in tree.nodes.values():
            ctx = ProposalContext(node.snap.state, node.snap.steer, harness.view.steering)
            fbf = node.fail_by_family()
            for s in agent.all_candidates(ctx):
                if (node.key, s.sid) in tree.expanded:
                    continue
                cands.append((node, s))
                feats.append(features(node.val, fbf, node.depth, s, s.sid not in tried,
                                      node.n_handlers))
        if not cands:
            break
        i = policy.choose(np.array(feats), rng)
        node, s = cands[i]
        tree.expanded.add((node.key, s.sid))
        proposal = from_strategy(s, node.snap.steer, agent.name)
        trial = harness.try_proposal(node.snap, proposal)
        record = {"round": round_, "node": node.key, "depth": node.depth,
                  "strategy_id": s.sid, "edit_key": s.edit_key, "n_candidates": len(cands),
                  "features": [round(float(x), 3) for x in feats[i]],
                  "val_before": node.val, "guard": trial.verdict.as_dict(),
                  "fail_by_family": node.fail_by_family(), "n_handlers": node.n_handlers}
        if trial.candidate is not None:
            calls += 1                     # a scoring pass happened: that is the cost
            child = trial.candidate
            key = child.state.key()
            record.update(child=key, val_after=child.val.accuracy, live_call=True,
                          child_n_handlers=sum(1 for c in child.state.cids()
                                               if c not in BASE_CIDS),
                          child_fail_by_family=dict(Counter(
                              r.family for r in failing(child.steer))))
            if trial.verdict.ok and key not in tree.nodes:
                tree.nodes[key] = Node(key, child, node.depth + 1, node.key, s.sid)
        else:
            record.update(child=None, val_after=None, live_call=False)
        tree.transitions.append(record)
        if on_call:
            on_call(record, tree)
    return tree
