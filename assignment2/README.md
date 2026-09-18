# CMPE 297 — Assignment 2

This assignment builds a coding-agent harness three ways: from scratch in
16 progressive stages (Part A), by installing and extending a real
open-source harness with community and custom plugins (Part B), and by
using that harness to run a self-improving ML loop with guards against
gaming its own scoreboard (Part C). All three talk to real, live model
APIs — no mocked calls, no fabricated results.

## Demo videos

- Part A: YOUTUBE_LINK_PART_A
- Part B: YOUTUBE_LINK_PART_B
- Part C: YOUTUBE_LINK_PART_C

---

## Part A — A coding agent harness, built from scratch

[`partA/`](partA/) — 16 self-contained stages, each adding exactly one
idea on top of the last. No frameworks, no agent SDKs: the `openai`
client pointed at OpenRouter, plus the standard library.

| # | Stage | The one new idea |
|---|-------|-------------------|
| 01 | [minimal_chat](partA/stage_01_minimal_chat/) | One API call. Print the reply and token usage, including `cached_tokens`. |
| 02 | [bash_tool](partA/stage_02_bash_tool/) | A JSON schema + a Python function = one tool. Single call, no loop — the model proposes, the code disposes. |
| 03 | [tool_registry](partA/stage_03_tool_registry/) | Schemas in a list, functions in a dict, same keys. A new tool is one entry in each. |
| 04 | [read_file](partA/stage_04_read_file/) | A second tool, added by editing only `tools.py` — the loop file never changes. |
| 05 | [agent_loop](partA/stage_05_agent_loop/) | Feed tool results back until the model answers in text. Store the assistant's `tool_calls`; tie each result to its call with `tool_call_id`. |
| 06 | [chat_ui](partA/stage_06_chat_ui/) | An outer loop asks for the next message. All drawing moves into `ui.py`, which knows nothing about models or tools. |
| 07 | [skills](partA/stage_07_skills/) | `SKILL.md` files with YAML front matter. Only name + description ride in the system prompt; the body loads on demand via `read_skill`. |
| 08 | [file_editing](partA/stage_08_file_editing/) | `write_file` and `str_replace`. `str_replace` refuses on zero or multiple matches — the refusal is a tool result, not an exception. |
| 09 | [late_injection](partA/stage_09_late_injection/) | Volatile facts (time, git branch, cwd) ride in a block appended to the request only, never stored — what keeps the stored prefix stable for prompt caching. |
| 10 | [sessions](partA/stage_10_sessions/) | Every message appended to JSONL as it happens. `/rewind` writes a marker, not a delete. `--resume` replays the log. |
| 11 | [todos](partA/stage_11_todos/) | `write_todos` replaces the whole list and requires exactly one `in_progress` item. Rides in the same late block as stage 09. |
| 12 | [permissions](partA/stage_12_permissions/) | A rule table rates every command allow/ask/deny. Compound commands split on `&&`/`\|`; strictest verdict wins. Honestly not real security. |
| 13 | [sandbox](partA/stage_13_sandbox/) | OS-level enforcement: Seatbelt (macOS), bubblewrap (Linux). Windows prints `sandbox: none` and says why, rather than faking it. |
| 14 | [compaction](partA/stage_14_compaction/) | Four mechanisms, cheapest first: cap oversized results to a temp file, shrink finished-turn results to a stub, drop old results outright, then a no-tools summarizer past 85% of the window. |
| 15 | [subagents](partA/stage_15_subagents/) | A `task` tool runs a second agent loop with an empty transcript and every tool except `task`, `write_todos`, `write_file`, `str_replace` — it can look, not edit or recurse. |
| 16 | [openrouter_routing](partA/stage_16_openrouter_routing/) | An ordered `MODELS` fallback route. `usage.include: true` gets the real dollar cost back. `/models` and `/route` inspect and change the route at runtime. |

### Quick start

```powershell
cd partA
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env   # fill in OPENROUTER_API_KEY

.\.venv\Scripts\python.exe stage_16_openrouter_routing\main.py
```

### Tests

```powershell
.\.venv\Scripts\python.exe run_tests.py
```

Runs all 16 stages against a fake model — no API key, no network call.
Each stage's entry file is imported fresh and its real loop, tool
dispatch, and slash commands run exactly as they would against the real
API. One line per stage, ending `all 16 stages passed.`

### The model-deprecation finding

The assignment spec's three suggested free OpenRouter models
(`google/gemini-2.0-flash-exp:free`, `meta-llama/llama-3.1-8b-instruct:free`,
`google/gemini-flash-1.5-8b`) all return 404 "no endpoints found" now —
they've been retired on OpenRouter's side since the assignment was
written. This isn't the "model doesn't support tool calling" case the
spec said to stop and flag for; it's deprecation. Same rule either way —
switch models, not architecture — so the live `/models` endpoint was
queried, several current free tool-calling candidates were each
round-tripped through a real tool call, and three that actually work
were swapped in everywhere the old default appeared (all 16 stages,
`.env.example`, the READMEs):

- Primary: `deepseek/deepseek-v4-flash-0731:free`
- Fallbacks: `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free`, `liquid/lfm-2.5-2.6b:free`

Confirmed end-to-end against the live API: the model proposed a `bash`
call, the harness ran it through permissions and the sandbox layer, fed
the result back with a matching `tool_call_id`, and produced a correct
final answer, at `$0.000000` (free-tier). Stage 16's `README.md` now
calls out that this rotation is expected and is exactly the scenario its
fallback routing exists to handle.

---

## Part B — Installing and extending DeepSeek Harness (dsh)

[`partB/`](partB/) — installs dsh, wires it to OpenRouter, keeps six
community plugins (one per catalog category), drops two that broke the
install, and adds two custom plugins.

### Install

Pinned version, not `@latest` — dsh is a developer preview and this is
what makes the install reproducible later:

```
@deepseek-ai/dsh@0.1.5-rc.2
```

```powershell
npx --yes @deepseek-ai/dsh@0.1.5-rc.2 web --patch ./openrouter.patch.yml --no-open
```

`openrouter.patch.yml` routes the model provider to OpenRouter via
`apiKeyEnv: OPENROUTER_API_KEY` — a credential *reference*, resolved
per-request through dsh's credential seam. No key in any committed file.
Full install log, including the pnpm-not-a-stated-prerequisite gotcha and
the native-directory-picker workaround, is in
[`partB/INSTALL.md`](partB/INSTALL.md).

### Community plugins — six kept

| Plugin | Category | What it does |
|---|---|---|
| [dsh-composer-expand](partB/PLUGINS.md#1-dsh-composer-expand--ui-enhancements) | UI | Toggle button expanding the composer to a tall writing view. |
| [dsh-cool-theme](partB/PLUGINS.md#2-dsh-cool-theme--themes--appearance) | Theming | 34 built-in palettes, full light/dark support, own Settings entry. |
| [dsh-engineer-tools](partB/PLUGINS.md#3-dsh-engineer-tools--tools--capabilities) | Tools | A scoped `git` runner and a lockfile-aware package-manager runner, both returning structured stdout/stderr/exitCode. |
| [dsh-init](partB/PLUGINS.md#4-dsh-init--workflow--automation) | Workflow | Claude-Code-style `/init` — writes `CLAUDE.md`, symlinks `AGENTS.md` to it. |
| [dsh-instruction-memory](partB/PLUGINS.md#5-dsh-instruction-memory--memory) | Memory | User-only standing instructions (model has no write access), auto-injected into every session's system prompt. |
| [dsh-write-protect](partB/PLUGINS.md#6-dsh-write-protect--security--permissions) | Security | Blocks writes to declared subpaths (e.g. `.git`) unless explicitly granted. |

### Two dropped

- **dsh-receipts** — installing it broke the *entire* plugin tree: it
  pulled in a version of `@deepseek-ai/dsh-llm` that no longer exports
  `CallId`, and pnpm's hoisting let that shadow the copy
  `@deepseek-ai/dsh-tools` actually needs. The web server failed to boot
  at all, not just this plugin. Removed.
- **dsh-a11y-scan** — picked as the replacement, hit the *identical*
  `CallId` failure for the identical reason. Same author as
  `dsh-receipts` — strong evidence that author's whole plugin batch was
  built against an incompatible `dsh-llm` release and never republished.
  Removed; `dsh-engineer-tools`, from a different author, was picked next
  and installed clean on the first try.

Full write-up with install commands and demo notes per plugin:
[`partB/PLUGINS.md`](partB/PLUGINS.md).

### Two custom plugins

**leakage-guard** ([`partB/plugins/leakage-guard/`](partB/plugins/leakage-guard/))
— inspects Python code the agent is about to write or run for four
regex-heuristic ML data-leakage patterns (`fit_transform` before a split,
a scaler fit outside a `Pipeline`, `shuffle=True` alongside a time-series
split, `.fit(` called with something named `test`), and warns without
blocking. There's no non-blocking "warn" verdict in dsh's real
`PreToolDecision` type, so it uses two real hook points together:
`tools/pre-execute` inspects and always allows; `tools/post-execute`
appends the warning text to the tool's own result content, so the agent
reads it and can self-correct on its next turn.

**session-cost-panel** ([`partB/plugins/session-cost-panel/`](partB/plugins/session-cost-panel/))
— tracks tokens and cost per model call across a session via
`session/event` (`request/header`, `assistant/message` for real token
counts, `tool/call` for per-tool attribution), surfaced through a `/cost`
command and persisted to a JSON file that survives a process restart
(verified by actually killing and restarting dsh and re-running `/cost`).
Every figure is labeled **ESTIMATED, not measured** — DSH's `TokenUsage`
type has no dollar-cost field, so this multiplies real token counts by a
hand-maintained, illustrative price table, unlike Part A where
OpenRouter's `usage.include` returns a real billed amount.

### Quick start

```powershell
cd partB
npx --yes @deepseek-ai/dsh@0.1.5-rc.2 web --patch ./openrouter.patch.yml --patch ./custom-plugins.patch.yml
```

---

## Part C — autoresearch: Karpathy's loop as a DSH plugin

[`partC/`](partC/) — a DSH plugin implementing propose → run → measure →
keep/revert on a real scikit-learn training script, with a held-out
split the loop cannot see and a reward-hacking guard checked against
deliberate gaming attempts, not just absence of false positives.

### The real 10-iteration run

| # | Change | Metric before → after | Elapsed (s) | Decision |
|---|---|---|---|---|
| 0 | baseline: `DecisionTreeClassifier(max_depth=2)` | — → 0.6711 | 6.18 | baseline |
| 1 | DecisionTree → `RandomForestClassifier` | 0.6711 → 0.8800 | 8.45 | **kept** |
| 2 | (propose call timed out after 3 attempts) | 0.8800 → — | — | reverted |
| 3 | RandomForest → `HistGradientBoostingClassifier` | 0.8800 → 0.8744 | 7.60 | reverted |
| 4 | RandomForest, hyperparameters changed | 0.8800 → 0.8778 | 7.63 | reverted |
| 5 | RandomForest, hyperparameters changed | 0.8800 → 0.8778 | 7.69 | reverted |
| 6 | (propose call timed out after 3 attempts) | 0.8800 → — | — | reverted |
| 7 | RandomForest, hyperparameters changed | 0.8800 → 0.8778 | 7.63 | reverted |
| 8 | RandomForest → `ExtraTreesClassifier` | 0.8800 → 0.8867 | 5.50 | **kept** |
| 9 | ExtraTrees, hyperparameters changed | 0.8867 → 0.8967 | 7.39 | **kept** |
| 10 | ExtraTrees, hyperparameters changed | 0.8967 → 0.8956 | 6.83 | reverted |

**67.11% → 89.67% held-out accuracy. 3 kept, 7 reverted** (5 for "did not
improve," 2 for LLM call timeouts, retried 3× before logging as a revert
— never silently dropped). Zero guard-content rejections in this run.
Full ledger: [`partC/runs/ledger.jsonl`](partC/runs/ledger.jsonl).

### Two real guard false positives, hit and fixed

1. A legitimate RandomForest edit was rejected — reason: "references
   'heldout'" — because the model added a defensive comment,
   `# Note: never touch heldout data`, and the guard scanned raw text
   including `#`-comments. Fixed: strip comments before scanning.
2. After that fix, a second legitimate edit was still rejected for the
   same reason — the match was inside `train.py`'s own module
   **docstring**, which comment-stripping doesn't touch. Fixed: also
   strip triple-quoted strings before scanning.

Neither was a false negative — no real gaming attempt ever got through —
but both would have made the guard unusable by rejecting honest work.

### The timing-threshold near-miss

A zero-rejection run proves the guard didn't produce false positives; it
proves nothing about whether it would catch a real cheating attempt. The
verification suite (below) tested that directly with a `train.py` gutted
to dump a fake object without training — and the first run of that test
found the gutted script still cost ~0.93s in pure Python/joblib import
overhead, which beat the original timing threshold (reject under 15% of
the 6.18s baseline = 0.928s) by 6 milliseconds and was accepted. Checked
against the real run's legitimate timings (5.50s–8.45s, 89%–137% of
baseline), the threshold was tightened to 50% of baseline — comfortable
margin below every real edit, comfortable margin above the gamed one.

### Guard verification suite — 13/13 passing

[`partC/tests/guard.test.mjs`](partC/tests/guard.test.mjs): 4 deliberately
gaming edits, each asserted rejected with the right reason (reads the
held-out split, hardcodes predictions, rewrites `evaluate.py`'s scorer at
runtime, a gutted `train.py` run end-to-end as a real subprocess and
caught only by the dynamic timing guard after passing the static one) —
plus 2 legitimate edits that must still pass, so the suite proves the
guard discriminates rather than just rejecting everything.

```powershell
cd partC
node tests/guard.test.mjs
# 13 passed, 0 failed
```

Full results, the leakage-boundary design, and the guard table:
[`partC/README.md`](partC/README.md).

### Quick start

```powershell
cd partC
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install scikit-learn numpy joblib
.\.venv\Scripts\python.exe target\train.py
.\.venv\Scripts\python.exe harness\evaluate.py

npx --yes @deepseek-ai/dsh@0.1.5-rc.2 --profile partc --patch ./openrouter.patch.yml --patch ./custom-plugins.patch.yml --port 3081
```

In a session inside the workspace: `/autoresearch 10`, then
`/autoresearch-status`.
