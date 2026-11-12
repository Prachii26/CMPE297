# Decisions

One line per call made without asking.

1. Folder is `assignment4` (lowercase), matching `assignment1`–`assignment5` at the repo root.
2. The agent in every theme is a scripted function returning what a model would emit; no keys, no network at runtime.
3. Dependencies per theme are pinned in that theme's requirements.txt (FastAPI, uvicorn, pytest, httpx, plus jsonschema / rich where a theme needs them); installs need the network once, runs never do.
4. Screenshots come from real browser runs via `tools/shoot.py`, using Playwright from the assignment 3 screenshot venv rather than adding Playwright to any theme's dependencies.
5. Theme 01's catalog has eight components (Stack, Heading, Text, MetricCard, RoomTable, OccupancyChart, BookingForm, Button); mixed mode adds exactly one `SandboxedHtml`.
6. The JSON Schema is generated from the catalog in code, so schema and catalog cannot drift.
7. The partial-JSON parser drops half-written strings and dangling keys rather than guessing, so the renderer only ever sees a prefix of the final value.
8. Flat element maps are emitted structure-first (containers with child-id lists, then leaves): ids make that order legal, and it is the shape's real advantage.
9. The streaming measurement reports both sides — flat fixes layout at 21% of the stream vs 96% for nested, but nested paints its first leaf sooner and is 16% shorter.
10. The CSP is injected into generated HTML by the server, not trusted to the agent; the sandbox token list (`allow-scripts` only) is sent by the server and applied verbatim by the page.
11. Open-ended HTML is mounted only once complete; streaming a half-written document into srcdoc is unreliable.
12. Theme 02 implements the AG-UI events by hand (no SDK), framed as one SSE `data:` line per event with a `type` field, camelCase fields per the spec.
13. Static and open-ended modes travel as frontend tool calls (`show_component`, `render_html`); declarative and mixed travel as shared state built by JSON Patch deltas — so the four modes visibly use different carriers on one transport.
14. The CSP is injected before HTML is placed in tool-call arguments, because those arguments stream to the page; a server-edge rewrite would be too late.
15. The page reads the AG-UI stream with fetch + a stream reader, because EventSource cannot POST a RunAgentInput.
16. Theme 03 writes A2UI v0.8 envelopes by hand; data-model arrays are encoded as index-keyed valueMaps with an isList marker — our reading of the contract, stated as such.
17. The server validates every A2UI component against the catalog the client advertised in that request, and drops anything else with an error line, so a client never receives a component it cannot render.
18. A2UI static mode = client-owned surface template + agent-sent dataModelUpdate only; open-ended = a client-advertised HtmlArtifact escape hatch, documented as contrary to A2UI's design.
19. A2UI responses stream as JSON Lines over a plain POST response — the format is independent of transport, so no AG-UI wrapper was added.
20. Theme 05 validates every patch against the mode's catalog before forwarding it; invalid patches become error lines and are never applied by either renderer.
21. json-render static mode = a client-owned skeleton where the server only accepts `replace` on props; `add` is refused.
22. The terminal renderer shows HtmlArtifact as a placeholder with the byte count — a terminal cannot run HTML, and the README says that is where one catalog / two renderers breaks down.
23. In json-render open-ended mode a booking re-sends the whole HTML prop, because there is no structured element to patch.
24. Terminal screenshots are rich's SVG export from real runs, rasterised to PNG with Playwright (tools/svg_to_png.py).
