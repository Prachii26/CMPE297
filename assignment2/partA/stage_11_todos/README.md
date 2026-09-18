# Stage 11 — Todos

**The idea:** give the model a scratchpad for multi-step plans, with one
rule enforced at the boundary: exactly one item can be `in_progress` at a
time. The list itself is a plain variable, and it reaches the model the
same way the clock does — through stage 09's late-injection block, never
as a stored message.

## Run it

```powershell
.venv\Scripts\python.exe stage_11_todos\main.py
```

Ask for something with several steps and watch it call `write_todos`,
then see the list show up in its own reminder block on the next turn.

## The code

`todos.py` holds the state and the one rule:

```python
def write_todos(todos: list) -> str:
    for item in todos:
        if item.get("status") not in VALID_STATUSES:
            return f"error: invalid status {item.get('status')!r} ... No changes made."

    in_progress = [item for item in todos if item["status"] == "in_progress"]
    if todos and len(in_progress) != 1:
        return f"error: exactly one todo must be in_progress, got {len(in_progress)}. No changes made."

    global TODOS
    TODOS = todos
    return f"todo list updated, {len(TODOS)} item(s)"
```

`write_todos` **replaces** the whole list — there's no `add_todo` or
`mark_done`. That's deliberate: with only one write path, there's only one
place to validate, and the model has to resend the full list (with its
one `in_progress` item) every time it wants to change anything. If the
validation fails, `TODOS` is left exactly as it was — the assignment to
the global only happens after every check passes, and the error string is
returned as an ordinary tool result, same as `str_replace`'s refusals in
stage 08.

### Riding in the late block

```python
def todos_block():
    if not TODOS:
        return ""
    marks = {"pending": "[ ]", "in_progress": "[~]", "completed": "[x]"}
    lines = ["current todos:"]
    for item in TODOS:
        lines.append(f"{marks.get(item['status'], '[?]')} {item['content']}")
    return "\n".join(lines)
```

`context.py`'s `reminder()` calls this and appends the result inside the
same `<system-reminder>` block as the time and git branch:

```python
lines = ["<system-reminder>", f"current_time: {now}", f"git_branch: {_git_branch()}", f"cwd: {os.getcwd()}"]
todos_text = todos_block()
if todos_text:
    lines.append(todos_text)
```

The todo list is exactly as volatile as the clock from the model's point
of view — it can change every single turn — so it belongs in exactly the
same place: spliced into the outgoing request, never written into
`messages`. That's what the test for this stage actually checks: after
`write_todos` runs, the *next* request's reminder block contains
`"look at tools.py"`, but no persisted message in that same request does.

### main.py didn't change

Same pattern as stage 04 and stage 08: one new schema, one new dict entry
in `tools.py`, and `main.py`'s dispatch loop handles it with no new code.

## Diff

```powershell
git diff --no-index stage_10_sessions stage_11_todos
```
