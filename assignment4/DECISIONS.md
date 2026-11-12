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
