# Stage 08 — File Editing

**The idea:** give the model the ability to actually change files, with a
safety rail built into the tool itself: `str_replace` will not guess which
occurrence you meant. It refuses on zero matches (you mistyped the target)
and on multiple matches (the edit is ambiguous) — and the refusal comes
back as a normal tool result, not a crash, so the model can look at why it
failed and try again with more context.

## Run it

```powershell
.venv\Scripts\python.exe stage_08_file_editing\main.py
```

Try: *"in some_file.py, change the word foo to bar"* where `foo` appears
twice — watch the model get a refusal, then retry with a more specific
`old_str`.

## The code

Two new functions in `tools.py`:

```python
def write_file(path: str, content: str) -> str:
    ...
    return f"wrote {len(content)} bytes to {path}"
```

`write_file` is unconditional — it creates or fully overwrites a file.

```python
def str_replace(path: str, old_str: str, new_str: str) -> str:
    ...
    count = text.count(old_str)
    if count == 0:
        return f"error: old_str not found in {path}. No changes made."
    if count > 1:
        return (f"error: old_str matches {count} times in {path}, must match "
                 "exactly once. Add more surrounding context ...")
    new_text = text.replace(old_str, new_str, 1)
    ...
```

`str_replace` is the interesting one. It reads the file, counts how many
times `old_str` appears, and only writes anything back if the count is
exactly 1. Both failure paths return a plain string starting with
`"error:"` — they never raise.

### Why the refusal has to be a *result*, not an exception

If `str_replace` raised on an ambiguous match, the exception would have to
be caught somewhere well above the tool-dispatch code, and by the time it
got there, there's no clean way to tell the model *why* its edit failed —
the conversation would just end or crash. Returning the refusal as the
tool's result means it gets appended to `messages` exactly like a
successful result would:

```python
messages.append({"role": "tool", "tool_call_id": call.id, "content": str(result)})
```

The model reads `"error: old_str matches 2 times..."` in its own
transcript on the next turn and can react to it — usually by picking a
longer, more specific `old_str` and calling `str_replace` again. This is
the same "errors are results" rule stage 05 introduced for unknown tool
names and tool exceptions; `str_replace` is just the tool where getting it
right actually matters, because a silent wrong-occurrence edit would be a
real bug in the user's file.

### main.py didn't change

Same story as stage 04: two new schemas, two new dict entries, and the
loop in `main.py` dispatches them with no new code.

## Diff

```powershell
git diff --no-index stage_07_skills stage_08_file_editing
```
