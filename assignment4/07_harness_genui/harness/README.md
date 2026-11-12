# Stage 15 — Subagents

**The idea:** let the top-level agent delegate a self-contained
investigation to a fresh, second agent loop — its own empty transcript,
a deliberately restricted tool set, and only its final text answer
crossing back. The parent's own conversation never sees the subagent's
intermediate tool calls.

## Run it

```powershell
.venv\Scripts\python.exe stage_15_subagents\main.py
```

Ask for something like *"read through the skills folder and tell me
which skill mentions git"* and watch it delegate via `task` rather than
doing the reads itself.

## The code

`subagent.py` builds a second, smaller registry from the same base tools:

```python
WITHHELD = {"task", "write_todos", "write_file", "str_replace"}
SUBAGENT_TOOLS = [t for t in TOOLS if t["function"]["name"] not in WITHHELD]
SUBAGENT_FUNCTIONS = {name: fn for name, fn in FUNCTIONS.items() if name not in WITHHELD}
```

Four names are withheld, for two different reasons:

- **`write_todos`, `write_file`, `str_replace`** — a subagent can look
  around and report back, but it cannot change anything. Any edit has to
  happen in the main conversation, where the user can see it.
- **`task`** — a subagent cannot spawn another subagent. Leaving `task`
  out of `SUBAGENT_TOOLS` isn't just a preference the subagent might
  ignore: it's removed from both the schema list (so the model never
  learns the tool exists) and the function dict (so even a hallucinated
  call for it resolves to `"error: unknown tool 'task'"`). There is no
  recursion path, by construction, not by convention.

### A fresh, empty transcript

```python
def task(prompt: str) -> str:
    client = make_client()
    messages = [{"role": "user", "content": prompt}]
    for _ in range(MAX_SUBAGENT_TURNS):
        response = client.chat.completions.create(model=MODEL, messages=messages, tools=SUBAGENT_TOOLS)
        message = response.choices[0].message
        if not message.tool_calls:
            return message.content
        ...
```

`task()`'s `messages` starts from scratch — just the one prompt handed to
it. It doesn't see the parent's history, its skills, its todos, or its
git branch. It runs the same shape of loop as `run_loop` in `main.py`
(store the assistant message with its `tool_calls`, tie each result back
with `tool_call_id` — stage 05's rules apply here too), just with the
smaller tool set and its own client.

### Only the final answer returns

```python
if not message.tool_calls:
    return message.content
```

Everything the subagent did along the way — every `bash` call, every
`read_file`, every intermediate result — lives only inside `task()`'s
local `messages` list, which is thrown away the moment the function
returns. The parent's own transcript gains exactly one tool result: this
string. A subagent that read through ten files to answer one question
costs the parent's context one summary, not ten file dumps.

### Wiring `task` in at the top level only

```python
# main.py
ALL_TOOLS = TOOLS + [TASK_SCHEMA]
ALL_FUNCTIONS = {**FUNCTIONS, "task": task}
```

`tools.py`'s base `TOOLS`/`FUNCTIONS` never mention `task` — that would
let a subagent (which also imports from `tools.py`) inherit it, defeating
the whole restriction. `main.py` is the one place `task` gets layered
back on top, for the top-level loop only.

## Diff

```powershell
git diff --no-index stage_14_compaction stage_15_subagents
```
