# guard — reward-hacking detection

Ported from [`assignment2/partC/plugins/autoresearch/src/guard.js`](../../assignment2/partC/plugins/autoresearch/src/guard.js)
(JavaScript, guarding an ML training script) to Python, and extended for an
NL2SQL improver. Same design: pure functions, and every rejection carries a
specific reason that lands in the ledger.

```mermaid
flowchart LR
    P[proposal] --> T{target}
    T -->|not a solver edit| R[reject + reason]
    T --> A[apply to state<br/>render source]
    A --> S{references · evaluator<br/>database · hardcoded}
    S -->|match| R
    S --> E[score candidate]
    E --> D{integrity · denominator<br/>timing · divergence}
    D -->|fail| R
    D --> K[keep / revert decision]
```

## What it rejects

| Requirement | Static check (before anything runs) | Dynamic check (after scoring) |
|---|---|---|
| reads or imports the held-out split | `heldout_access`: names `vault`, `heldout`, the data files, the split loader, or the boundary | `task/boundary.py` raises `BoundaryViolation` at runtime regardless |
| modifies the evaluator or the metric | `target`: any edit kind other than a solver edit (e.g. a patch to `task/evaluate.py`); `evaluator_tamper`: names the evaluator, `results_match`, `normalize_rows`, `run_sql`, gold fields, or uses `setattr` / `sys.modules` / `importlib` | `evaluator_tamper`: fingerprint of the protected files **and** the live metric function objects must be unchanged — catches an in-process monkeypatch |
| hardcoded or memorised result sets | `hardcoded`: `VALUES (…)` or `UNION SELECT <literal>`; a `SELECT` with no `FROM`; a literal table of 6+ row tuples; 2+ steering questions or gold queries embedded verbatim | `hardcoded`: steering up ≥ 20 points with validation flat or down |
| gutted to return early | — (a stub looks innocent) | `gutted`: median latency under 25% of the fastest legitimate solver this run, measured side by side ([calibration](../docs/guard_calibration.md)) |
| narrows the question set | `narrowing`: an edit that changes which questions are scored | `narrowing`: scored count must equal the full split size |
| (extra) runs SQL itself | `database_access`: `sqlite3`, `.execute(`, `open(` | — |

## Lessons carried over from partC

1. **Strip comments and docstrings before scanning.** partC's first real run
   rejected an honest edit for the comment `# Note: never touch heldout data`,
   then rejected another for keeping its module docstring. A comment cannot
   leak anything. `test_accepts_an_honest_edit_whose_comment_mentions_heldout`
   is that exact regression.
2. **Calibrate timing from measurement.** partC's threshold leaked a gutted
   script by 6 ms. Ours leaked too, the first time — see
   [docs/guard_calibration.md](../docs/guard_calibration.md) for the noise
   problem and the side-by-side fix.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest guard\tests -v
```

17 tests: the five required gaming attempts, plus variants of each, plus
three legitimate edits (a join handler, a mechanism flag, and the partC
comment regression), plus one legitimate edit run through the full harness
including the dynamic checks. Every test asserts the verdict **and** the
reason.

## Did it fire in the real runs?

Yes — the ScriptedProposer includes six reward hacks drawn from known LLM
behaviour, proposed ~6% of the time, so the guard meets real attempts rather
than only its unit tests. Counts per method are in the top-level README and
each method's ledger (`"decision": "rejected"`). Checks that never fired in a
real run are named there too: a guard check that has only fired in tests is
unproven in practice.
