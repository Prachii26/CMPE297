# Prompts

Every prompt sent in the session that built this assignment, verbatim and in
order. Notes in *[brackets]* describe session events that are not prompts;
nothing inside a prompt block has been edited.

---

## Prompt 1

*[Sent, then interrupted by the user before any work landed. The user then
ran the local command `/model opus`, which is not a prompt.]*

```text
Assignment 5 for CMPE 297: demonstrate three state-of-the-art RSI methods on one problem domain, as progressive codelabs following section 10 of the professor's course map.

## Location
Create assignment5 at the root of the CMPE297 repo, parallel to Assignment1, assignment2, assignment3. List the repo root first and match the existing casing convention.

Structure:
  assignment5/
    task/                 the problem domain and its evaluation
    00_baseline/
    01_so_rsi/
    02_dream_rsi/
    03_aide2/
    guard/                reward-hacking detection, ported from assignment2/partC
    docs/
    README.md
    PROMPTS.md
    DECISIONS.md

I am on Windows PowerShell. Write every command in PowerShell syntax.

## Read first, do not copy
Read these for structure, vocabulary and the comparison framework:
- https://raw.githubusercontent.com/dlmastery/simple-coding-harness/main/COURSE-MAP.md (section 10)
- https://raw.githubusercontent.com/dlmastery/simple-coding-harness/main/10_research_studio/README.md
- https://raw.githubusercontent.com/dlmastery/simple-coding-harness/main/12_october_2026_papers/PAPER_SUMMARIES.md
Write our own code in our own domain. Cite these in each README.

Also read assignment2/partC in this repo. Its reward-hacking guard and run ledger are ours and we are extending them.

## The problem domain (task/)
Natural language to SQL over a seeded SQLite database: a university course-enrollment schema with 8 tables (students, courses, sections, enrollments, instructors, departments, terms, grades). Seed it deterministically with numpy default_rng(42). No downloads.

Build 120 natural-language questions with gold SQL and gold result sets, spanning joins, aggregates, filters, subqueries and ordering. Split them three ways and enforce the boundary in code:
- steering (40): visible to the improver
- validation (40): used to select among candidates
- held-out (40): NEVER visible to any improver, used only for the final reported number

The system under improvement is solver.py: question in, SQL out. Start it deliberately weak — template matching that handles simple SELECTs and fails on joins and aggregates — so there is real headroom. Report a baseline held-out exact-result-set match rate before any method runs. If the baseline is above 55% or below 15%, adjust the question mix and say so.

Metric: exact result-set match on held-out, plus median query latency. Set-compare, order-insensitive unless the question asks for ordering.

## The proposer
Candidate edits come from a pluggable proposer:
- ScriptedProposer (default): a deterministic mutator over a library of repair strategies. Everything runs offline at zero cost.
- LLMProposer (optional): Gemini via GEMINI_API_KEY. Free tier is roughly 20 requests per day per model across about 6 models, so budget it. Run enough real rounds on ONE method to prove the integration works, capture that transcript, and say in the README which runs were scripted and which were live.
Never let a run silently switch proposers. Log which one produced every ledger entry.

## The three methods

00_baseline — a naive RSI loop: propose an edit, run the full evaluation, keep if validation improved, revert otherwise. Ledger every iteration with the edit, before/after metric, decision, reason, and wall-clock. This is the control that the three methods are measured against. Run at least 15 iterations.

01_so_rsi — Second-Order RSI (arXiv 2610.05701). Changed object: the diagnostic strategy.
Standard RSI patches symptoms and thrashes. SO-RSI investigates WHY before editing.
Implement: structural anomaly detection over the trace history for the three signals in the paper — recurrence (the same fix attempted repeatedly), opposing edits (undoing a previous change), and expectation mismatch (the outcome contradicts what the edit predicted); lightweight diagnostic probes that test a hypothesis about root cause rather than applying a fix; an inquiry memory that persists causal findings across rounds; and edits that address the diagnosed mechanism.
Show the behavioural result, not just the score: count oscillations and repeated-fix attempts in the baseline versus SO-RSI. The paper's claim is reduced thrashing — measure whether ours shows it, and report honestly if it does not.

02_dream_rsi — Dream-RSI (arXiv 2609.14858). Changed object: the exploration policy.
Three stages, each a separate module: online exploration where the current policy drives real discovery and logs full execution traces; replay simulator construction turning recorded discovery trees into a reusable simulator pool; and dreaming-based policy improvement where candidate policies are evaluated cheaply off-policy against that pool instead of running live. Redeploy the selected policy and grow the pool.
The controlled baseline from the paper is Recursive Fixed Exploration — same discovery agent, same budget, same starting policy, but the exploration policy never changes. Implement that comparison. Report downstream metric against cumulative discovery cost for both, over at least 8 rounds. The interesting number is calls saved at equal performance, so report that.

03_aide2 — AIDE² (arXiv 2609.26457). Changed object: the harness code itself.
Two loops. The inner loop is a small tree search over SQL repairs with explicit search-and-control code: branching factor, node selection rule, stopping condition, and the repair-strategy ordering. The outer loop proposes rewrites to that search-and-control module, benchmarks each modified version of the inner agent, and keeps what wins on evaluations the outer loop cannot see.
Enforce the hidden-evaluation boundary in code, not by convention, and show the enforcement in the README. Keep the proposer fixed across inner-agent variants so the measured difference is the harness, not the model.
Run at least 6 outer generations and show the lineage: which generation each surviving change came from.

## The guard (guard/)
Port and extend the reward-hacking guard from assignment2/partC. It must reject, with a logged reason:
- any edit that reads or imports the held-out split
- any edit that modifies the evaluator or the metric definition
- hardcoded or memorised expected result sets
- a solver gutted to return early (timing far below the observed legitimate range)
- an edit that narrows the question set rather than improving the solver
Write a test suite that feeds it four deliberate gaming attempts and at least two legitimate edits, and asserts each verdict with its reason. A guard that has never fired is unproven — say so in the README if it does not fire during the real runs.

## Deliverables
Each method folder: runnable code, a README with a mermaid diagram, the paper's mechanism, OUR adaptation and how it differs, run commands, the real ledger and result, and limits. Tests that run offline.

assignment5/README.md must contain, near the top:
- A single YOUTUBE_VIDEO_LINK placeholder
- The comparison table, which is the centrepiece. One row per method plus the baseline, with these columns exactly, because they are the professor's stated framework: changed object, feedback signal, inheritance, evaluation, cost.
- For each method, three separately labelled statements: the SOURCE CLAIM from the paper with its arXiv id, OUR LAPTOP ADAPTATION and what we simplified, and the OBSERVED RESULT from our run. Never blur these three. A laptop adaptation that did not reproduce the paper's direction is a finding, not a failure — report it plainly.
- Baseline and final held-out numbers for every method, with the proposer used.

docs/ledgers/ — the raw append-only ledgers from every run.
PROMPTS.md — every prompt I send, verbatim, in order, from session history. Invent nothing.

## Rules
- Python 3.11, one .venv. numpy, pytest, rich. No GPU, no downloads, no network at runtime except the optional LLM proposer.
- Every method must finish a full run in under 10 minutes on a laptop.
- Do not ask me questions. Make a call, log one line in DECISIONS.md.
- If a method is still failing after 60 minutes, mark it PARTIAL with the exact error and move on. Do not fake a result.
- Commit and push after each method is verified.
- Grep for AIza and sk- before the final push; confirm .venv/ is gitignored.

## Order
Build task/ and 00_baseline first and report the baseline held-out number before going further — everything downstream is meaningless if the baseline is wrong. Then guard/, then 01, 02, 03.

Report after the baseline, then after each method.
```

## Prompt 2

*[Identical to prompt 1, re-sent after the model switch.]*

```text
Assignment 5 for CMPE 297: demonstrate three state-of-the-art RSI methods on one problem domain, as progressive codelabs following section 10 of the professor's course map.

## Location
Create assignment5 at the root of the CMPE297 repo, parallel to Assignment1, assignment2, assignment3. List the repo root first and match the existing casing convention.

Structure:
  assignment5/
    task/                 the problem domain and its evaluation
    00_baseline/
    01_so_rsi/
    02_dream_rsi/
    03_aide2/
    guard/                reward-hacking detection, ported from assignment2/partC
    docs/
    README.md
    PROMPTS.md
    DECISIONS.md

I am on Windows PowerShell. Write every command in PowerShell syntax.

## Read first, do not copy
Read these for structure, vocabulary and the comparison framework:
- https://raw.githubusercontent.com/dlmastery/simple-coding-harness/main/COURSE-MAP.md (section 10)
- https://raw.githubusercontent.com/dlmastery/simple-coding-harness/main/10_research_studio/README.md
- https://raw.githubusercontent.com/dlmastery/simple-coding-harness/main/12_october_2026_papers/PAPER_SUMMARIES.md
Write our own code in our own domain. Cite these in each README.

Also read assignment2/partC in this repo. Its reward-hacking guard and run ledger are ours and we are extending them.

## The problem domain (task/)
Natural language to SQL over a seeded SQLite database: a university course-enrollment schema with 8 tables (students, courses, sections, enrollments, instructors, departments, terms, grades). Seed it deterministically with numpy default_rng(42). No downloads.

Build 120 natural-language questions with gold SQL and gold result sets, spanning joins, aggregates, filters, subqueries and ordering. Split them three ways and enforce the boundary in code:
- steering (40): visible to the improver
- validation (40): used to select among candidates
- held-out (40): NEVER visible to any improver, used only for the final reported number

The system under improvement is solver.py: question in, SQL out. Start it deliberately weak — template matching that handles simple SELECTs and fails on joins and aggregates — so there is real headroom. Report a baseline held-out exact-result-set match rate before any method runs. If the baseline is above 55% or below 15%, adjust the question mix and say so.

Metric: exact result-set match on held-out, plus median query latency. Set-compare, order-insensitive unless the question asks for ordering.

## The proposer
Candidate edits come from a pluggable proposer:
- ScriptedProposer (default): a deterministic mutator over a library of repair strategies. Everything runs offline at zero cost.
- LLMProposer (optional): Gemini via GEMINI_API_KEY. Free tier is roughly 20 requests per day per model across about 6 models, so budget it. Run enough real rounds on ONE method to prove the integration works, capture that transcript, and say in the README which runs were scripted and which were live.
Never let a run silently switch proposers. Log which one produced every ledger entry.

## The three methods

00_baseline — a naive RSI loop: propose an edit, run the full evaluation, keep if validation improved, revert otherwise. Ledger every iteration with the edit, before/after metric, decision, reason, and wall-clock. This is the control that the three methods are measured against. Run at least 15 iterations.

01_so_rsi — Second-Order RSI (arXiv 2610.05701). Changed object: the diagnostic strategy.
Standard RSI patches symptoms and thrashes. SO-RSI investigates WHY before editing.
Implement: structural anomaly detection over the trace history for the three signals in the paper — recurrence (the same fix attempted repeatedly), opposing edits (undoing a previous change), and expectation mismatch (the outcome contradicts what the edit predicted); lightweight diagnostic probes that test a hypothesis about root cause rather than applying a fix; an inquiry memory that persists causal findings across rounds; and edits that address the diagnosed mechanism.
Show the behavioural result, not just the score: count oscillations and repeated-fix attempts in the baseline versus SO-RSI. The paper's claim is reduced thrashing — measure whether ours shows it, and report honestly if it does not.

02_dream_rsi — Dream-RSI (arXiv 2609.14858). Changed object: the exploration policy.
Three stages, each a separate module: online exploration where the current policy drives real discovery and logs full execution traces; replay simulator construction turning recorded discovery trees into a reusable simulator pool; and dreaming-based policy improvement where candidate policies are evaluated cheaply off-policy against that pool instead of running live. Redeploy the selected policy and grow the pool.
The controlled baseline from the paper is Recursive Fixed Exploration — same discovery agent, same budget, same starting policy, but the exploration policy never changes. Implement that comparison. Report downstream metric against cumulative discovery cost for both, over at least 8 rounds. The interesting number is calls saved at equal performance, so report that.

03_aide2 — AIDE² (arXiv 2609.26457). Changed object: the harness code itself.
Two loops. The inner loop is a small tree search over SQL repairs with explicit search-and-control code: branching factor, node selection rule, stopping condition, and the repair-strategy ordering. The outer loop proposes rewrites to that search-and-control module, benchmarks each modified version of the inner agent, and keeps what wins on evaluations the outer loop cannot see.
Enforce the hidden-evaluation boundary in code, not by convention, and show the enforcement in the README. Keep the proposer fixed across inner-agent variants so the measured difference is the harness, not the model.
Run at least 6 outer generations and show the lineage: which generation each surviving change came from.

## The guard (guard/)
Port and extend the reward-hacking guard from assignment2/partC. It must reject, with a logged reason:
- any edit that reads or imports the held-out split
- any edit that modifies the evaluator or the metric definition
- hardcoded or memorised expected result sets
- a solver gutted to return early (timing far below the observed legitimate range)
- an edit that narrows the question set rather than improving the solver
Write a test suite that feeds it four deliberate gaming attempts and at least two legitimate edits, and asserts each verdict with its reason. A guard that has never fired is unproven — say so in the README if it does not fire during the real runs.

## Deliverables
Each method folder: runnable code, a README with a mermaid diagram, the paper's mechanism, OUR adaptation and how it differs, run commands, the real ledger and result, and limits. Tests that run offline.

assignment5/README.md must contain, near the top:
- A single YOUTUBE_VIDEO_LINK placeholder
- The comparison table, which is the centrepiece. One row per method plus the baseline, with these columns exactly, because they are the professor's stated framework: changed object, feedback signal, inheritance, evaluation, cost.
- For each method, three separately labelled statements: the SOURCE CLAIM from the paper with its arXiv id, OUR LAPTOP ADAPTATION and what we simplified, and the OBSERVED RESULT from our run. Never blur these three. A laptop adaptation that did not reproduce the paper's direction is a finding, not a failure — report it plainly.
- Baseline and final held-out numbers for every method, with the proposer used.

docs/ledgers/ — the raw append-only ledgers from every run.
PROMPTS.md — every prompt I send, verbatim, in order, from session history. Invent nothing.

## Rules
- Python 3.11, one .venv. numpy, pytest, rich. No GPU, no downloads, no network at runtime except the optional LLM proposer.
- Every method must finish a full run in under 10 minutes on a laptop.
- Do not ask me questions. Make a call, log one line in DECISIONS.md.
- If a method is still failing after 60 minutes, mark it PARTIAL with the exact error and move on. Do not fake a result.
- Commit and push after each method is verified.
- Grep for AIza and sk- before the final push; confirm .venv/ is gitignored.

## Order
Build task/ and 00_baseline first and report the baseline held-out number before going further — everything downstream is meaningless if the baseline is wrong. Then guard/, then 01, 02, 03.

Report after the baseline, then after each method.
```

## Prompt 3

```text
Tool loaded.
```
