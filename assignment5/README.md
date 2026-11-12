# Assignment 5 — Three October-2026 RSI methods on one NL2SQL task

**Demo video:** YOUTUBE_VIDEO_LINK

Three recursive-self-improvement methods from section 10 of the course map,
rebuilt as progressive codelabs on a single problem: natural language to SQL
over a seeded university database. Each method changes a different object,
and each is measured against the same naive baseline on the same questions,
with the same guard and the same held-out boundary.

## Comparison

| | **changed object** | **feedback signal** | **inheritance** | **evaluation** | **cost** (per run) |
|---|---|---|---|---|---|
| **00 Naive RSI** (control) | the solver: its handlers and flags | which steering questions fail; one validation number per candidate | the current solver only — keep or revert, no memory | keep iff validation strictly improves; held-out once, after the loop | 20 iterations ≈ 19.6 full scorings; < 2 s |
| **01 SO-RSI** | the **diagnostic strategy**: how a failure is investigated before the next edit | steering traces, three anomaly signals, and outcomes of probes (interventions on steering only) | the solver **plus an inquiry memory** of confirmed and refuted causes, carried across rounds | same keep rule as 00; held-out once, after | ≈ 19.2 full scorings + ~38 steering probe queries; 2–3 s |
| **02 Dream-RSI** | the **exploration policy**: which expansion gets the next live discovery call | off-policy dream scores from a replay simulator; live discovery outcomes | policy weights, the **simulator pool** of every recorded discovery tree, and the best solver found | a dreamed policy is redeployed only if it beats the current one in the same dreams; solver selected on validation; held-out once, after | 60 live scorings + ~75k simulated steps (3–7 s, zero live calls); ~12 s |
| **03 AIDE²** | the **harness code**: the inner agent's search-and-control module | a single hidden score per variant (validation, mean of 3 inner runs) plus inner cost | the winning control module, one survivor per generation, with **lineage** | hidden evaluation the outer loop cannot see, **enforced in code**; held-out once, after | 25 benchmarks × 3 inner runs × ≤ 24 steering scorings, + 75 hidden scorings; ~90 s |

## Held-out results

The starting solver scores **0.250** on all three splits (inside the 15–55%
band the brief requires; the question mix was not adjusted).

| method | proposer | runs | held-out start | **held-out final** |
|---|---|---|---|---|
| 00 Naive RSI | scripted | 5 seeds × 20 it | 0.250 | **0.520 ± 0.154** |
| 00 Naive RSI | **live LLM** — `gemini-3.5-flash` | 1 seed × 8 calls | 0.250 | **0.575** |
| 01 SO-RSI | scripted | 5 seeds × 20 it (same seeds as 00) | 0.250 | **0.940 ± 0.108** |
| 02 Dream-RSI | scripted base agent | 10 seeds × 10 rounds × 6 calls | 0.250 | **0.863 ± 0.227** |
| 02 Recursive Fixed Exploration (its baseline) | scripted base agent | same 10 seeds | 0.250 | 0.930 ± 0.103 |
| 03 AIDE² | scripted outer, fixed scripted inner | 3 outer seeds × 8 generations | 0.325 (gen-0 inner agent) | **0.542 ± 0.038** |

**Which runs were live:** exactly one — `00_baseline` with the Gemini
proposer, 8 calls, transcript in
[`docs/ledgers/00_baseline_llm_transcript.jsonl`](docs/ledgers/00_baseline_llm_transcript.jsonl).
Two of its 8 calls returned HTTP 503 and were logged as `proposer_error`; the
run did not fall back to the scripted proposer. Every other run used the
scripted proposer, offline and deterministic. Every ledger entry names its
proposer.

The rows are not a ranking: each method spends a different budget on a
different object (see the cost column). The comparison that matters is each
method against its own control.

---

## 01 · SO-RSI — [details](01_so_rsi/README.md)

**SOURCE CLAIM (arXiv 2610.05701).** Standard RSI "repeatedly patches
surface-level parameters in response to immediate failure symptoms, often
leading to trial-and-error thrashing". SO-RSI monitors traces for
recurrence, opposing edits and expectation mismatch, runs lightweight
diagnostic probes, keeps a persistent inquiry memory, and makes systematic
edits. Reported: +21.8 and +25.8 points held-out over Naive RSI on Lean 4 and
Verus under matched 24-hour budgets; it "substantially suppresses failure
recurrence and eliminates unproductive zero-progress optimization loops".

**OUR LAPTOP ADAPTATION.** All four components, on the same proposer, guard,
keep rule and iteration budget as 00. Probes are four hand-written
interventions on steering questions (dispatch, values, counts, implicated);
a confirmed cause becomes one bundled edit with the fixes it blocked.
*Simplified:* the probes cover exactly the three root causes our testbed
contains — the paper's investigation is open-ended. Budget is matched in
iterations and scorings, not hours.

**OBSERVED RESULT.** Held-out **0.520 → 0.940** on average over 5 seeds,
higher on every seed, at equal evaluations. Blind repeats **2.2 → 0**,
oscillations **1.0 → 0**, zero-progress iterations **10.4 → 3.4** of 20. The
paper's direction reproduced on score and behaviour; "eliminates
zero-progress loops" did not — they fell by two thirds. An ablation shows the
gain comes from diagnosis: a plain tabu list reached only 0.615. Our effect
is larger than the paper's because our probes were written for our causes.

## 02 · Dream-RSI — [details](02_dream_rsi/README.md)

**SOURCE CLAIM (arXiv 2609.14858).** "Accumulated discovery history can act
as a replay simulator over the realized search space"; dreaming in it gives
"low-cost off-policy feedback to evaluate and refine exploration policies";
the improved policy is redeployed and the pool grows. Reported across 9 tasks
in 4 domains: "competitive quality" and "improves discovery efficiency in
several settings".

**OUR LAPTOP ADAPTATION.** Three separate stages: online exploration with
full traces, a replay simulator over a state graph of every expansion actually
run, and cross-entropy search over a 7-weight linear exploration policy
scored by simulated rollouts. Compared against Recursive Fixed Exploration —
same base agent, budget, starting policy and random numbers. *Simplified:* a
linear policy, one task, 60 live calls per run.

**OBSERVED RESULT.** **Half reproduced.** On 7 of 10 seeds Dream-RSI reached
fixed exploration's final level with **8.6 ± 6.4 fewer live calls (~18%)**;
the median run hit 100% validation by 42 calls against 84% for fixed. On 3 of
10 it never got there, so mean held-out was *lower* (0.863 vs 0.930) and
twice as variable. The ledgers show why: each failing run's dreamed policy
stopped exploring something it needed, by three different routes, and a
replay simulator can only replay what the policy chose to do. Two post-hoc
fixes, reported separately, each closed one route and not the others.

## 03 · AIDE² — [details](03_aide2/README.md)

**SOURCE CLAIM (arXiv 2609.26457).** An agent that "proposes changes to its
own code, benchmarks modified versions of itself … and keeps the changes that
perform best on hidden evaluations"; seven successive improvements in an
8-day run, generalising to four held-out benchmarks; reward hacking "falls
from 55% to 32% during the run", unoptimised for.

**OUR LAPTOP ADAPTATION.** The inner agent is a tree search over solver
repairs; its search-and-control module (branching factor, node selection,
stopping rule, strategy ordering) is generated source that the outer loop
rewrites one slot at a time, benchmarks on the validation split, and keeps if
it wins. The hidden boundary is enforced four ways in code — closure,
steering-only view, a runtime seal, and a guard on the control source. The
inner proposer is fixed across variants. *Simplified:* rewrites come from a
written library, not a model; 8 generations, one task.

**OBSERVED RESULT.** Hidden and held-out **0.325 → 0.542 ± 0.038** over 8
generations in 3 lineages, each with 3–4 kept rewrites; every lineage made
its biggest jump by replacing the strategy ordering, which routes around the
shadowing bug without knowing it exists. Held-out matched hidden exactly (no
overfitting — but our balanced splits make that a weak transfer test). The
reward-hacking claim was **not testable**: only 1 of 75 variants ever tried a
hack.

---

## The task

[`task/`](task/) — a university course-enrollment database with 8 tables
(students, courses, sections, enrollments, instructors, departments, terms,
grades), built in memory from `numpy.random.default_rng(42)`, and 120
questions: 20 families (simple selects, joins, aggregates, group-bys,
ordering, subqueries) × 6 instances. Each family has a canonical phrasing
and a user-style one (`computer engineering`, `cmpe120`, `fall 2024`), and
every split holds one of each for every family: steering 40, validation 40,
held-out 40.

Metric: exact result-set match — as a set, or as a list when the question
asks for an order — plus median latency. The starting solver
([`task/solver.py`](task/solver.py)) is a template matcher with three hidden
problems that interact: a generic handler that shadows anything appended
after it, case-sensitive literals that miss user-style entity names, and
`COUNT(*)` over enrollments where students retake courses. Every fix
together reaches 100% (pinned by a test), so the headroom is real.

**The held-out boundary** is enforced in code
([`task/boundary.py`](task/boundary.py), [`task/vault.py`](task/vault.py)):
the split is sealed while any improvement loop runs; generated solver or
control code and proposer modules are refused even during final scoring;
the vault is the only reader and appends every read to
[`docs/ledgers/heldout_access.jsonl`](docs/ledgers/heldout_access.jsonl). It
holds 140 reads, every one after a loop ended. Improvers see validation only
as one number per candidate.

## The guard — [details](guard/README.md)

Ported from `assignment2/partC` (JS) to Python and extended. Rejects, with a
logged reason: held-out access, evaluator or metric tampering, hardcoded or
memorised answers, a solver gutted to return early, and narrowing the
question set. 18 tests feed it gaming attempts and legitimate edits and
assert the verdict and the reason.

**It fired on real proposals, not only in tests** — 41 times across the
reported runs: hardcoded 27, held-out access 7, narrowing 4, evaluator patch
2, gutted solver 1. The scripted proposer includes six known reward hacks at a
6% rate for exactly this reason. The live LLM never attempted one.

**Checks that fired only in tests**, and are therefore unproven in practice:
the in-source metric monkeypatch and runtime integrity fingerprint, database
access, the steering/validation divergence check, the dynamic denominator
check, and the AIDE² control-module scan. The gutted-solver check leaked a
stub on its first version; [docs/guard_calibration.md](docs/guard_calibration.md)
records the noise problem and the side-by-side fix.

## Run everything

Windows PowerShell, from the repo root:

```powershell
cd assignment5
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

.\.venv\Scripts\python.exe -m pytest                         # 74 offline tests
.\.venv\Scripts\python.exe 00_baseline\run.py                # ~10 s
.\.venv\Scripts\python.exe 01_so_rsi\run.py                  # ~15 s (needs 00 first)
.\.venv\Scripts\python.exe 01_so_rsi\run.py --ablation no_probes
.\.venv\Scripts\python.exe 01_so_rsi\run.py --ablation no_veto
.\.venv\Scripts\python.exe 02_dream_rsi\run.py               # ~8 min, 10 seeds x 4 arms
.\.venv\Scripts\python.exe 03_aide2\run.py                   # ~5 min

# optional live proposer (one method, budgeted)
$env:GEMINI_API_KEY = "<your key>"
.\.venv\Scripts\python.exe 00_baseline\run.py --proposer llm --seeds 0 --iterations 8
```

Every full method run finishes in under 10 minutes on a laptop. Python 3.11;
dependencies are numpy, pytest and rich; nothing is downloaded and nothing
touches the network except the optional LLM proposer.

## Layout

```
task/          database, questions, evaluator, boundary, vault, solver state, repair library
core/          shared loop, proposers (scripted + LLM), ledger, behavioural metrics
guard/         reward-hacking guard + tests
00_baseline/   naive RSI (the control)
01_so_rsi/     anomalies, probes, inquiry memory, loop, ablations
02_dream_rsi/  online exploration, replay simulator, dreaming, fixed-exploration baseline
03_aide2/      control module, inner agent, hidden benchmark, outer loop
docs/ledgers/  raw append-only ledgers from every reported run, inquiry memories,
               LLM transcript, held-out access audit
docs/results/  per-method JSON summaries      docs/solvers/  final solvers and control modules
DECISIONS.md   every judgement call, one line each       PROMPTS.md  every prompt, verbatim
```

## References

- Course map, section 10: <https://raw.githubusercontent.com/dlmastery/simple-coding-harness/main/COURSE-MAP.md>
- Research studio: <https://raw.githubusercontent.com/dlmastery/simple-coding-harness/main/10_research_studio/README.md>
- Paper summaries: <https://raw.githubusercontent.com/dlmastery/simple-coding-harness/main/12_october_2026_papers/PAPER_SUMMARIES.md> — covers SO-RSI; the Dream-RSI and AIDE² source claims are quoted from their arXiv abstracts
- arXiv [2610.05701](https://arxiv.org/abs/2610.05701) (SO-RSI) · [2609.14858](https://arxiv.org/abs/2609.14858) (Dream-RSI) · [2609.26457](https://arxiv.org/abs/2609.26457) (AIDE²)
- Guard and ledger lineage: [`assignment2/partC`](../assignment2/partC/)
