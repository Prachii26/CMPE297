# Assignment 3 — Five Google ADK agents

Five agents built on the Google Agent Development Kit (**`google-adk==2.13.0`**,
Python 3.11, `gemini-flash-latest` via AI Studio). Each has its own virtualenv,
its own README with a mermaid architecture diagram, pinned requirements, an
offline test suite, and a demo transcript from a real run.

Each agent is written from scratch against a named reference implementation —
read, not copied — with the domain changed and at least two behaviours changed.
Those changes are listed in each agent's README under "Our changes".

**Demo video:** YOUTUBE_VIDEO_LINK

## Status

| | Agent | What it does | Status | Tests |
|---|---|---|---|---|
| **C** | [c_bug_assistant_agent](c_bug_assistant_agent/README.md) | Triages VoltLoop e-scooter bugs over MCP; `search_bugs` returns a severity- and component-ranked queue, and `set_status` refuses to act without an audited reason. | **WORKING** | 22 |
| **A** | [a_deep_research_agent](a_deep_research_agent/README.md) | Turns an ideal customer profile into a sourced lead table; planner → 3 parallel researchers → critic loop → writer, each lead scored 1–5 by a deterministic tool. | **PARTIAL** | 34 |
| **D** | [d_code_review_agent](d_code_review_agent/README.md) | Reviews a Python file by path with AST, pycodestyle and complexity tools, then fixes it in a capped loop that emits a unified diff. | **WORKING** | 38 |
| **B** | [b_gemini_cli_agent](b_gemini_cli_agent/README.md) | Answers questions about a sandboxed code folder by driving the Gemini CLI as a function tool, returning a structured summary. | **WORKING** | 28 |
| **E** | [e_ecommerce_agent](e_ecommerce_agent/README.md) | Meeple Market board game shop over MCP + SQLite; every tool is scoped to a `user_id`, and out-of-stock items always return alternatives. | **WORKING** | 33 |

Four of five are verified live. Agent A is **PARTIAL**, but much further along
than that label suggests: after replacing Gemini's Search grounding (metered on
its own exhausted quota) with a DuckDuckGo-backed `FunctionTool`, **five of its
seven stages run live** — planner, all three parallel researchers, and the lead
scorer, producing five real Nordic companies with real source URLs and fit
scores of 5/4/4/4/3. The critic loop starts and calls its wrapped search agent;
the critic and report writer did not finish before the day's per-model quota
ran out, so there is no final lead table. Full account, including the three
attempts and two bugs found on the way, in
[its demo](a_deep_research_agent/docs/demo.md).

## Run commands

All PowerShell, from the repo root. Each agent has its own venv and its own
port, so several can run at once.

```powershell
# C - bug triage assistant
cd Assignment3\c_bug_assistant_agent
.\.venv\Scripts\adk.exe web --port 8731

# A - lead research pipeline
cd Assignment3\a_deep_research_agent
.\.venv\Scripts\adk.exe web --port 8741

# D - code review and fix
cd Assignment3\d_code_review_agent
.\.venv\Scripts\adk.exe web --port 8751

# B - codebase Q&A via the Gemini CLI
cd Assignment3\b_gemini_cli_agent
.\.venv\Scripts\adk.exe web --port 8761

# E - Meeple Market shop
cd Assignment3\e_ecommerce_agent
.\.venv\Scripts\adk.exe web --port 8771
```

First-time setup, per agent folder:

```powershell
cd Assignment3\<agent_folder>
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$lines = @("GOOGLE_GENAI_USE_VERTEXAI=FALSE", "GOOGLE_API_KEY=$env:GEMINI_API_KEY")
Set-Content -Path .env -Value $lines -Encoding utf8
```

Agent B additionally needs the Gemini CLI from npm:

```powershell
npm install -g @google/gemini-cli   # verified against 0.66.0
```

## Tests

```powershell
cd Assignment3\<agent_folder>
.\.venv\Scripts\python.exe -m pytest tests\ -q
```

No test makes a network call. The model is stubbed (agent A replays a scripted
`BaseLlm`), the Gemini CLI subprocess is stubbed (agent B), and the MCP tools
are called directly against a throwaway SQLite file (agents C and E). Each
suite also strips `GOOGLE_API_KEY`/`GEMINI_API_KEY` so an accidental live call
fails loudly instead of quietly spending quota.

## Verification and the quota ceiling

"Verified" for this assignment means: `adk web` starts, a real
`gemini-flash-latest` call succeeds, the tool calls appear in the trace, and the
tests pass.

The live half ran into a hard ceiling. This AI Studio key's free tier allows
only **20 `generateContent` requests per day** for `gemini-2.5-flash` (plus 5
per minute), and that was exhausted early.

Quota is tracked **per model** — the quota ID is
`GenerateRequestsPerDayPerProjectPerModel` — so switching models gives a fresh
bucket. Probing the key found six usable alternatives (`gemini-flash-latest`,
`gemini-flash-lite-latest`, `gemini-3-flash-preview`, `gemini-3.5-flash`,
`gemini-3.5-flash-lite`, `gemini-3.1-flash-lite`), while `gemini-2.5-pro` and
`gemini-2.5-flash-lite` return 404 for this key.

All five agents therefore default to **`gemini-flash-latest`**, overridable per
agent with an env var. Each `docs/demo.md` records the model that produced its
transcript.

Rate limiting still shapes the runs. Every agent builds its model with
`HttpRetryOptions(http_status_codes=[429, 503, 504])` and long jittered
backoff. Agent E's demo run took 467 seconds, nearly all of it absorbing a 503
"this model is currently experiencing high demand" retry — without that config
the run would simply have failed. Every test suite runs without the API, so
correctness is demonstrable regardless of quota.

Where an agent could not complete a live run within budget, it is marked
**PARTIAL** with the exact error, here and in its own README. Nothing is marked
WORKING on the strength of a stubbed run.

## Findings

Three things from building this that a reader should know.

### 1. A code reviewer that invents what it cannot see

Agent D's first live run passed every check and **destroyed the module it was
fixing**. `get_discount(user, cart_total, coupon, is_member, region)` came back
as `get_discount(total, is_member, items, is_holiday, is_birthday)`, with the
region rules, the coupon rules and the clearance loop deleted and flat currency
discounts turned into percentages. `checks_pass` was `true`, because PEP 8 and
cyclomatic complexity cannot see semantics.

The cause was upstream of the fixer. `check_style` returned line numbers and
violation codes but **not the text of those lines**, so the reviewer filled in
the gap from imagination: it reported variables named `is_holiday` and
`is_birthday` at lines 22 and 24, which actually contain `is_member` — neither
name appears anywhere in the file. The fixer then read that review and built a
feature around the invented names.

Two fixes, both in code rather than in the prompt:

- `check_style` now attaches the real source line to every violation, so there
  is nothing left to guess.
- `propose_patch` compares the module's public API before and after and fails
  with `api_preserved: false`, naming every change. Extracting **private**
  helpers stays allowed, since that is how a complexity-16 function is
  legitimately brought down.

Re-run against the exact patch from that session: `style_ok` and
`complexity_ok` stay `true`, `api_preserved` goes `false`, `checks_pass` goes
`false`. Five tests cover it. Full write-up in
[agent D's demo](d_code_review_agent/docs/demo.md).

### 2. Search grounding is a separate quota from the model

Agent A stalled on `429 RESOURCE_EXHAUSTED` across three runs. The obvious
reading — the model's daily cap — was wrong, and chasing it cost real time.

Quota on this key is tracked **per model**
(`GenerateRequestsPerDayPerProjectPerModel`, 20/day each), so the first fix was
to give each of the three parallel researchers its own model. All three still
429'd, which ruled the model quota out.

The controlled test that settled it: one model, one minute, two requests.

```
plain (no tools)       200 OK
grounded (search)      429  You exceeded your current quota...
```

**Google Search grounding is metered on its own dimension**, and it was
exhausted. The error shape is the tell — per-model 429s carry a `QuotaFailure`
detail naming the quota and its value, while the grounding 429 carries only a
help link.

The fix was to stop fighting it: the researchers now use a `web_search`
`FunctionTool` backed by DuckDuckGo, which needs no key and no quota. The
pipeline's actual subject — Sequential/Parallel/Loop composition, `output_key`
state passing, and a critic that rejects unsourced leads — does not depend on
which engine sits behind the tool. A side benefit: a `FunctionTool` has none of
the built-in-tool restrictions that make `google_search` awkward to compose.

That unblocked the parallel stage: the researchers now complete and the scorer
produces real, sourced leads. Swapping the backend also surfaced two bugs of my
own — a rate-limit lock held across the network call, which made one slow
search block every other researcher (a run sat 1500 s with **zero** API
errors), and researchers with no search budget, one of which ran **33** searches
and burned its model's daily quota. Both are fixed; both are the kind of fault
that only appears under real concurrency.

### 3. Two process mistakes worth not repeating

Both are in [DECISIONS.md](DECISIONS.md), and both cost time rather than
correctness.

- **Running agents concurrently produced self-inflicted 429s.** Agent A's three
  parallel researchers alone exceed the 5-requests-per-minute cap; running
  agent D and agent B's CLI alongside them made every run slower, not faster.
  Serialising the demo runs was strictly quicker.
- **Watching the DOM to decide a run had finished cancelled two live runs.**
  During a 429 or 503 backoff the dev UI is completely static, so "the page
  stopped changing" reads identically to "the run is done". Closing the browser
  at that point cancels the run server-side (`Root node ... was cancelled`).
  Completion is now detected by polling the ADK sessions API for a text event
  from the expected final agent.

## Layout

```
assignment3/
├── README.md              this file
├── PROMPTS.md             every prompt sent, verbatim
├── DECISIONS.md           one line per call made without asking
├── _reference/            upstream clones, gitignored, not submitted
├── a_deep_research_agent/
├── b_gemini_cli_agent/
├── c_bug_assistant_agent/
├── d_code_review_agent/
└── e_ecommerce_agent/
```

Each agent folder holds the ADK package, `requirements.txt`, `.env.example`,
`tests/`, and `docs/` with a demo transcript and a screenshot.

Secrets live only in `.env`, which is gitignored along with `.venv/` and
`_reference/`. No API key appears in any tracked file.

## References

Each agent cites its source in its own README. The five read for this
assignment:

| Agent | Reference |
|---|---|
| C | [google/adk-samples](https://github.com/google/adk-samples) — `software-bug-assistant`, plus the *Zero to Assistant* codelab |
| A | [MagnIeeT/leadGenerationAgentADK](https://github.com/MagnIeeT/leadGenerationAgentADK), plus Google's *Build a deep research agent with ADK* |
| D | [ayoisio/adk-code-review-assistant](https://github.com/ayoisio/adk-code-review-assistant) |
| B | [derrickchwong/gemini-cli-on-adk](https://github.com/derrickchwong/gemini-cli-on-adk) |
| E | [mtoscano84/sports-agent-adk-mcp-alloydb](https://github.com/mtoscano84/sports-agent-adk-mcp-alloydb) |
