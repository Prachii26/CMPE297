# Stage 04 — read_file, Without Touching the Loop

**The idea:** prove the registry pays off. Add a second tool, `read_file`,
by editing only `tools.py`. `main.py` — the file that sends the request and
dispatches the call — does not change at all.

## Run it

```powershell
.venv\Scripts\python.exe stage_04_read_file\main.py
```

## The code

`main.py` in this stage is byte-for-byte identical to stage 03's:

```powershell
git diff --no-index stage_03_tool_registry\main.py stage_04_read_file\main.py
# (no output -- the files are the same)
```

`tools.py` gained one function and one schema:

```python
def read_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError as exc:
        return f"error reading {path}: {exc}"

TOOLS = [BASH_SCHEMA, READ_FILE_SCHEMA]
FUNCTIONS = {"bash": bash, "read_file": read_file}
```

`read_file` catches its own errors and returns them as a string instead of
letting an exception escape — a small preview of stage 08's rule that tool
failures are results, not exceptions.

### Where the file's content actually goes

Run this and ask the model to read a file. The content prints to **your
screen** — inside `main.py`'s `print("--- tool output ---")` block — but it
never goes back to the model. There is still no loop: the model's very
first response is also its last. If you ask the model something that
requires it to *look at* the file's contents (summarize it, count
something in it), it can't, because it never sees what `read_file`
returned. It only knows it asked for the read.

This is deliberate, and it's the last stage where it's true. Stage 05 adds
the loop that feeds tool results back as messages, and only then can the
model actually reason about what a tool gave it.

## Diff

```powershell
git diff --no-index stage_03_tool_registry stage_04_read_file
```
