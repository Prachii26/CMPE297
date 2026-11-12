# Prompts

Every prompt sent for this assignment, verbatim and in order.

---

## Prompt 1

```text
Assignment 4 for CMPE 297: build a GenUI codelab series demonstrating A2UI, AG-UI, MCP Apps, json-render, OpenUI Lang and harness integration, each across four generation modes.

## Location
Create assignment4 at the root of the CMPE297 repo, parallel to the existing Assignment1, assignment2, assignment3 and assignment5 folders. Do not nest it inside any of them. List the repo root first and match the existing casing convention.

Structure:
  assignment4/
    01_foundations/
    02_ag_ui/
    03_a2ui/
    04_openui_lang/
    05_json_render/
    06_mcp_apps/
    07_harness_genui/
    docs/
    README.md
    PROMPTS.md
    DECISIONS.md

I am on Windows PowerShell. Write every command in PowerShell syntax.

## The conceptual spine — this is what is actually being graded
Two decisions are separate, and every README must keep them separate:
- GENERATION MODE: what the agent emits. static (agent names a prebuilt component and supplies props; you own layout) / declarative (agent composes a layout from a catalog you allow) / open-ended (agent writes raw HTML, rendered in a sandbox) / mixed (catalog by default, one open-ended region).
- TRANSPORT: how the UI reaches the user. AG-UI is an event stream. MCP Apps is a host mounting a ui:// resource. A2UI, OpenUI Lang and json-render are UI DESCRIPTION formats, not transports.

Where a system does not naturally support a mode, implement the closest honest thing and say in the README why the combination is awkward. An honest note beats a forced demo. Never claim a system does something it does not.

## Ground rules
- Python 3.11 + FastAPI backend, vanilla JS frontend, no build step, no npm, no React. One .venv per theme.
- The agent in every demo is SCRIPTED: a function returning exactly what a model would emit for that prompt. No API keys, no network at runtime, everything offline at zero cost. State this in the top-level README as a deliberate choice.
- Running example across all themes: a campus study-room booking dashboard (room list, availability metrics, an occupancy chart, a booking form, a confirm action). Do NOT use the lemonade stand from the reference course.
- Ports: theme 01 on 8001 through theme 07 on 8007.
- Read https://raw.githubusercontent.com/dlmastery/simple-coding-harness/main/genui/README.md and the theme READMEs under that path for structure and vocabulary. Do NOT copy code. Write our own, in our own domain. Cite it in each README.
- Do not ask me questions. Make a call, log one line in DECISIONS.md.
- Commit and push after each theme.

## Timeboxing — I am recording another assignment's video while you work
45 minutes hard cap per theme. At the cap, commit what works, mark the theme PARTIAL in its README with the exact error and what is missing, and move to the next one. Do not fake a pass and do not overrun. Six working themes and one honest PARTIAL beats four perfect ones.

## Per-theme definition of done
- server.py (FastAPI), page/index.html, page/app.js
- A --mode flag or modes/ subfolder covering static, declarative, open_ended and mixed
- README.md: what this theme adds, a mermaid diagram, the four modes with what the agent emits in each, run commands, what to look at in the code, limits, source cited
- requirements.txt
- tests/ with at least 3 offline pytest tests (spec shape validates, out-of-catalog component is rejected, sandbox attributes are present)
- docs/ with one screenshot per mode from a real run

Verified means the server starts, the page renders, all four modes produce visibly different output, and the tests pass.

## The seven themes

01_foundations — the four modes with no library at all, so the mechanism is visible before libraries hide it.
Static: three components exist in code; the scripted agent emits {"component","props"} over SSE; a hand-written renderer keyed by name draws them. Declarative: a catalog of eight components, a JSON Schema derived from it, the agent writes the whole layout, the page renders while the document streams using a tolerant partial-JSON parser. Open-ended: no catalog, the agent writes the page, mounted in an iframe sandbox with a Content Security Policy. Mixed: catalog plus one sandboxed region.
Our addition: instrument the declarative step to measure at which streamed chunk the layout becomes known for a nested tree versus a flat element map with ids. Put the real numbers in the README. That measurement is why A2UI and json-render both use the flat shape, and we should show it rather than assert it.

02_ag_ui — the event protocol. Implement the AG-UI event types we need over SSE: run lifecycle, text message start/content/end, tool call start/args/end, state snapshot and state delta. Show all four generation modes riding the same transport, which is the point. Include a state patch demo where a user action updates shared state and the agent sees it.

03_a2ui — Google's declarative spec. A component catalog the client advertises, a flat element map with ids, a separate data model, JSONL streaming so structure and data change independently. Show a user action going back to the agent and the agent patching the existing surface rather than replacing it.

05_json_render — catalog, spec, patches, actions. A validated element map against a catalog with per-component prop schemas, incremental patches that update a rendered spec in place, actions calling back into the server, and a second render target (terminal, using rich) driven by the same spec — one catalog, two renderers.

04_openui_lang — the compact language. Write our own parser for the line-oriented syntax (identifier = Component(args), forward references, streaming-first). Render it with theme 03's catalog. Then measure: count tokens for the same study-room interface as OpenUI Lang, as A2UI JSON, and as json-render JSON, using a stated tokenizer. Put our own numbers and the method in the README. Do not quote the 67% marketing figure — measure ours and say what we measured.

06_mcp_apps — a different host owns the surface. An MCP server exposing a tool whose _meta.ui.resourceUri points at a ui:// resource serving HTML. Build a minimal host page that mounts it in a sandboxed iframe and speaks MCP JSON-RPC over postMessage both directions: host passes tool data in, the UI calls another tool out. This is open-ended by construction, so for the other modes show the same host rendering a catalog-constrained payload. Explain in the README what the sandbox actually prevents and what it does not.

07_harness_genui — the one that matters most, and the differentiator.
Wire a rendering surface onto MY OWN harness from assignment2/partA. Read that code first. Add a render_ui(spec) tool to the stage 15 loop: the spec is a json-render style element map validated against a six-component catalog. Two surfaces from one agent — a terminal renderer using rich, and --web serving the same spec to a browser page over SSE. Then a mixed step where the agent may emit one sandboxed HtmlArtifact alongside catalog components, with CSP, only when the user asks for something interactive.
In the README, state explicitly that this harness is my own from assignment 2, link to it, and name which stage is being extended.

## Top-level deliverables
- assignment4/README.md: what this is, the generation-vs-transport distinction stated up front, a table of the seven themes with status (WORKING or PARTIAL) and one line each, the four modes defined once, run commands, and a single YOUTUBE_VIDEO_LINK placeholder near the top.
- docs/comparison.md: a table across the six systems — generation modes supported, transport, payload format, where validation happens, what the security boundary is, when you would pick it. Include theme 04's token measurements.
- PROMPTS.md: every prompt I send for this assignment, verbatim, in order, from session history. Invent nothing.
- Run every test suite, report counts per theme.
- Grep for AIza and sk-, confirm no hits. Confirm .venv/ is gitignored.

## Order
Build 01 first and get the four modes genuinely working, since every later theme reuses that vocabulary. Then 02, 03, 05, 04, 06, 07. Report after 01, then work straight through without stopping unless something is unrecoverable.
```
