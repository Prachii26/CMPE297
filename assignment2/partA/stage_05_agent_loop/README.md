# Stage 05 — The Agent Loop

**The idea:** stop stopping after one tool call. Keep feeding results back
to the model until it answers in plain text. This is the stage where the
program becomes an *agent* rather than a single request/response.

## Run it

```powershell
.venv\Scripts\python.exe stage_05_agent_loop\main.py
```

Ask it something that needs two hops (read a file, then reason about what
it read) and watch it actually use the second hop — stage 04 couldn't.

## The code

`run_loop` replaces the one-shot call:

```python
def run_loop(client, messages):
    for _ in range(MAX_TURNS):
        response = client.chat.completions.create(model=MODEL, messages=messages, tools=TOOLS)
        message = response.choices[0].message

        if not message.tool_calls:
            return message.content
        ...
```

It keeps calling the model with a growing `messages` list until a response
comes back with no `tool_calls` — that's the model's way of saying "I'm
done, here's my answer."

### Rule 1 — store the assistant message, tool_calls and all

```python
messages.append({
    "role": "assistant",
    "content": message.content,
    "tool_calls": [
        {"id": call.id, "type": "function",
         "function": {"name": call.function.name, "arguments": call.function.arguments}}
        for call in message.tool_calls
    ],
})
```

The API validates that every `tool`-role message is answering some
specific `tool_calls` entry from an assistant message earlier in the
transcript. If you only append the tool's *result* and never store the
assistant message that asked for it, the very next request is rejected —
there's a tool message with nothing to point back to. So the assistant
message goes into `messages` first, unmodified, before any tool result.

### Rule 2 — tie each result to its call with `tool_call_id`

```python
messages.append({
    "role": "tool",
    "tool_call_id": call.id,
    "content": str(result),
})
```

A single assistant turn can request several tool calls at once. Each one
gets a unique `id`. When we answer it, we echo that same id back as
`tool_call_id` on the `tool`-role message. That's how the model knows which
result answers which request when there's more than one in flight.

### Errors are results

```python
def run_tool(name, args):
    fn = FUNCTIONS.get(name)
    if fn is None:
        return f"error: unknown tool '{name}'"
    try:
        return fn(**args)
    except Exception as exc:
        return f"error running {name}: {exc}"
```

A tool failure becomes a string that goes back into the transcript as a
normal tool result, not a Python exception that kills the loop. The model
gets to see the error and can retry or explain it. Stage 08 leans on this
same pattern for `str_replace`'s refusal messages.

## Diff

```powershell
git diff --no-index stage_04_read_file stage_05_agent_loop
```
