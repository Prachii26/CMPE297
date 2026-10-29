# Assignment 3 — Five Google ADK agents

Five agents built on the Google Agent Development Kit (**`google-adk==2.13.0`**,
Python 3.11, `gemini-2.5-flash` via AI Studio). Each has its own virtualenv,
its own README with a mermaid architecture diagram, pinned requirements, an
offline test suite, and a demo transcript from a real run.

Each agent is written from scratch against a named reference implementation —
read, not copied — with the domain changed and at least two behaviours changed.
Those changes are listed in each agent's README under "Our changes".

## Status

| | Agent | What it does | Status | Tests |
|---|---|---|---|---|
| **C** | [c_bug_assistant_agent](c_bug_assistant_agent/README.md) | Triages VoltLoop e-scooter bugs over MCP; `search_bugs` returns a severity- and component-ranked queue, and `set_status` refuses to act without an audited reason. | *see below* | 22 |
| **A** | [a_deep_research_agent](a_deep_research_agent/README.md) | Turns an ideal customer profile into a sourced lead table; planner → 3 parallel researchers → critic loop → writer, each lead scored 1–5 by a deterministic tool. | *see below* | 22 |
| **D** | [d_code_review_agent](d_code_review_agent/README.md) | Reviews a Python file by path with AST, pycodestyle and complexity tools, then fixes it in a capped loop that emits a unified diff. | *see below* | 33 |
| **B** | [b_gemini_cli_agent](b_gemini_cli_agent/README.md) | Answers questions about a sandboxed code folder by driving the Gemini CLI as a function tool, returning a structured summary. | *see below* | 25 |
| **E** | [e_ecommerce_agent](e_ecommerce_agent/README.md) | Meeple Market board game shop over MCP + SQLite; every tool is scoped to a `user_id`, and out-of-stock items always return alternatives. | *see below* | 33 |

> **Status column is filled in by the final verification pass.** See
> [the verification note](#verification-and-the-quota-ceiling) below for what
> "verified" required and what blocked it.

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
`gemini-2.5-flash` call succeeds, the tool calls appear in the trace, and the
tests pass.

The hard constraint on the live half of that is the AI Studio free tier on this
key: **20 `generateContent` requests per day** for `gemini-2.5-flash`, plus a
**5 per minute** cap. `gemini-2.0-flash` and `gemini-2.5-flash-lite` both
return 404 "no longer available", so there is no second quota bucket to spread
load across.

That budget is small next to what these agents cost. One run of agent A is 7–11
model calls on its own. Two things follow, and both are visible in the code:

- Every agent builds its model with
  `HttpRetryOptions(http_status_codes=[429, 503, 504])` and long jittered
  backoff. Without it, agent A's parallel stage trips the per-minute cap
  immediately and the pipeline dies halfway.
- Every test suite runs without the API, so correctness is demonstrable
  regardless of quota.

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
