# Assignment 3 — Five Google ADK agents

Five agents built on the Google Agent Development Kit (**`google-adk==2.13.0`**,
Python 3.11, `gemini-flash-latest` via AI Studio). Each has its own virtualenv,
its own README with a mermaid architecture diagram, pinned requirements, an
offline test suite, and a demo transcript from a real run.

Each agent is written from scratch against a named reference implementation —
read, not copied — with the domain changed and at least two behaviours changed.
Those changes are listed in each agent's README under "Our changes".

## Status

| | Agent | What it does | Status | Tests |
|---|---|---|---|---|
| **C** | [c_bug_assistant_agent](c_bug_assistant_agent/README.md) | Triages VoltLoop e-scooter bugs over MCP; `search_bugs` returns a severity- and component-ranked queue, and `set_status` refuses to act without an audited reason. | **WORKING** | 22 |
| **A** | [a_deep_research_agent](a_deep_research_agent/README.md) | Turns an ideal customer profile into a sourced lead table; planner → 3 parallel researchers → critic loop → writer, each lead scored 1–5 by a deterministic tool. | **PARTIAL** | 22 |
| **D** | [d_code_review_agent](d_code_review_agent/README.md) | Reviews a Python file by path with AST, pycodestyle and complexity tools, then fixes it in a capped loop that emits a unified diff. | **WORKING** | 38 |
| **B** | [b_gemini_cli_agent](b_gemini_cli_agent/README.md) | Answers questions about a sandboxed code folder by driving the Gemini CLI as a function tool, returning a structured summary. | **WORKING** | 28 |
| **E** | [e_ecommerce_agent](e_ecommerce_agent/README.md) | Meeple Market board game shop over MCP + SQLite; every tool is scoped to a `user_id`, and out-of-stock items always return alternatives. | **WORKING** | 33 |

Four of five are verified live. Agent A is **PARTIAL**: its pipeline loads and
its planner stage completes against a real model, but the three parallel
researchers fail on the **Google Search grounding quota**, which is rate
limited separately from the model quota and is exhausted on this key. The exact
error, the three attempts made, and the test that isolates grounding from the
model are in [its demo](a_deep_research_agent/docs/demo.md).

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
