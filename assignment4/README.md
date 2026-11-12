# Assignment 4 — Generative UI codelabs

**Demo video:** YOUTUBE_VIDEO_LINK

Seven progressive codelabs on one running example — a **campus study-room
booking dashboard** (room list, availability metrics, an occupancy chart, a
booking form, a confirm action) — showing A2UI, AG-UI, MCP Apps, json-render,
OpenUI Lang and a render tool on my own agent harness, each across four
generation modes.

## Two decisions, kept separate

Every theme answers two different questions, and every README keeps them apart:

1. **Generation mode — what the agent emits.**
2. **Transport — how the UI reaches the user.** **AG-UI** is an event stream.
   **MCP Apps** is a host mounting a `ui://` resource. **A2UI, OpenUI Lang and
   json-render are UI description formats, not transports** — here they travel
   over plain HTTP responses, and could ride AG-UI or anything else unchanged.

## The four generation modes

| mode | the agent… | who owns layout |
|---|---|---|
| **static** | names a prebuilt component and supplies its props | **we do** |
| **declarative** | composes a layout from a catalog we allow | the agent, inside the catalog |
| **open-ended** | writes raw HTML, rendered in a sandbox | the agent, completely |
| **mixed** | uses the catalog by default, plus one open-ended region | the agent, with one sandboxed exception |

Where a system does not naturally support a mode, the theme implements the
closest honest thing and its README says why the combination is awkward —
for example open-ended A2UI needs a client-advertised `HtmlArtifact` that
contradicts A2UI's own premise, and a terminal renderer can only show a
placeholder for HTML.

## The themes

| theme | status | tests | one line |
|---|---|---|---|
| [01 · foundations](01_foundations/) | **WORKING** | 6 | the four modes with no library; measured: a flat element map fixes the layout at 21% of the stream, a nested tree at 96% |
| [02 · AG-UI](02_ag_ui/) | **WORKING** | 5 | hand-written AG-UI events over SSE; all four modes on one transport; a user's state patch read by the agent |
| [03 · A2UI](03_a2ui/) | **WORKING** | 5 | structure and data as two JSONL streams; the client advertises its catalog; an action patches, not replaces |
| [04 · OpenUI Lang](04_openui_lang/) | **WORKING** | 5 | our own parser with forward references; measured tokens: 460 vs 499 (json-render) vs 1132 (A2UI), cl100k |
| [05 · json-render](05_json_render/) | **WORKING** | 7 | a spec built only by validated patches; actions; one catalog, a web and a terminal renderer |
| [06 · MCP Apps](06_mcp_apps/) | **WORKING** | 5 | an MCP server with a `ui://` app, a minimal host and a two-way JSON-RPC bridge; fetch and a forbidden tool blocked |
| [07 · harness GenUI](07_harness_genui/) | **WORKING** | 7 | `render_ui` on **my own stage 15 harness from assignment 2**; terminal + web from one agent; mixed rule enforced in the tool |

**40 offline tests, all passing** (each theme in its own venv). Every theme
has one screenshot per mode from a real browser run in its `docs/`.

Comparison across the six systems, with the token and streaming measurements:
**[docs/comparison.md](docs/comparison.md)**.

## The agent is scripted — deliberately

In every demo the agent is a **scripted function returning exactly what a
model would emit** for that prompt. There are no API keys, no network calls at
runtime, and no cost. This is a deliberate choice: it makes every run
reproducible, keeps the four modes comparable (they differ only in what the
agent is allowed to emit), and keeps the subject — the generation mode and the
transport — free of model noise. Everything around the agent is real: the
servers, the streams, the validators, the renderers, the sandboxes and the
bridges. In theme 07 the scripted client is shaped like the OpenAI SDK so my
harness's unmodified loop drives it; `HARNESS_SCRIPTED=0` switches back to the
original OpenRouter client.

## Run everything

Windows PowerShell. Each theme is self-contained with its own `.venv`, and
listens on its own port (theme 01 on 8001 … theme 07 on 8007).

```powershell
cd assignment4\01_foundations       # or any theme folder
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe server.py                 # then open http://127.0.0.1:8001
.\.venv\Scripts\python.exe server.py --mode mixed    # open in a given mode (all four selectable)
.\.venv\Scripts\python.exe -m pytest tests -q
```

| theme | start | extra |
|---|---|---|
| 01 | `server.py` → :8001 | `measure_stream.py` |
| 02 | `server.py` → :8002 | |
| 03 | `server.py` → :8003 | |
| 04 | `server.py` → :8004 | `measure_tokens.py` |
| 05 | `server.py` → :8005 | `terminal.py --mode declarative --book ENG-112` |
| 06 | `server.py` → host on :8006 | |
| 07 | `server.py --mode mixed --prompt "…interactive room picker"` → :8007 | `harness\main.py --mode declarative [--web]` |

Screenshots were taken with `tools/shoot.py` / `tools/shoot_action.py`
(Playwright; not a theme dependency).

## Files

```
01_foundations/ … 07_harness_genui/   one theme each: server.py, page/, tests/, docs/, README.md, requirements.txt
docs/comparison.md                    the six systems side by side, plus the measurements
tools/                                screenshot helpers used for docs/
DECISIONS.md                          every judgement call, one line each
PROMPTS.md                            every prompt for this assignment, verbatim
```

## Source

Structure and vocabulary: the GenUI course,
<https://raw.githubusercontent.com/dlmastery/simple-coding-harness/main/genui/README.md>,
and its theme READMEs. No code was copied; the domain, implementations and
measurements are ours.
