# Six systems, compared

Two separate questions run through every row:

- **Generation mode** — what the agent emits: *static* (names a prebuilt component, we own layout), *declarative* (composes a layout from an allowed catalog), *open-ended* (writes raw HTML, sandboxed), *mixed* (catalog by default, one open-ended region).
- **Transport** — how the UI reaches the user. Only two of the six are transports: **AG-UI** (an event stream) and **MCP Apps** (a host mounting a `ui://` resource). **A2UI, OpenUI Lang and json-render are UI description formats** and can ride any transport.

Everything below is what our implementations in this assignment do — not
the full feature set of each project.

## The table

| system | what kind of thing it is | generation modes, as built here | transport used here | payload format | where validation happens | security boundary | when you would pick it |
|---|---|---|---|---|---|---|---|
| **No library** (theme 01) | the mechanism itself | all four natively — that is the point of the theme | plain SSE | `{component, props}` events; a JSON element map streamed in chunks; raw HTML | server: JSON Schema **generated from the catalog**, plus graph checks; client: renderer keyed by name draws nothing else | `iframe sandbox="allow-scripts"` + a CSP the server injects; one accepted `postMessage` shape | to understand the trade-offs, or when you need full control and few moving parts |
| **AG-UI** (theme 02) | **transport** — typed agent↔frontend events | all four on one stream: static and open-ended as frontend **tool calls**, declarative and mixed as **shared state** grown by JSON Patch | SSE from `POST /agent` (`RunAgentInput` in, events out) | `RUN_*`, `TEXT_MESSAGE_*`, `TOOL_CALL_*`, `STATE_SNAPSHOT`, `STATE_DELTA` (RFC 6902) | server validates the planned surface against the catalog before the first delta; an invalid one becomes `RUN_ERROR` and no delta | inherits whatever the payload needs (here the theme 01 sandbox + CSP, injected **before** HTML enters tool-call arguments) | the agent lives in your product and you need streaming text, tool calls and shared state between agent and page |
| **A2UI** (theme 03) | **format** — declarative UI as data | declarative natively; static = client-owned surface + agent sends **data only**; open-ended only via a client-advertised `HtmlArtifact` (contrary to A2UI's "UI as data, not code" premise) | JSON Lines over a plain POST (could ride AG-UI) | `surfaceUpdate` (flat components with ids, props bound to data paths), `dataModelUpdate` (separate data model), `beginRendering`, `userAction` | server validates every component against the catalog **the client advertised** in that request; anything else is dropped | no code by default; the escape hatch, if advertised, is sandboxed | structure and data change at different rates, or a client must constrain what any agent can send it |
| **OpenUI Lang** (theme 04) | **format** — a compact line-oriented language | declarative natively; static = client-owned layout program whose names the agent fills with **values** (forward references); open-ended and mixed via `HtmlArtifact` statements | chunked plain text | `name = Component(positional args)`, one statement per line, forward references | server checks each statement (catalog, arity, static values-only) and replaces a rejected one with a comment; client parses complete lines only | as for its `HtmlArtifact`: sandbox + CSP | token budget matters and the payload is structure-heavy; streaming line by line with placeholders |
| **json-render** (theme 05) | **format** — catalog + spec + patches + actions | declarative natively; static = client-owned skeleton, agent may only `replace` props; open-ended via `HtmlArtifact`, which a terminal cannot draw | JSON Lines over HTTP | flat element map built and changed only by RFC 6902 patches; actions `{name, params}` | **every patch** is applied to a server copy and the result validated against per-component prop schemas before it is forwarded | catalog-only by design; the HTML escape hatch is sandboxed on the web and a placeholder in the terminal | one catalog has to serve several renderers (web and terminal here), with incremental updates and actions |
| **MCP Apps** (theme 06) | **transport** — a host mounts your UI | open-ended **by construction** (the host mounts whatever HTML the `ui://` resource holds); the other modes here are our own catalog convention in `structuredContent`, not part of MCP Apps | MCP JSON-RPC (server) + JSON-RPC over `postMessage` (app ⇄ host) | tool with `_meta.ui.resourceUri`; resource `text/html;profile=mcp-app` with `_meta.ui.csp`; `ui/initialize`, `tool-input`/`tool-result`, `tools/call` | server checks our catalog payloads; the **host** decides what the app may call | the **host's** sandbox and the CSP it builds from `_meta.ui.csp`, plus the host's tool allowlist — verified: `fetch` blocked, a forbidden tool refused | the agent lives in someone else's chat client and you are shipping an interactive view to it |

Theme 07 is not a seventh system: it puts a json-render style
`render_ui(spec)` tool into **my own stage 15 harness** from assignment 2,
with a terminal and a browser surface, and enforces the mixed-mode rule
(one `HtmlArtifact`, only for interactive requests) inside the tool.

## Token measurements (theme 04)

The same study-room interface — 1 heading, 3 metrics, 7 chart points, 6 rooms
× 6 fields, a form with 3 rooms and 4 slots, a button — encoded three ways and
counted with tiktoken `cl100k_base` and `o200k_base` (BPE files vendored, run
offline). Method: [04_openui_lang/measure_tokens.py](../04_openui_lang/measure_tokens.py).

| format | chars | cl100k_base | o200k_base | × OpenUI Lang |
|---|---|---|---|---|
| OpenUI Lang | 1327 | **460** | **459** | 1.00× |
| json-render JSON, compact | 1706 | 499 | 495 | 1.08× |
| json-render JSON, pretty | 3415 | 908 | 900 | 1.97× |
| A2UI JSONL, compact | 4199 | 1132 | 1167 | 2.46× |
| A2UI JSONL, pretty | 11045 | 2311 | 2303 | 5.02× |

On this data-heavy interface OpenUI Lang is **8% smaller than compact
json-render**. The big multiples come from A2UI's typed data-model entries and
from pretty-printed JSON, not from the language alone.

## Streaming measurement (theme 01)

The same dashboard as a nested tree and as a flat element map, streamed in
40-character chunks:

| shape | first leaf painted | layout fixed |
|---|---|---|
| nested tree | chunk 4 of 45 | chunk 43 of 45 (96%) |
| flat element map, structure first | chunk 13 of 53 | chunk 11 of 53 (21%) |

The flat map fixes every slot early and never reflows; the nested tree paints
something sooner but keeps rearranging until the end, and is 16% shorter.
