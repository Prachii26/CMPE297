"""Stage 3 -- dreaming-based policy improvement.

Candidate policies are evaluated off-policy against the replay simulator
instead of live: a cross-entropy search over the seven policy weights,
each candidate scored by simulated rollouts from every root in the pool.
The best candidate replaces the current policy only if it beats it in the
same dreams (same random numbers) by a margin -- a noisy dream should not
redeploy a worse policy.

Cost: zero discovery calls. The work is simulated steps, counted and
reported, plus wall-clock time.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from dream_policy import FEATURES, Policy
from dream_simulator import ReplaySimulator

CEM_ITERS = 3
POPULATION = 24
ELITE = 6
SIGMA0 = 0.8
REPS = 4
ADOPT_MARGIN = 0.002


@dataclass
class DreamResult:
    policy: Policy
    adopted: bool
    current_score: float
    best_score: float
    candidates_evaluated: int
    steps_simulated: int
    searched: list = None


def improve(current: Policy, sim: ReplaySimulator, steps: int, seed: int,
            round_: int, support_only: bool = False) -> DreamResult:
    """support_only (POST-HOC, the dream_support arm): search only the
    weights the pool has evidence about; leave the rest where they are."""
    rng = np.random.default_rng(seed)
    start_steps = sim.steps_simulated
    current_score = sim.dream_score(current, steps, REPS, seed)
    mean = current.theta.copy()
    search = current.active & sim.support() if support_only else current.active
    sigma = np.where(search, SIGMA0, 0.0)   # inactive weights stay pinned
    best_theta, best_score, evaluated = current.theta.copy(), current_score, 0
    for _ in range(CEM_ITERS):
        # draw noise only for the searched weights, so adding an inactive
        # feature never changes the random stream of a policy that ignores it
        z = np.zeros((POPULATION, len(mean)))
        z[:, search] = rng.standard_normal((POPULATION, int(search.sum())))
        pop = mean + sigma * z
        scores = np.array([sim.dream_score(Policy(t, current.temperature,
                                                  active=current.active), steps, REPS, seed)
                           for t in pop]) if search.any() else np.zeros(POPULATION)
        evaluated += POPULATION
        elite = pop[np.argsort(scores)[-ELITE:]]
        mean = elite.mean(axis=0)
        sigma = np.where(search, elite.std(axis=0) + 0.05, 0.0)
        if scores.max() > best_score:
            best_score, best_theta = float(scores.max()), pop[int(scores.argmax())].copy()
    adopted = best_score > current_score + ADOPT_MARGIN
    policy = (Policy(best_theta, current.temperature, f"dream-r{round_}", current.active.copy())
              if adopted else current)
    return DreamResult(policy, adopted, current_score, best_score, evaluated,
                       sim.steps_simulated - start_steps,
                       [f for f, s in zip(FEATURES, search) if s])
