# Part A — A Coding Agent Harness, Built From Scratch

A coding agent harness, built up progressively in 16 stages. Each stage is
its own self-contained, runnable directory that adds exactly **one** new
idea on top of the stage before it — no frameworks, no agent SDKs, just
the `openai` client (pointed at OpenRouter) and the Python standard
library.

Every stage folder has its own `README.md` that shows the stage's code,
explains what changed and why, and ends with a `git diff --no-index`
command against the previous stage — so you can see, in isolation,
exactly what that one idea added.

## Why OpenRouter

The harness talks to [OpenRouter](https://openrouter.ai) rather than
OpenAI directly — a hard requirement for this assignment, and also a
convenient one: OpenRouter exposes an OpenAI-compatible chat completions
API in front of many providers, so the same `openai` Python client works
unmodified, with only `base_url` and the API key changed. The default
model is `deepseek/deepseek-v4-flash-0731:free`, read from the `MODEL`
environment variable so it can be swapped without touching any code.

## The 16 stages

| # | Stage | The one new idea |
|---|-------|-------------------|
| 01 | [minimal_chat](stage_01_minimal_chat/) | One API call. Print the reply and token usage, including `cached_tokens`. |
| 02 | [bash_tool](stage_02_bash_tool/) | A JSON schema + a Python function = one tool. Single call, no loop — the model proposes, the code disposes. |
| 03 | [tool_registry](stage_03_tool_registry/) | Schemas in a list, functions in a dict, same keys. A new tool is one entry in each. |
| 04 | [read_file](stage_04_read_file/) | A second tool, added by editing only `tools.py` — the loop file (`main.py`) never changes. |
| 05 | [agent_loop](stage_05_agent_loop/) | Feed tool results back until the model answers in text. Store the assistant's `tool_calls`; tie each result to its call with `tool_call_id`. |
| 06 | [chat_ui](stage_06_chat_ui/) | An outer loop asks for the next message. All drawing moves into `ui.py`, which knows nothing about models or tools. |
| 07 | [skills](stage_07_skills/) | `SKILL.md` files with YAML front matter. Only name + description ride in the system prompt; the body loads on demand via `read_skill`. |
| 08 | [file_editing](stage_08_file_editing/) | `write_file` and `str_replace`. `str_replace` refuses on zero or multiple matches — the refusal is a tool result, not an exception. |
| 09 | [late_injection](stage_09_late_injection/) | Volatile facts (time, git branch, cwd) ride in a block appended to the *request* only (`messages + [reminder()]`), never stored — this is what keeps the stored prefix stable enough for prompt caching to work. |
| 10 | [sessions](stage_10_sessions/) | Every message appended to JSONL as it happens. `/rewind` writes a marker, not a delete. `--resume` replays the log. |
| 11 | [todos](stage_11_todos/) | `write_todos` replaces the whole list and requires exactly one `in_progress` item. The list rides in the same late block as stage 09. |
| 12 | [permissions](stage_12_permissions/) | A rule table rates every command allow / ask / deny. Compound commands split on `&&`/`\|`; the strictest verdict wins. Honestly *not* real security. |
| 13 | [sandbox](stage_13_sandbox/) | OS-level enforcement: Seatbelt (macOS), bubblewrap (Linux). Windows prints `sandbox: none` and says why, rather than faking it. Every command gets a timeout. |
| 14 | [compaction](stage_14_compaction/) | Four mechanisms, cheapest first: cap oversized fresh results to a temp file, shrink finished-turn results to a stub, drop old results outright, and — last resort — a no-tools summarizer that writes a handoff note past 85% of the window. |
| 15 | [subagents](stage_15_subagents/) | A `task` tool runs a second, independent agent loop with an empty transcript and every tool *except* `task`, `write_todos`, `write_file`, `str_replace` — it can look, but not edit or recurse. Only its final answer returns. |
| 16 | [openrouter_routing](stage_16_openrouter_routing/) | An ordered `MODELS` fallback route. `usage.include: true` gets the real dollar cost back from OpenRouter. `/models` and `/route` inspect and change the route at runtime; cost prints per call and as a session total on exit. |

## Quick start

```powershell
# from Assignment2\partA
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

Copy-Item .env.example .env
notepad .env   # fill in your real OPENROUTER_API_KEY

.\.venv\Scripts\python.exe stage_16_openrouter_routing\main.py
```

Any earlier stage runs the same way — swap the path:

```powershell
.\.venv\Scripts\python.exe stage_01_minimal_chat\chat.py
.\.venv\Scripts\python.exe stage_06_chat_ui\main.py
```

## Running the tests

```powershell
.\.venv\Scripts\python.exe run_tests.py
```

`run_tests.py` runs every stage against a **fake model** — no API key
needed, no network call made. Each stage's entry file is imported fresh
(with its own directory on `sys.path`, so same-named sibling files like
`tools.py` never collide between stages), its client factory
(`make_client`) is monkeypatched to return a scripted fake client, and
the stage's real code path — its loop, its tool dispatch, its slash
commands — runs exactly as it would against the real API. One line per
stage, ending in `passed`:

```
stage_01_minimal_chat: passed
stage_02_bash_tool: passed
...
stage_16_openrouter_routing: passed

all 16 stages passed.
```

## Layout

```
partA/
  README.md              <- this file
  requirements.txt
  .env.example
  run_tests.py
  stage_01_minimal_chat/
  stage_02_bash_tool/
  ...
  stage_16_openrouter_routing/
```

Every `stage_NN_*/` directory is self-contained and runnable on its own —
copy it out of this repo and it still works, given a `.env` with an
`OPENROUTER_API_KEY`.
