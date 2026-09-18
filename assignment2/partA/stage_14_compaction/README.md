# Stage 14 — Compaction

**The idea:** a long-running agent eventually fills its context window.
Reach for the cheapest fix first, and only escalate to something
expensive once the cheap options run out.

## Run it

```powershell
.venv\Scripts\python.exe stage_14_compaction\main.py
```

Compaction is invisible in normal use — it only does anything once the
transcript is large. The behavior is exercised directly in `run_tests.py`
by shrinking the fake context window to a few characters.

## The four mechanisms, cheapest to most expensive

All four live in `compaction.py`.

**1. `cap_fresh_result` — unconditional, applied at creation time.**

```python
def cap_fresh_result(content: str) -> str:
    if len(content) <= FRESH_RESULT_CAP:
        return content
    path = os.path.join(_temp_dir(), f"result_{time.time_ns()}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"(output was {len(content)} chars, over the {FRESH_RESULT_CAP} cap; full output written to {path}. ...)"
```

`main.py`'s `run_loop` calls this on every tool result the instant it's
produced — not later, during a size check. A single 500KB log dump should
never sit in memory at full size, even if the rest of the conversation is
nowhere near the window limit. This is the cheapest mechanism because it
needs no scan of the transcript, just one length check.

**2. `shrink_finished_results` — old tool output → a 300-char stub.**

```python
def shrink_finished_results(messages) -> bool:
    boundary = _last_user_index(messages)
    for m in messages[:boundary]:
        if m["role"] == "tool" and len(m["content"]) > FINISHED_STUB_LEN:
            m["content"] = f"(shrunk: was {len(m['content'])} chars) " + m["content"][:FINISHED_STUB_LEN]
            return True
    return False
```

A tool result "belongs to a finished turn" if it sits *before* the most
recent user message — the model already answered that turn and moved on.
Shrinking it is cheap: no API call, and the information has (presumably)
already been used.

**3. `drop_old_results` — even more aggressive, same finished-turn rule.**

```python
def drop_old_results(messages) -> bool:
    boundary = _last_user_index(messages)
    for m in messages[:boundary]:
        if m["role"] == "tool" and m["content"] != "(dropped: ...)":
            m["content"] = "(dropped: old tool result, no longer available)"
            return True
    return False
```

If shrinking to 300 chars still isn't enough, whole results from finished
turns get replaced with a one-line marker instead.

**4. `_summarize` — the expensive one: a whole extra API call.**

```python
def _summarize(messages, client, model):
    response = client.chat.completions.create(
        model=model,
        messages=messages + [{"role": "user", "content": "Write a short handoff note ..."}],
    )
    return response.choices[0].message.content
```

No `tools=` argument at all — the model can only write text, it cannot
act. `compact()` only reaches this if mechanisms 1-3 couldn't get the
transcript back under `LOW_WATER` (35%) of the window, which happens once
there's nothing cheap left to shrink or drop. Its result replaces almost
the whole transcript:

```python
def compact(messages, client, model, summarize_fn=None):
    if estimate_chars(messages) <= CONTEXT_WINDOW_CHARS * HIGH_WATER:
        return
    while estimate_chars(messages) > CONTEXT_WINDOW_CHARS * LOW_WATER:
        if shrink_finished_results(messages):
            continue
        if drop_old_results(messages):
            continue
        break
    if estimate_chars(messages) > CONTEXT_WINDOW_CHARS * HIGH_WATER:
        note = (summarize_fn or _summarize)(messages, client, model)
        system_msgs = [m for m in messages if m["role"] == "system"]
        messages[:] = system_msgs + [{"role": "user", "content": f"<handoff-note>\n{note}\n</handoff-note>"}]
```

`compact()` does nothing at all below `HIGH_WATER` (85%). Above it, it
tries the cheap mechanisms in a loop, escalating only when the cheaper one
had nothing left to touch. If it's *still* over 85% after exhausting
those — nothing left to shrink or drop — only then does it pay for a
summarizer call, and the result deliberately collapses the transcript
down to just the system prompt and the handoff note, which is nowhere
near the window, let alone 35% of it.

### Wired into main.py in two places

```python
# top of every loop iteration, before the request goes out
compact(messages, client, MODEL)
...
# every tool result, the moment it's produced
result = cap_fresh_result(str(run_tool(call.function.name, args)))
```

### Honesty note: characters, not tokens

`estimate_chars` counts characters, not tokens. A real tokenizer (like
`tiktoken`) wasn't part of this project's dependency list, and counting
characters is a defensible, if rough, proxy — English text runs roughly
4 characters per token. `CONTEXT_WINDOW_CHARS` is calibrated loosely
around that ratio, not measured against any specific model's actual
tokenizer. Treat the exact thresholds as illustrative, not precise.

## Diff

```powershell
git diff --no-index stage_13_sandbox stage_14_compaction
```
