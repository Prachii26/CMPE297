# Stage 06 — Chat UI

**The idea:** turn one exchange into a conversation, and separate *what
gets printed* from *how it looks on screen*. An outer loop keeps asking
for the next message. Every bit of drawing moves into `ui.py`, which knows
nothing about models, tools, or the OpenAI client.

## Run it

```powershell
.venv\Scripts\python.exe stage_06_chat_ui\main.py
```

Type a message, see tool calls and usage print as they happen, keep
chatting. Ctrl+C or Ctrl+D to quit.

## The code

Three files, and the boundary between them is the point of this stage:

- **`tools.py`** — unchanged from stage 05. Tool definitions.
- **`ui.py`** — every `print`/`console.print` in the program lives here.
- **`main.py`** — decides *when* to call ui functions; owns the loop.

```python
# ui.py
def print_usage(prompt_tokens, completion_tokens, total_tokens, cached_tokens=None):
    ...
```

`print_usage` takes four plain numbers. It doesn't take a `response`
object, doesn't import `openai`, doesn't know a `ChatCompletion` exists.
`main.py` is the one that reaches into `response.usage` and hands over
plain values:

```python
# main.py
usage = response.usage
details = getattr(usage, "prompt_tokens_details", None)
cached = getattr(details, "cached_tokens", None) if details else None
ui.print_usage(usage.prompt_tokens, usage.completion_tokens, usage.total_tokens, cached)
```

If we swapped providers, or swapped the SDK, `ui.py` would not need to
change — only the code in `main.py` that unpacks the response.

### The outer loop

```python
while True:
    try:
        user_input = ui.get_input()
    except (EOFError, KeyboardInterrupt):
        break
    ...
    messages.append({"role": "user", "content": user_input})
    reply = run_loop(client, messages)
    messages.append({"role": "assistant", "content": reply})
    ui.print_reply(reply)
```

`run_loop` is stage 05's inner loop, unchanged in shape — it still resolves
tool calls until the model answers in text. The outer `while True` is new:
it's what makes this a chat instead of a script that runs once.

### Usage after every call, not just the last one

`run_loop` calls `ui.print_usage(...)` inside its `for` loop, once per
`client.chat.completions.create(...)` call — including the intermediate
calls that only returned tool calls, not a final answer. A multi-tool-call
turn burns tokens on every hop, and hiding that until the end would make
the running cost invisible until stage 16 needs it.

## Diff

```powershell
git diff --no-index stage_05_agent_loop stage_06_chat_ui
```
