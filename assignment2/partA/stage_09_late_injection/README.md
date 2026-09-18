# Stage 09 — Late Injection

**The idea:** some facts are volatile — the current time, the git branch,
the working directory — and change on every single call. Put them
somewhere that only affects the *request going out*, never the *transcript
we keep*.

## Run it

```powershell
.venv\Scripts\python.exe stage_09_late_injection\main.py
```

Ask "what time is it" or "what branch am I on" and it'll know, without
either fact ever having been stored as a message.

## The code

`context.py` has one function:

```python
def reminder():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    content = (
        "<system-reminder>\n"
        f"current_time: {now}\n"
        f"git_branch: {_git_branch()}\n"
        f"cwd: {os.getcwd()}\n"
        "</system-reminder>"
    )
    return {"role": "user", "content": content}
```

And `main.py`'s `run_loop` changed by exactly one expression:

```python
response = client.chat.completions.create(
    model=MODEL,
    messages=messages + [reminder()],   # was: messages=messages
    tools=TOOLS,
)
```

`messages + [reminder()]` builds a **new list** for this one call. It is
never assigned back to `messages`. The persisted transcript — the one that
grows across turns, gets the assistant's tool_calls appended to it, gets
tool results appended to it — never has a reminder message added to it.
Every outgoing request gets a freshly-built one glued onto the end.

## Why this preserves prefix caching

Go back to stage 01's `cached_tokens`. Providers that support prompt
caching look at how much of the *front* of a request is byte-identical to
a request they've already processed, and only charge (and re-process) the
part that changed. Caching only helps if the shared prefix is actually
shared — the same tokens, in the same order, unchanged.

If `reminder()`'s output had been appended to `messages` directly:

```
[system, user_1, reminder_1, assistant_1, tool_1, user_2, reminder_2, ...]
```

every single reminder — with a different timestamp — sits *in the middle*
of the transcript, at a different position each turn as the conversation
grows. Every request after the first reminder was inserted has a prefix
that differs from every previous request at that exact point, because
`reminder_1`'s timestamp is now baked into history forever. No later
request can share a long cached prefix with an earlier one, because the
volatile block keeps mutating what "the prefix" even is.

With late injection, the stored transcript is:

```
[system, user_1, assistant_1, tool_1, user_2, ...]
```

— completely stable turn over turn. The reminder only ever exists at the
very end of the one-off list built for a single outgoing call, never
inside the shared prefix. Turn 2's request shares its entire prefix (turns
0 through the end of turn 1) with turn 1's request, so a caching provider
can actually skip re-processing it.

This is the same idea behind the `<system-reminder>` tags you've likely
seen appended to messages in other agent harnesses — it's a real, load-
bearing pattern, not a toy invented for this assignment.

## Diff

```powershell
git diff --no-index stage_08_file_editing stage_09_late_injection
```
