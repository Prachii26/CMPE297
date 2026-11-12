"""Stage 2 -- replay simulator construction.

Recorded discovery trees become a reusable simulator pool: a graph whose
nodes are solver states (by content hash) and whose edges are the
expansions that were actually run, each with its recorded outcome. Trees
from different rounds merge wherever they reached the same solver, so the
pool covers more of the search space every round.

The simulator answers "what happens if this policy explores from here?"
with zero live calls -- but ONLY over the realised search space. An
expansion nobody ran has no recorded outcome and is not available in a
dream. That restriction is the paper's ("a replay simulator over the
realized search space"), and it is the method's main bias: a policy can
only be rewarded for preferring things that were tried.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np

from dream_online import DiscoveryTree
from dream_policy import FEATURES, Policy, features, strategy


@dataclass
class SimNode:
    val: float
    fail_by_family: dict[str, int]
    n_handlers: int = 0


@dataclass
class ReplaySimulator:
    nodes: dict[str, SimNode] = field(default_factory=dict)
    edges: dict[str, dict[str, str]] = field(default_factory=lambda: defaultdict(dict))
    roots: list[str] = field(default_factory=list)
    steps_simulated: int = 0

    def add_tree(self, tree: DiscoveryTree) -> None:
        for n in tree.nodes.values():
            self.nodes.setdefault(n.key, SimNode(n.val, n.fail_by_family(), n.n_handlers))
        for t in tree.transitions:
            if t.get("live_call") and t["guard"]["ok"] and t["child"]:
                self.edges[t["node"]][t["strategy_id"]] = t["child"]
                self.nodes.setdefault(t["child"], SimNode(t["val_after"],
                                                          t["child_fail_by_family"],
                                                          t["child_n_handlers"]))
        if tree.root not in self.roots:
            self.roots.append(tree.root)

    def support(self) -> np.ndarray:
        """Which policy features actually vary across recorded expansions.
        A feature that is constant over the pool (e.g. is_mechanism when no
        mechanism was ever tried) cannot change any dream score, so the
        simulator carries no evidence about its weight. novelty and depth
        always vary inside a rollout."""
        rows = []
        for key, out in self.edges.items():
            node = self.nodes[key]
            for sid in out:
                rows.append(features(node.val, node.fail_by_family, 0, strategy(sid),
                                     True, node.n_handlers))
        if not rows:
            return np.zeros(len(FEATURES), dtype=bool)
        varies = np.ptp(np.array(rows), axis=0) > 0
        varies[FEATURES.index("novelty")] = varies[FEATURES.index("depth")] = True
        return varies

    @property
    def n_edges(self) -> int:
        return sum(len(v) for v in self.edges.values())

    def rollout(self, policy: Policy, root: str, steps: int,
                rng: np.random.Generator) -> list[float]:
        """Best validation after each simulated expansion."""
        reached = {root: 0}
        used: set[tuple[str, str]] = set()
        tried: set[str] = set()
        best = self.nodes[root].val
        curve = []
        for _ in range(steps):
            cands, feats = [], []
            for key, depth in reached.items():
                node = self.nodes[key]
                for sid, child in self.edges.get(key, {}).items():
                    if (key, sid) in used:
                        continue
                    cands.append((key, sid, child, depth))
                    feats.append(features(node.val, node.fail_by_family, depth,
                                          strategy(sid), sid not in tried, node.n_handlers))
            if not cands:
                break
            key, sid, child, depth = cands[policy.choose(np.array(feats), rng)]
            used.add((key, sid))
            tried.add(sid)
            reached.setdefault(child, depth + 1)
            best = max(best, self.nodes[child].val)
            curve.append(best)
            self.steps_simulated += 1
        return curve

    def dream_score(self, policy: Policy, steps: int, reps: int, seed: int) -> float:
        """Mean area under the best-gain curve over every root in the pool.
        Common random numbers (fixed seed) so policies are compared fairly."""
        rng = np.random.default_rng(seed)
        scores = []
        for root in self.roots:
            base = self.nodes[root].val
            for _ in range(reps):
                curve = self.rollout(policy, root, steps, rng)
                gains = [b - base for b in curve] + [curve[-1] - base if curve else 0.0] \
                    * (steps - len(curve))
                scores.append(float(np.mean(gains)) if gains else 0.0)
        return float(np.mean(scores)) if scores else 0.0
