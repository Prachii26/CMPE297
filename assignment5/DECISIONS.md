# Decisions

One line per call made without asking, in the order they were made.

1. Folder is `assignment5` (lowercase): the repo root has `assignment1`, `assignment2`, `assignment3`.
2. Shared code lives in `core/` (loop, proposers, ledger, metrics) — not in the brief's tree, but `00_baseline/` etc. start with digits and cannot be imported as packages.
3. Method-local modules carry a method prefix (`so_*`, `dream_*`, `aide_*`) so one pytest process can import all four methods without name collisions.
4. Task tests live in `task/tests/`; guard tests in `guard/tests/`; each method has its own `tests/`.
5. The solver is a `SolverState` (ordered handlers + flags) that renders to a complete Python module, so the guard always scans real source; `task/solver.py` is the rendered starting state, committed and pinned by a test.
6. Questions are generated from 20 families × 6 instances; instance i gets phrasing i % 2 and split i // 2, so every split holds one A and one B instance of every family.
7. Phrasing B uses user-style entity forms (`computer engineering`, `cmpe120`, `fall 2024`) because SQLite `=` is case-sensitive: value linking is a real NL2SQL failure, not an invented one.
8. Set comparison uses distinct rows (true set semantics); ordered questions compare as lists; floats compare at 2 decimal places on both sides.
9. Instances with an empty gold result are discarded at generation: broken SQL returns nothing and would match them.
10. Top-k ordering instances with a tie at or above the cut-off are discarded: the gold order would be arbitrary.
11. Students enrol only from their admit year onward and skip ~20% of terms, so per-term headcounts vary (first draft had every student in every term, making the A2 answer a constant 300).
12. Starting solver scores 25.0% on all three splits — inside 15–55%, so the question mix was not adjusted.
13. Validation is exposed to improvers as one aggregate number per candidate, never as questions.
14. The held-out boundary has three layers: a process-wide phase flag, call-stack inspection for generated code and proposer modules, and the guard's static scan.
15. One keep rule for every method — strict validation improvement — so differences come from what a method proposes, not from how it accepts.
16. The ScriptedProposer includes six reward hacks at a combined 6% rate, so the guard is exercised by real runs and not only by unit tests.
17. The gutted-solver check compares candidate and starting solver timed back to back (3 reps, min per question) after single-pass timing let a stub through in testing; threshold 0.25 from measured ratios 0.17 (stub) vs 0.60 (fastest legit edit).
18. LLM proposer calls Gemini over REST with urllib (no SDK), keeping dependencies to numpy, pytest and rich; the key travels in the `x-goog-api-key` header, never in a URL.
19. Live LLM rounds run on the baseline method only (8 calls, `gemini-3.5-flash`): the simplest loop isolates whether the integration works. A failed call is a `proposer_error` entry, never a silent switch to the scripted proposer.
20. Baseline reported over 5 seeds × 20 iterations (brief asks ≥ 15) because a single seed ranged from 32.5% to 75%.
21. Source claims for Dream-RSI (2609.14858) and AIDE² (2609.26457) come from their arXiv abstracts: the course's PAPER_SUMMARIES.md covers SO-RSI but not these two.
22. SO-RSI's systematic edit is a bundle (mechanism + the fixes it blocked) judged as one candidate; the guard checks a bundle part by part, so no part escapes the target rules.
23. SO-RSI is reported with two ablations (no_probes = tabu list, no_veto = diagnosis without screening) to show which component carries the effect.
24. "Blind repeat" = this exact edit already failed in this exact solver; a bundle of individually-failed parts is a new edit. Recomputed the baseline under the refined definition: unchanged.
25. Three development runs of SO-RSI from superseded code had appended to docs/ledgers before the final runs (a shell variable did not persist between commands). They were uncommitted; they were deleted, the committed audit log restored, and the reported runs re-run from scratch with identical results.
26. so_loop resolves the ledger directory at call time, so tests can no longer write into docs/ledgers.
27. Dream-RSI's discovery cost is one live scoring pass per expansion; the base agent's edit pool is the ScriptedProposer's legitimate candidates (no reward hacks) and is identical in both arms.
28. The exploration policy is linear over seven expansion features with a softmax; dreaming is a cross-entropy search over its weights, scored on simulated rollouts from every root in the pool, adopted only if it beats the current policy in the same dreams by a margin.
29. Dream-RSI and Recursive Fixed Exploration share seeds, so round 1 is the same discovery tree in both arms; differences start at the first policy update.
30. "Calls saved at equal performance" = live calls fixed exploration needed to reach its own final validation level, minus the calls the dream arm needed to reach the same level; reported per seed, including seeds where the dream arm never got there.
31. Dream-RSI is reported over 10 seeds, not 5, after a change in the CEM random stream alone moved per-seed calls-saved by up to 12: the per-seed number is noise-dominated.
32. Two post-hoc Dream variants are reported separately from the designed method: dream_context (tests a first diagnosis of the seed-0 failure, later shown wrong) and dream_support (tests the corrected diagnosis). No further variants were added after seeing their results.
33. CEM draws noise only for searched weights, so adding an inactive feature cannot change a policy's random stream.
34. AIDE2's inner budget (24 attempts) belongs to the outer loop, not the editable module, so every control variant is benchmarked at equal cost; a guard-rejected attempt still spends budget.
35. AIDE2's hidden evaluation is the validation split, scored only after the inner agent exits, averaged over 3 inner seeds; ties on hidden accuracy go to the variant using fewer inner scorings.
36. AIDE2's inner proposer is ScriptedProposer(0) for every variant — fixed, deterministic — so a measured difference is the harness, not the model.
37. The validation seal (task.boundary.inner_agent) was added to the shared boundary module rather than to 03_aide2, so the enforcement is in the same place as the held-out seal and covered by the same tests.
38. AIDE2's inner candidate pool includes the six reward hacks so that the AIDE2 abstract's reward-hacking observation has a laptop analogue; generation 0 was NOT altered when its hack rate turned out to be zero.
