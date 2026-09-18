# Stage 03 — Tool Registry

**The idea:** stop hard-coding `if name == "bash"`. Put every schema in a
list, every function in a dict, both keyed by the same tool name. Adding a
tool becomes one entry in each collection, never a new branch in the loop.

## Run it

```powershell
cd stage_03_tool_registry
..\..\stage_03_tool_registry\..\.venv\Scripts\python.exe main.py
```

(or, simpler, from `partA`: `.venv\Scripts\python.exe stage_03_tool_registry\main.py`)

## The code

Two files now, split along a seam that matters for every stage after this:

- **`tools.py`** owns tool definitions: the schema, the function, and the
  two collections that connect them.
- **`main.py`** owns the loop/dispatch: it doesn't know what tools exist,
  only that `TOOLS` describes them and `FUNCTIONS` runs them.

```python
TOOLS = [BASH_SCHEMA]
FUNCTIONS = {"bash": bash}
```

```python
fn = FUNCTIONS.get(name)
output = fn(**args)
```

`main.py` never mentions `"bash"` by name. It looks up whatever name the
model sent in `FUNCTIONS`, and calls it. Compare this to stage 02's
`if call.function.name == "bash":` — that branch is gone, replaced by a
dictionary lookup that works for any number of tools.

### Why this is the file to get right early

Stage 04 adds `read_file` by editing only `tools.py` — appending one entry
to `TOOLS` and one to `FUNCTIONS`. `main.py` will not change at all. That
only works because `main.py`'s dispatch code has no tool-specific logic in
it. If `main.py` still had an `if/elif` chain, every new tool would require
touching the loop file, and it would be easy to forget a case.

## Diff

```powershell
git diff --no-index stage_02_bash_tool stage_03_tool_registry
```
