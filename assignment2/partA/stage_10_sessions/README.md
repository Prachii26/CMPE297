# Stage 10 — Sessions

**The idea:** persist the conversation to disk as it happens, not at exit.
Every message gets appended to a JSONL file the instant it's added to
`messages`. `/rewind` doesn't delete anything from that file — it appends
a marker saying where the effective transcript now ends. `--resume`
replays the file to rebuild `messages` exactly as they last stood.

## Run it

```powershell
.venv\Scripts\python.exe stage_10_sessions\main.py
# ... chat, then Ctrl+C ...
.venv\Scripts\python.exe stage_10_sessions\main.py --resume
```

Sessions land in `stage_10_sessions\sessions\<timestamp>.jsonl` (gitignored).

## The code

`sessions.py` is four small functions built around one file format: one
JSON object per line.

```python
def log_message(session_id, message):
    append_event(session_id, {"type": "message", "message": message})

def log_rewind(session_id, to_index):
    append_event(session_id, {"type": "rewind", "to_index": to_index})
```

Every append happens right where `main.py` already appends to `messages`
in memory — there's no separate "save" step, no buffering, no write on
exit. If the process is killed mid-turn, the file already has everything
up to that point.

### /rewind writes a marker, it doesn't delete

```python
def handle_slash_command(command, session_id, messages):
    if command == "/rewind":
        turn_starts = [i for i, m in enumerate(messages) if m["role"] == "user"]
        to_index = turn_starts[-1]
        del messages[to_index:]
        log_rewind(session_id, to_index)
```

`del messages[to_index:]` only changes the in-memory list for the rest of
this run. On disk, `log_rewind` appends a `{"type": "rewind", "to_index": N}`
event — the original messages are still sitting in the file, untouched.
Replaying the file is what makes the cut "real":

```python
def load_messages(session_id):
    messages = []
    for event in ...:
        if event["type"] == "message":
            messages.append(event["message"])
        elif event["type"] == "rewind":
            messages = messages[: event["to_index"]]
    return messages
```

A rewind marker truncates the *replayed* list, not the file. This is the
same append-only-log-plus-tombstone idea a database uses to support undo
without losing the audit trail — you can always tell a rewind happened
and see exactly what it cut, because the cut messages are still on disk.

### Slash commands never reach the model

```python
if user_input.startswith("/"):
    handle_slash_command(user_input.strip(), session_id, messages)
    continue
```

That `continue` happens before `user_input` is ever appended to `messages`
or logged. `/rewind` is resolved entirely inside `handle_slash_command` —
no request goes out, `run_loop` never runs, and the command text itself
never becomes part of the conversation the model sees.

### --resume

```python
if resume:
    session_id = latest_session_id()
    messages = load_messages(session_id) if session_id else []
```

`latest_session_id()` picks whichever `.jsonl` file was modified most
recently. `load_messages` replays it (respecting any rewind markers) and
that becomes the starting `messages` list — the conversation picks up
exactly where the last run left it, including anything that was rewound.

## Diff

```powershell
git diff --no-index stage_09_late_injection stage_10_sessions
```
